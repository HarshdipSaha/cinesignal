"""Orchestrator — wires EntityResolver -> PlaybookRunner -> Interpreter ->
MemoComposer -> NumberValidator into one playbook run, matching the spec's
architecture (§3). This is the single entrypoint the API layer calls.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import date
from typing import Any, Awaitable, Callable

import clickhouse_connect

from agent import resolver
from agent.composer import compose
from agent.interpreter import interpret
from agent.models import Memo, MemoSection, ResolvedEntity
from agent.runner import PlaybookRunner
from agent.validator import validate

EventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]

MAX_COMPOSE_ATTEMPTS = 2


class PlaybookExecutionError(Exception):
    pass


def _state_client():
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ["CLICKHOUSE_PORT"]),
        username=os.environ["CLICKHOUSE_USER"],
        password=os.environ["CLICKHOUSE_PASSWORD"],
        secure=True,
        database="cinesignal",
    )


def _json_default(o: Any) -> Any:
    if isinstance(o, date):
        return o.isoformat()
    raise TypeError(f"not JSON serializable: {type(o)}")


async def resolve_entity(query: str, entity_type: str | None = None) -> tuple[ResolvedEntity | None, list[ResolvedEntity]]:
    return await resolver.resolve(query, entity_type)


async def run_playbook(
    playbook_id: str,
    entity: ResolvedEntity,
    params: dict[str, Any],
    on_event: EventCallback | None = None,
) -> Memo:
    async def emit(event_type: str, data: dict[str, Any]) -> None:
        if on_event:
            await on_event(event_type, data)

    await emit("stage", {"stage": "resolved", "entity": entity.model_dump()})

    runner = PlaybookRunner()
    evidence, findings, chart_data, verdict = await runner.run(playbook_id, entity, params, on_event)
    await emit("stage", {"stage": "queried", "step_count": len(evidence), "verdict": verdict})

    from agent.playbook_loader import get_playbook

    playbook = get_playbook(playbook_id)

    citation_index = {e.query_id: f"q{i + 1}" for i, e in enumerate(evidence)}
    query_ids_ordered = [e.query_id for e in evidence]

    insights = await interpret(playbook.name, verdict, findings, chart_data)
    await emit("stage", {"stage": "interpreted", "headline": insights.headline})

    composed = None
    validation = None
    for attempt in range(1, MAX_COMPOSE_ATTEMPTS + 1):
        composed = await compose(entity, playbook.name, verdict, findings, insights, citation_index)
        validation = validate(composed, findings, evidence)
        if validation.passed:
            break
        await emit("stage", {"stage": "validation_retry", "attempt": attempt, "unverifiable": validation.unverifiable_numbers})

    if composed is None or validation is None:
        raise PlaybookExecutionError("memo composition failed")

    memo_id = evidence[0].query_id.split(":")[0] if evidence else f"memo-{uuid.uuid4().hex[:12]}"

    memo = Memo(
        memo_id=memo_id,
        playbook_id=playbook.id,
        playbook_version=playbook.version,
        entity=entity,
        params=params,
        verdict=verdict,
        headline=composed.headline,
        sections=[MemoSection(heading=s.heading, body=s.body) for s in composed.sections],
        findings=findings,
        chart_data=chart_data,
        query_ids=query_ids_ordered,
        validated=validation.passed,
        validator_notes=validation.notes,
    )

    _persist(memo, evidence)
    await emit("memo", {"memo_id": memo.memo_id, "validated": memo.validated})
    return memo


def _persist(memo: Memo, evidence: list) -> None:
    client = _state_client()
    now_rows = []
    for e in evidence:
        now_rows.append(
            [
                e.query_id,
                memo.memo_id,
                e.step_id,
                e.sql,
                json.dumps(e.params, default=_json_default),
                json.dumps(e.columns),
                json.dumps(e.rows[:500], default=_json_default),  # cap stored row payload
                e.row_count,
                e.rows_scanned or 0,
                e.elapsed_ms,
            ]
        )
    if now_rows:
        client.insert(
            "cinesignal.query_log",
            now_rows,
            column_names=["query_id", "memo_id", "step_id", "sql", "params", "columns", "rows_json", "row_count", "rows_scanned", "elapsed_ms"],
        )

    client.insert(
        "cinesignal.memos",
        [[
            memo.memo_id,
            memo.playbook_id,
            memo.playbook_version,
            memo.entity.wikidata_id,
            memo.entity.label,
            json.dumps(memo.params, default=_json_default),
            memo.verdict,
            memo.model_dump_json(),
            json.dumps(memo.query_ids),
        ]],
        column_names=["memo_id", "playbook_id", "playbook_version", "entity_id", "entity_label", "params", "verdict", "memo_json", "query_ids"],
    )
