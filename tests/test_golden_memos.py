"""Determinism test (spec §9): "same input -> identical numbers twice."

Exercises the actual runtime path — a real ClickHouseMCPSession talking to
mcp-clickhouse talking to ClickHouse Cloud — but only through PlaybookRunner
(agent/runner.py), which is where the determinism guarantee actually lives:
no LLM call sits between a set of params and a set of Finding values, so
this test does not require Vertex AI credentials. It's skipped automatically
if the warehouse doesn't have data yet (ingestion is a separate, long-running
process — see ingest/STATUS.md for current row counts).

Known flakiness while ingestion is still running: this test calls the same
playbook twice and diffs the results, but if new pageviews/entities rows
land between the two calls, the underlying data genuinely changed — that's
not a determinism bug, it's the dataset moving under a live test. Re-run in
isolation (or after ingestion finishes) to confirm; don't chase this as a
regression unless it fails on a static dataset.
"""
from __future__ import annotations

import asyncio
import os

import pytest
from dotenv import load_dotenv

load_dotenv()

from agent.mcp_client import ClickHouseMCPSession  # noqa: E402
from agent.models import ResolvedEntity  # noqa: E402
from agent.runner import PlaybookRunner  # noqa: E402


def _has_clickhouse_creds() -> bool:
    return all(os.environ.get(k) for k in ("CLICKHOUSE_HOST", "CLICKHOUSE_USER", "CLICKHOUSE_PASSWORD"))


async def _pick_fixture_entity() -> ResolvedEntity | None:
    """Any film/series entity with at least some attention rows — good
    enough as a golden fixture without hardcoding a wikidata_id that may
    not exist yet depending on how far ingestion has gotten."""
    async with ClickHouseMCPSession() as session:
        result = await session.run_query(
            "SELECT e.wikidata_id, e.page_title, e.entity_type, e.tconst, e.nconst, e.genres "
            "FROM cinesignal.entities e "
            "INNER JOIN cinesignal.entity_attention_daily a ON a.wikidata_id = e.wikidata_id "
            "WHERE e.entity_type IN ('film', 'series') AND e.genres != '' "
            "GROUP BY e.wikidata_id, e.page_title, e.entity_type, e.tconst, e.nconst, e.genres "
            "HAVING count() > 30 "
            "LIMIT 1",
            query_id="test-fixture-pick",
        )
    if result.error or not result.rows:
        return None
    wid, title, etype, tconst, nconst, genres = result.rows[0]
    return ResolvedEntity(
        wikidata_id=wid, label=title, entity_type=etype, tconst=tconst or "", nconst=nconst or "",
        genres=[g.strip() for g in genres.split(",") if g.strip()],
    )


@pytest.mark.skipif(not _has_clickhouse_creds(), reason="no ClickHouse credentials in environment")
def test_title_pulse_is_deterministic() -> None:
    entity = asyncio.run(_pick_fixture_entity())
    if entity is None:
        pytest.skip("no entity with attention data yet — ingestion likely still running, see ingest/STATUS.md")

    runner = PlaybookRunner()
    params = {"start_date": "2024-01-01", "end_date": "2026-01-01", "cohort_size": 30}

    async def run_once():
        _, findings, chart_data, verdict = await runner.run("title_pulse", entity, params)
        return findings, chart_data, verdict

    findings_a, chart_a, verdict_a = asyncio.run(run_once())
    findings_b, chart_b, verdict_b = asyncio.run(run_once())

    assert verdict_a == verdict_b
    values_a = [(f.key, f.value) for f in findings_a]
    values_b = [(f.key, f.value) for f in findings_b]
    assert values_a == values_b, "re-running the same playbook with the same params must reproduce identical numbers"
    assert chart_a.get("views") == chart_b.get("views")
