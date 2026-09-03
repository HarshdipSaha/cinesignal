"""SQL template tests (spec §9). Every playbook's every step must render
with a plausible param set, and the binders must reject injection attempts
and malformed values — this is the entire safety boundary for user-supplied
values reaching a query string."""
from __future__ import annotations

import pytest

from agent.playbook_loader import get_playbook
from agent.sql_template import ParamError, bind_search_text, render

SAMPLE_PARAMS = {
    "campaign_impact": {
        "q1_event_window_series": {"entity_id": "Q123", "window_start": "2026-01-01", "window_end": "2026-03-01"},
        "q2_cohort_candidates": {"entity_id": "Q123", "genres": ["Action", "Sci-Fi"], "cohort_size": 50},
        "q3_cohort_series": {"cohort_ids": ["Q1", "Q2"], "window_start": "2026-01-01", "window_end": "2026-03-01"},
        "q4_spillover_candidates": {"entity_id": "Q123", "spillover_limit": 5},
        "q5_spillover_series": {"spillover_ids": ["Q9"], "window_start": "2026-01-01", "window_end": "2026-03-01"},
    },
    "title_pulse": {
        "q1_daily_series": {"entity_id": "Q123", "start_date": "2023-01-01", "end_date": "2026-01-01"},
        "q2_cohort_candidates": {"entity_id": "Q123", "genres": ["Drama"], "cohort_size": 50},
        "q3_cohort_monthly": {"cohort_ids": ["Q1", "Q2", "Q123"], "start_date": "2023-01-01", "end_date": "2026-01-01"},
    },
    "launch_window": {
        "q1_competition_density": {"quarter_start": "2026-10-01", "quarter_end": "2026-12-31", "genres": ["Horror"]},
        "q2_competitor_attention": {"competitor_ids": ["Q5"], "lookback_start": "2026-07-01", "lookback_end": "2026-12-31"},
        "q3_seasonal_genre_demand": {"genres": ["Horror"], "lookback_start": "2021-10-01", "lookback_end": "2026-12-31"},
    },
}


@pytest.mark.parametrize("playbook_id", ["campaign_impact", "title_pulse", "launch_window"])
def test_every_step_renders(playbook_id: str) -> None:
    pb = get_playbook(playbook_id)
    for step_id, step in pb.steps.items():
        params = SAMPLE_PARAMS[playbook_id][step_id]
        sql = render(step.sql, params, step.param_types)
        assert "{{" not in sql, f"unsubstituted placeholder left in {playbook_id}/{step_id}"
        assert "SELECT" in sql.upper()


def test_wikidata_id_rejects_injection() -> None:
    pb = get_playbook("campaign_impact")
    step = pb.steps["q1_event_window_series"]
    with pytest.raises(ParamError):
        render(step.sql, {"entity_id": "Q1' OR '1'='1", "window_start": "2026-01-01", "window_end": "2026-03-01"}, step.param_types)


def test_date_rejects_non_iso() -> None:
    pb = get_playbook("campaign_impact")
    step = pb.steps["q1_event_window_series"]
    with pytest.raises(ParamError):
        render(step.sql, {"entity_id": "Q1", "window_start": "not-a-date", "window_end": "2026-03-01"}, step.param_types)


def test_missing_param_raises() -> None:
    pb = get_playbook("campaign_impact")
    step = pb.steps["q1_event_window_series"]
    with pytest.raises(ParamError):
        render(step.sql, {"entity_id": "Q1"}, step.param_types)


def test_search_text_escapes_quotes() -> None:
    escaped = bind_search_text("O'Brien's \"movie\"")
    assert escaped == "'O\\'Brien\\'s \"movie\"'"


def test_search_text_length_cap() -> None:
    with pytest.raises(ParamError):
        bind_search_text("x" * 500)


def test_genre_list_rejects_unsafe_token() -> None:
    from agent.sql_template import bind_genre_list

    with pytest.raises(ParamError):
        bind_genre_list(["Action'; DROP TABLE cinesignal.entities; --"])
