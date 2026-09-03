"""NumberValidator tests (spec §9): "inject a hallucinated numeral -> memo
must be rejected", plus the inverse — a memo whose numbers are all
traceable must pass."""
from __future__ import annotations

from agent.composer import ComposedMemo, ComposedSection
from agent.models import Finding, StepEvidence
from agent.validator import extract_numbers, validate

FINDINGS = [
    Finding(key="abnormal_lift_views", label="Abnormal lift", value=41234567, unit="views", query_id="memo-x:q1"),
    Finding(key="half_life_days", label="Half-life", value=6, unit="days", query_id="memo-x:q1"),
    Finding(key="spillover_pct", label="Spillover", value=22.4, unit="pct", query_id="memo-x:q4"),
]

EVIDENCE = [
    StepEvidence(
        step_id="q1_event_window_series", title="Event window", query_id="memo-x:q1",
        sql="SELECT 1", params={}, columns=["date", "views"],
        rows=[["2026-01-01", 900000], ["2026-01-02", 1200000]],
        row_count=2, elapsed_ms=42, rows_scanned=1_800_000_000,
    ),
]


def _memo(body: str) -> ComposedMemo:
    return ComposedMemo(headline="Test", sections=[ComposedSection(heading="Summary", body=body)])


def test_traceable_numbers_pass() -> None:
    body = "The trailer drove +41M attention-hours [q1] with a 6 day half-life [q1] and 22.4% spillover [q4]."
    result = validate(_memo(body), FINDINGS, EVIDENCE)
    assert result.passed, result.notes


def test_hallucinated_numeral_is_rejected() -> None:
    body = "The trailer drove an abnormal lift of 999999999 views [q1], a number invented by the model."
    result = validate(_memo(body), FINDINGS, EVIDENCE)
    assert not result.passed
    assert 999999999.0 in result.unverifiable_numbers


def test_small_numbers_are_ignored_as_ordinals() -> None:
    body = "This is the #1 title in its cohort, ranked over 3 comparable releases [q1]."
    result = validate(_memo(body), FINDINGS, EVIDENCE)
    assert result.passed, result.notes


def test_rounded_million_suffix_matches_raw_value() -> None:
    # 41234567 rounds to "~41.2M" in prose; tolerance should still accept it.
    body = "Abnormal lift reached roughly 41.2M views [q1]."
    result = validate(_memo(body), FINDINGS, EVIDENCE)
    assert result.passed, result.notes


def test_extract_numbers_strips_citation_markers() -> None:
    nums = extract_numbers("Lift of 500000 views [q12] over 14 days")
    assert 12.0 not in nums  # the citation ordinal must not be parsed as data
    assert 500000.0 in nums
