"""PlaybookRunner — the deterministic engine. No LLM call happens anywhere in
this file or in agent/playbooks_impl/*: every number a memo cites traces back
to a `{{param}}`-bound SQL template executed via ClickHouseMCPSession, plus
plain arithmetic on the returned rows. This is what makes a memo reproducible."""
from __future__ import annotations

import uuid
from typing import Any, Awaitable, Callable

from agent.mcp_client import ClickHouseMCPSession, QueryResult, get_shared_session, reset_shared_session
from agent.models import Finding, ResolvedEntity, StepEvidence
from agent.playbook_loader import Playbook, get_playbook
from agent.sql_template import render

EventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


class PlaybookContext:
    """Handed to each playbook_impl module. Executes one templated step at a
    time, logging full evidence (SQL text, params, rows, timing) for every
    call — this list becomes the memo's evidence chain."""

    def __init__(self, playbook: Playbook, session: ClickHouseMCPSession, memo_id: str, on_event: EventCallback | None):
        self.playbook = playbook
        self.session = session
        self.memo_id = memo_id
        self.on_event = on_event
        self.evidence: list[StepEvidence] = []
        self._n = 0

    async def query(self, step_id: str, params: dict[str, Any], enrich: bool = False) -> QueryResult:
        step = self.playbook.steps[step_id]
        sql = render(step.sql, params, step.param_types)
        self._n += 1
        query_id = f"{self.memo_id}:q{self._n}"
        result = await self.session.run_query(sql, query_id, enrich_scan_stats=enrich)
        ev = StepEvidence(
            step_id=step_id,
            title=step.title,
            query_id=query_id,
            sql=sql,
            params=params,
            columns=result.columns,
            rows=result.rows,
            row_count=result.row_count,
            elapsed_ms=result.elapsed_ms,
            rows_scanned=result.rows_scanned,
            error=result.error,
        )
        self.evidence.append(ev)
        if self.on_event:
            await self.on_event(
                "step",
                {
                    "step_id": step_id,
                    "title": step.title,
                    "query_id": query_id,
                    "row_count": ev.row_count,
                    "elapsed_ms": ev.elapsed_ms,
                    "error": ev.error,
                },
            )
        return result


class PlaybookRunner:
    """Dispatches to the right playbooks_impl module by playbook id."""

    async def run(
        self,
        playbook_id: str,
        entity: ResolvedEntity,
        params: dict[str, Any],
        on_event: EventCallback | None = None,
    ) -> tuple[list[StepEvidence], list[Finding], dict[str, Any], str]:
        playbook = get_playbook(playbook_id)
        memo_id = f"memo-{uuid.uuid4().hex[:12]}"

        impl = _load_impl(playbook_id)

        session = await get_shared_session()
        ctx = PlaybookContext(playbook, session, memo_id, on_event)
        if on_event:
            await on_event("stage", {"stage": "querying", "message": f"Running {playbook.name} v{playbook.version}"})
        findings, chart_data, verdict = await impl.run(entity, params, ctx)

        if any(e.error for e in ctx.evidence):
            await reset_shared_session()

        return ctx.evidence, findings, chart_data, verdict


def _load_impl(playbook_id: str):
    import importlib

    return importlib.import_module(f"agent.playbooks_impl.{playbook_id}")
