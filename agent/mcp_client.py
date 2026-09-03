"""Runtime wiring to the official `mcp-clickhouse` MCP server.

`ClickHouseMCPSession` is a thin async wrapper around the raw MCP
`ClientSession` (stdio transport) — used by the deterministic
`PlaybookRunner` (agent/runner.py) and by `agent/resolver.py`'s search
query. No LLM is in this path for SQL execution; determinism is the point.
Tracks per-query `query_id`/`elapsed_ms`/`rows_scanned` for the evidence
chain (API §6).

`get_shared_session()` hands out ONE long-lived session, reused across
every request in the process, instead of every caller spawning its own.
Spawning a fresh mcp-clickhouse subprocess per request measured at 1-13s
of pure startup overhead in production (worse under Cloud Run's
constrained cold-start CPU) — verified live, this was the dominant cost
in a "search feels slow" complaint, not the actual ClickHouse query.

Response format note: `run_query` returns one text content block whose text
is JSON `{"columns": [...], "rows": [[...], ...]}` — verified against a live
call against the ClickHouse Cloud cluster during the Gate-0 smoke test
(scripts/test_mcp_clickhouse.py), arrays-of-arrays, not per-row dicts.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import clickhouse_connect
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _clickhouse_env() -> dict[str, str]:
    """Environment for the mcp-clickhouse subprocess: read-only, our cluster."""
    env = dict(os.environ)
    env["CLICKHOUSE_HOST"] = os.environ["CLICKHOUSE_HOST"]
    env["CLICKHOUSE_PORT"] = os.environ.get("CLICKHOUSE_PORT", "8443")
    env["CLICKHOUSE_USER"] = os.environ["CLICKHOUSE_USER"]
    env["CLICKHOUSE_PASSWORD"] = os.environ["CLICKHOUSE_PASSWORD"]
    env["CLICKHOUSE_SECURE"] = "true"
    env["CLICKHOUSE_DATABASE"] = "cinesignal"
    # Belt-and-suspenders: this is meant to be a read-only agent user, but
    # also refuse writes/drops at the MCP-server level regardless of grants.
    env["CLICKHOUSE_ALLOW_WRITE_ACCESS"] = "false"
    env["CLICKHOUSE_ALLOW_DROP"] = "false"
    # mcp-clickhouse's default (30s) turned out too tight in production: the
    # ingestion pipeline runs unattended against the same cluster and its
    # bulk inserts occasionally starve concurrent reads for longer than
    # that (observed live: a resolve() search that normally takes ~0.3s hit
    # the 30s timeout during heavy ingest activity). Give queries more room
    # to survive that contention rather than hard-failing the whole request.
    env.setdefault("CLICKHOUSE_MCP_QUERY_TIMEOUT", "90")
    return env


def _mcp_clickhouse_bin() -> str:
    # Prefer the venv console-script exe (works on Windows without relying on
    # PATH); fall back to the bare command name for other environments.
    candidate = Path(sys.executable).parent / "mcp-clickhouse"
    return str(candidate) if candidate.exists() else "mcp-clickhouse"


def clickhouse_server_params() -> StdioServerParameters:
    return StdioServerParameters(command=_mcp_clickhouse_bin(), args=[], env=_clickhouse_env())


class QueryResult:
    __slots__ = ("query_id", "sql", "columns", "rows", "elapsed_ms", "rows_scanned", "error")

    def __init__(
        self,
        query_id: str,
        sql: str,
        columns: list[str],
        rows: list[list[Any]],
        elapsed_ms: int,
        rows_scanned: int | None = None,
        error: str | None = None,
    ) -> None:
        self.query_id = query_id
        self.sql = sql
        self.columns = columns
        self.rows = rows
        self.elapsed_ms = elapsed_ms
        self.rows_scanned = rows_scanned
        self.error = error

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def as_dicts(self) -> list[dict[str, Any]]:
        return [dict(zip(self.columns, r)) for r in self.rows]


class ClickHouseMCPSession:
    """Async context manager wrapping one live mcp-clickhouse stdio session.
    Opened once per playbook run and reused across all of that run's steps
    (spawning a fresh subprocess per query costs ~1-2s of startup)."""

    def __init__(self) -> None:
        self._stdio_ctx = None
        self._session_ctx = None
        self.session: ClientSession | None = None
        self._direct = None  # lazy clickhouse-connect client, for query_log enrichment only

    async def __aenter__(self) -> "ClickHouseMCPSession":
        self._stdio_ctx = stdio_client(clickhouse_server_params())
        read, write = await self._stdio_ctx.__aenter__()
        self._session_ctx = ClientSession(read, write)
        self.session = await self._session_ctx.__aenter__()
        await self.session.initialize()
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        if self._session_ctx is not None:
            await self._session_ctx.__aexit__(*exc_info)
        if self._stdio_ctx is not None:
            await self._stdio_ctx.__aexit__(*exc_info)

    async def list_tools(self) -> list[str]:
        assert self.session is not None
        result = await self.session.list_tools()
        return [t.name for t in result.tools]

    def _direct_client(self):
        if self._direct is None:
            self._direct = clickhouse_connect.get_client(
                host=os.environ["CLICKHOUSE_HOST"],
                port=int(os.environ["CLICKHOUSE_PORT"]),
                username=os.environ["CLICKHOUSE_USER"],
                password=os.environ["CLICKHOUSE_PASSWORD"],
                secure=True,
                database="cinesignal",
            )
        return self._direct

    async def _lookup_rows_scanned(self, sql: str) -> int | None:
        """Best-effort display enrichment ONLY — never on the execution path,
        never affects correctness (the MCP call above already has the real
        result rows). Originally polled system.query_log for read_rows, but
        that flushes asynchronously on ClickHouse Cloud (longer than made
        sense to block on) and was silently returning nothing — verified
        live: rows_scanned was landing as 0 in the UI, reading as "broken"
        rather than "not scanned much". clickhouse-connect exposes read_rows
        synchronously in the HTTP response summary instead, no flush-interval
        race — re-running the query direct (not via MCP) is an extra round
        trip, but a reliable one, only paid on the one "headline" query per
        playbook run that gets enrich=True."""
        import asyncio

        client = self._direct_client()
        try:
            result = await asyncio.to_thread(client.query, sql)
        except Exception:  # noqa: BLE001
            return None
        read_rows = (result.summary or {}).get("read_rows")
        return int(read_rows) if read_rows is not None else None

    async def run_query(self, sql: str, query_id: str, enrich_scan_stats: bool = False) -> QueryResult:
        assert self.session is not None, "session not started — use `async with`"
        t0 = time.perf_counter()
        try:
            result = await self.session.call_tool("run_query", {"query": sql})
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            return QueryResult(query_id, sql, [], [], elapsed_ms, None, error=str(exc))
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        text = "".join(getattr(block, "text", "") for block in result.content)
        if getattr(result, "isError", False):
            return QueryResult(query_id, sql, [], [], elapsed_ms, None, error=text or "MCP tool error")

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return QueryResult(
                query_id, sql, [], [], elapsed_ms, None, error=f"unparseable MCP response: {text[:300]}"
            )

        if isinstance(payload, dict) and "error" in payload and "rows" not in payload:
            return QueryResult(query_id, sql, [], [], elapsed_ms, None, error=str(payload["error"]))

        columns = payload.get("columns", [])
        rows = payload.get("rows", [])
        rows_scanned = await self._lookup_rows_scanned(sql) if enrich_scan_stats else None
        return QueryResult(query_id, sql, columns, rows, elapsed_ms, rows_scanned)


_shared_session: ClickHouseMCPSession | None = None
_shared_loop: asyncio.AbstractEventLoop | None = None
_shared_lock: asyncio.Lock | None = None


def _lock_for_current_loop() -> asyncio.Lock:
    """A fresh asyncio.Lock per event loop. Needed because this singleton
    also has to survive multiple asyncio.run() calls in one process (every
    test in tests/test_golden_memos.py, any script run repeatedly) — each
    asyncio.run() spins up and tears down its OWN event loop, and both the
    session's transport and a plain asyncio.Lock are loop-bound; reusing
    either across loops raised real errors here (RuntimeError: Attempted to
    exit cancel scope in a different task than it was entered in), verified
    live via pytest. A single long-running server process (uvicorn) only
    ever has one loop, so this never fires there — it's here for the
    multi-asyncio.run() case."""
    global _shared_lock, _shared_loop
    loop = asyncio.get_running_loop()
    if _shared_lock is None or _shared_loop is not loop:
        _shared_lock = asyncio.Lock()
    return _shared_lock


async def get_shared_session() -> ClickHouseMCPSession:
    """The one process-wide mcp-clickhouse session for the CURRENT event
    loop. Created lazily on first use, then reused for the life of that
    loop (see _lock_for_current_loop for why "loop" and not just
    "process")."""
    global _shared_session, _shared_loop
    lock = _lock_for_current_loop()
    async with lock:
        loop = asyncio.get_running_loop()
        if _shared_session is None or _shared_loop is not loop:
            session = ClickHouseMCPSession()
            await session.__aenter__()
            _shared_session = session
            _shared_loop = loop
    return _shared_session


async def reset_shared_session() -> None:
    """Drop the shared session so the next get_shared_session() spawns a
    fresh one. Call this after a run_query() that came back with `.error`
    set — that's ambiguous between "the SQL was bad" and "the subprocess/
    pipe died", and respawning is cheap enough that it's not worth telling
    those apart precisely: a live session never pays this cost, only the
    (rare) error path does.

    Deliberately does NOT call the session's __aexit__/graceful-close path:
    anyio's cancel scopes are bound to the task that entered them, and
    get_shared_session() was awaited inside whatever request task happened
    to create it first — a *different* task calling __aexit__ later (which
    is exactly what "reset from an error handler" means) hits anyio's
    "Attempted to exit cancel scope in a different task than it was entered
    in", verified live. Dropping the reference instead leaks the orphaned
    subprocess (it exits on its own once its stdin pipe closes) rather than
    risking that crash on a request path — an acceptable trade for a reset
    path that should rarely fire."""
    global _shared_session
    async with _lock_for_current_loop():
        _shared_session = None
