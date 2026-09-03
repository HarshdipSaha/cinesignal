"""Runtime wiring to the official `mcp-clickhouse` MCP server.

Two consumers, both hitting the SAME server/protocol at runtime:

1. `ClickHouseMCPSession` — a thin async wrapper around the raw MCP
   `ClientSession` (stdio transport). Used by the deterministic
   `PlaybookRunner` (agent/runner.py) to execute versioned SQL templates.
   No LLM is in this path; determinism is the point. Tracks per-query
   `query_id`/`elapsed_ms`/`rows_scanned` for the evidence chain (API §6).

2. `build_mcp_toolset()` — wraps the same server as a google-adk
   `McpToolset`, for use by the `LlmAgent`-based EntityResolver
   (agent/resolver.py), which genuinely needs an LLM to judge which
   candidate row is the right match.

Response format note: `run_query` returns one text content block whose text
is JSON `{"columns": [...], "rows": [[...], ...]}` — verified against a live
call against the ClickHouse Cloud cluster during the Gate-0 smoke test
(scripts/test_mcp_clickhouse.py), arrays-of-arrays, not per-row dicts.
"""
from __future__ import annotations

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
        """Best-effort display enrichment ONLY — never on the execution
        path, never affects correctness. system.query_log flushes
        asynchronously so this may legitimately find nothing in time."""
        import asyncio

        client = self._direct_client()
        for _ in range(4):
            await asyncio.sleep(0.5)
            try:
                res = client.query(
                    "SELECT read_rows FROM system.query_log "
                    "WHERE type = 'QueryFinish' AND query = {q:String} "
                    "ORDER BY event_time_microseconds DESC LIMIT 1",
                    parameters={"q": sql.strip()},
                )
                if res.result_rows:
                    return int(res.result_rows[0][0])
            except Exception:  # noqa: BLE001
                return None
        return None

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


def build_mcp_toolset(tool_filter: list[str] | None = None):
    """google-adk McpToolset wired to the same mcp-clickhouse server, for
    LLM-driven tool use (EntityResolver's candidate search). Imported lazily
    so this module stays importable before google-adk/ADC are configured."""
    from google.adk.tools.mcp_tool import McpToolset
    from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams

    return McpToolset(
        connection_params=StdioConnectionParams(server_params=clickhouse_server_params(), timeout=30),
        tool_filter=tool_filter or ["run_query", "list_databases", "list_tables"],
    )
