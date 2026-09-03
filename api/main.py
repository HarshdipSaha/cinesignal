"""CineSignal API — FastAPI backend. Serves /api/* and (in production) the
built React SPA as static files. Run: `uvicorn api.main:app --reload`."""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent import resolver, tree  # noqa: E402
from api.db import get_client  # noqa: E402

app = FastAPI(title="CineSignal API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # hackathon demo; tighten if this ships past judging
    allow_methods=["*"],
    allow_headers=["*"],
)

PLAYBOOK_ALIASES = {
    "p1": "title_pulse", "title_pulse": "title_pulse",
    "p2": "campaign_impact", "campaign_impact": "campaign_impact",
    "p3": "launch_window", "launch_window": "launch_window",
}


def _resolve_playbook_id(raw: str) -> str:
    pid = PLAYBOOK_ALIASES.get(raw)
    if pid is None:
        raise HTTPException(404, f"unknown playbook: {raw!r}")
    return pid


@app.get("/api/resolve")
async def api_resolve(q: str, entity_type: str | None = None) -> dict[str, Any]:
    if not q or not q.strip():
        raise HTTPException(400, "q is required")
    best, candidates = await resolver.resolve(q.strip(), entity_type)
    return {
        "best_match": best.model_dump() if best else None,
        "candidates": [c.model_dump() for c in candidates],
    }


class RunRequest(BaseModel):
    entity_id: str
    params: dict[str, Any] = {}


@app.post("/api/playbooks/{playbook}/run")
async def api_run_playbook(playbook: str, req: RunRequest):
    playbook_id = _resolve_playbook_id(playbook)
    entity = await resolver.get_by_id(req.entity_id)
    if entity is None:
        raise HTTPException(404, f"unknown entity_id: {req.entity_id!r}")

    params = _apply_playbook_defaults(playbook_id, req.params)

    queue: asyncio.Queue = asyncio.Queue()
    SENTINEL = object()

    async def on_event(event_type: str, data: dict[str, Any]) -> None:
        await queue.put({"type": event_type, **data})

    async def worker() -> None:
        try:
            memo = await tree.run_playbook(playbook_id, entity, params, on_event)
            await queue.put({"type": "done", "memo_id": memo.memo_id, "validated": memo.validated})
        except Exception as exc:  # noqa: BLE001
            await queue.put({"type": "error", "message": str(exc)})
        finally:
            await queue.put(SENTINEL)

    task = asyncio.create_task(worker())

    async def event_stream():
        try:
            while True:
                item = await queue.get()
                if item is SENTINEL:
                    break
                yield f"data: {json.dumps(item, default=str)}\n\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _apply_playbook_defaults(playbook_id: str, params: dict[str, Any]) -> dict[str, Any]:
    params = dict(params)
    if playbook_id == "campaign_impact":
        params.setdefault("event_date", date.today().isoformat())
        params.setdefault("cohort_size", 50)
        params.setdefault("spillover_limit", 5)
    elif playbook_id == "title_pulse":
        params.setdefault("end_date", date.today().isoformat())
        params.setdefault("start_date", (date.today() - timedelta(days=365 * 3)).isoformat())
        params.setdefault("cohort_size", 50)
    elif playbook_id == "launch_window":
        today = date.today()
        params.setdefault("year", today.year + (1 if today.month > 9 else 0))
        params.setdefault("quarter", 1)
    return params


@app.get("/api/memo/{memo_id}")
async def api_get_memo(memo_id: str) -> dict[str, Any]:
    client = get_client()
    res = client.query(
        "SELECT memo_json FROM cinesignal.memos WHERE memo_id = {id:String} ORDER BY created_at DESC LIMIT 1",
        parameters={"id": memo_id},
    )
    if not res.result_rows:
        raise HTTPException(404, f"unknown memo_id: {memo_id!r}")
    return json.loads(res.result_rows[0][0])


@app.get("/api/evidence/{query_id:path}")
async def api_get_evidence(query_id: str) -> dict[str, Any]:
    client = get_client()
    res = client.query(
        "SELECT sql, params, columns, rows_json, row_count, rows_scanned, elapsed_ms, created_at "
        "FROM cinesignal.query_log WHERE query_id = {id:String} ORDER BY created_at DESC LIMIT 1",
        parameters={"id": query_id},
    )
    if not res.result_rows:
        raise HTTPException(404, f"unknown query_id: {query_id!r}")
    sql, params, columns_json, rows_json, row_count, rows_scanned, elapsed_ms, created_at = res.result_rows[0]
    columns: list[str] = json.loads(columns_json) if columns_json else []
    raw_rows: list[list[Any]] = json.loads(rows_json)
    # Frontend wants {col: value} rows, not raw arrays — zip using the
    # column order captured alongside the query at execution time.
    row_dicts = [dict(zip(columns, r)) for r in raw_rows] if columns else raw_rows
    return {
        "query_id": query_id,
        "sql": sql,
        "params": json.loads(params),
        "columns": columns,
        "rows": row_dicts,
        "row_count": row_count,
        "rows_scanned": rows_scanned,
        "elapsed_ms": elapsed_ms,
        "created_at": created_at.isoformat() if isinstance(created_at, datetime) else str(created_at),
    }


@app.get("/api/explore/{entity_id}")
async def api_explore(entity_id: str, months: int = 36) -> dict[str, Any]:
    """Public fan-explorer series — direct query, no agent tree, no LLM."""
    from agent.sql_template import bind_wikidata_id

    client = get_client()
    res = client.query(
        "SELECT page_title, entity_type, genres, release_date FROM cinesignal.entities "
        f"WHERE wikidata_id = {bind_wikidata_id(entity_id)} LIMIT 1"
    )
    if not res.result_rows:
        raise HTTPException(404, f"unknown entity_id: {entity_id!r}")
    label, entity_type, genres, release_date = res.result_rows[0]

    series = client.query(
        "SELECT date, sum(views) AS views FROM cinesignal.entity_attention_daily "
        f"WHERE wikidata_id = {bind_wikidata_id(entity_id)} "
        "AND date >= today() - INTERVAL {m:UInt16} MONTH GROUP BY date ORDER BY date",
        parameters={"m": months},
    )
    return {
        "entity": {"wikidata_id": entity_id, "label": label, "entity_type": entity_type, "genres": genres, "release_date": str(release_date) if release_date else None},
        "series": [{"date": str(d), "views": int(v)} for d, v in series.result_rows],
    }


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Serve the built SPA in production (web/dist), if present. Dev mode runs
# the Vite dev server separately (see web/README / package.json scripts).
#
# StaticFiles(html=True) alone only serves exact file matches (plus "/" ->
# index.html) — it 404s on client-side routes like /memo/:id, which breaks
# on any page refresh or shared/deep link (confirmed live: 404 on
# /memo/<real id>). So assets are mounted at their own sub-path, and every
# other non-API path falls through to a catch-all that serves index.html
# and lets React Router take over client-side.
_SPA_DIST = ROOT / "web" / "dist"
if _SPA_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_SPA_DIST / "assets")), name="spa-assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404, f"no such API route: /{full_path}")
        candidate = _SPA_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_SPA_DIST / "index.html")
