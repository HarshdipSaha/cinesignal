"""P2 — Campaign Impact (the flagship playbook).

Event-study methodology (documented here because it's the thing a judge or a
skeptical marketer will ask about):

1. Pull the target entity's daily attention for [event_date - pre, event_date + post].
2. Pull the same calendar window for up to `cohort_size` same-genre titles.
3. Each cohort title is baseline-scaled: scale = target's pre-window mean /
   cohort title's pre-window mean (its own attention level, not the target's —
   this controls for "some franchises are just bigger than others").
4. The counterfactual for day d is the MEDIAN of the scaled cohort values at
   day d — "what a comparably-sized same-genre title's attention typically
   looks like on this same calendar day," used as the no-event baseline.
5. Abnormal lift = sum(actual - counterfactual) over [event_date, event_date + lift_window].
6. Half-life = days from the peak of (actual - counterfactual) until that
   excess first decays to <= half its peak value.
7. Verdict: target's own lift-window sum vs. the distribution of the SCALED
   cohort's lift-window sums (not a nested counterfactual per cohort member —
   that would be a much more expensive recursive computation; this is a
   deliberate, documented approximation) -> BREAKOUT / IN-LINE / UNDERPERFORMED.
8. Spillover: % change in cast/director attention, post-event mean vs.
   pre-event baseline mean, averaged across principals with a usable baseline.

`attention_hours` is an explicit, documented estimate (ATTENTION_MINUTES_PER_VIEW
below), not a measured quantity — pageview logs don't carry dwell time.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from agent.models import Finding, ResolvedEntity
from agent.runner import PlaybookContext
from agent.stats import daterange, mean, median, percentile_rank, series_to_map

ATTENTION_MINUTES_PER_VIEW = 3.0  # documented assumption, not measured

DEFAULT_COHORT_SIZE = 50
DEFAULT_SPILLOVER_LIMIT = 5
PRE_WINDOW_DAYS = 60
POST_WINDOW_DAYS = 30
LIFT_WINDOW_DAYS = 14


def _parse_date(v: Any) -> date:
    return v if isinstance(v, date) else datetime.strptime(str(v), "%Y-%m-%d").date()


async def run(entity: ResolvedEntity, params: dict[str, Any], ctx: PlaybookContext) -> tuple[list[Finding], dict[str, Any], str]:
    event_date = _parse_date(params["event_date"])
    genres = params.get("genres") or entity.genres
    cohort_size = int(params.get("cohort_size", DEFAULT_COHORT_SIZE))
    spillover_limit = int(params.get("spillover_limit", DEFAULT_SPILLOVER_LIMIT))

    window_start = event_date - timedelta(days=PRE_WINDOW_DAYS)
    window_end = event_date + timedelta(days=POST_WINDOW_DAYS)

    q1 = await ctx.query(
        "q1_event_window_series",
        {"entity_id": entity.wikidata_id, "window_start": window_start.isoformat(), "window_end": window_end.isoformat()},
        enrich=True,
    )
    target_series = series_to_map(q1.rows)

    findings: list[Finding] = []
    chart_data: dict[str, Any] = {}

    if not genres:
        findings.append(Finding(key="data_gap", label="No genre data for entity", value="insufficient_data", query_id=q1.query_id))
        return findings, chart_data, "INSUFFICIENT_DATA"

    q2 = await ctx.query("q2_cohort_candidates", {"entity_id": entity.wikidata_id, "genres": genres, "cohort_size": cohort_size})
    cohort_ids = [r[0] for r in q2.rows]

    if not cohort_ids:
        findings.append(Finding(key="data_gap", label="No cohort titles found for these genres", value="insufficient_data", query_id=q2.query_id))
        return findings, chart_data, "INSUFFICIENT_DATA"

    q3 = await ctx.query(
        "q3_cohort_series",
        {"cohort_ids": cohort_ids, "window_start": window_start.isoformat(), "window_end": window_end.isoformat()},
    )
    cohort_series: dict[str, dict[date, float]] = {}
    for wid, d, views in q3.rows:
        d = d if isinstance(d, date) else date.fromisoformat(d)
        cohort_series.setdefault(wid, {})[d] = float(views)

    pre_days = list(daterange(window_start, event_date - timedelta(days=1)))
    target_baseline = mean([target_series.get(d, 0.0) for d in pre_days])

    scaled_cohort: dict[str, dict[date, float]] = {}
    for wid, series in cohort_series.items():
        cohort_baseline = mean([series.get(d, 0.0) for d in pre_days])
        if cohort_baseline <= 0:
            continue
        scale = target_baseline / cohort_baseline if target_baseline > 0 else 0.0
        scaled_cohort[wid] = {d: v * scale for d, v in series.items()}

    all_days = list(daterange(window_start, window_end))
    counterfactual: dict[date, float] = {}
    for d in all_days:
        values = [s[d] for s in scaled_cohort.values() if d in s]
        counterfactual[d] = median(values) or 0.0

    actual = {d: target_series.get(d, 0.0) for d in all_days}
    excess = {d: actual[d] - counterfactual[d] for d in all_days}

    lift_days = [event_date + timedelta(days=i) for i in range(0, LIFT_WINDOW_DAYS + 1)]
    abnormal_lift_views = sum(excess.get(d, 0.0) for d in lift_days)
    abnormal_lift_hours = abnormal_lift_views * ATTENTION_MINUTES_PER_VIEW / 60.0

    post_days = [event_date + timedelta(days=i) for i in range(0, POST_WINDOW_DAYS + 1)]
    peak_day = max(post_days, key=lambda d: excess.get(d, 0.0))
    peak_excess = excess.get(peak_day, 0.0)
    half_life_days: int | None = None
    if peak_excess > 0:
        for d in post_days:
            if d < peak_day:
                continue
            if excess.get(d, 0.0) <= peak_excess / 2:
                half_life_days = (d - peak_day).days
                break

    # Verdict: target's raw lift-window sum vs. the distribution of the
    # scaled cohort's own lift-window sums (documented approximation, see
    # module docstring point 7).
    cohort_lift_sums = [sum(s.get(d, 0.0) for d in lift_days) for s in scaled_cohort.values()]
    target_lift_sum = sum(actual.get(d, 0.0) for d in lift_days)
    pct = percentile_rank(target_lift_sum, cohort_lift_sums) if cohort_lift_sums else 50.0
    if pct >= 90:
        verdict = "BREAKOUT"
    elif pct <= 25:
        verdict = "UNDERPERFORMED"
    else:
        verdict = "IN_LINE"

    # Spillover: cast/crew attention lift around the same event.
    spillover_rows: list[dict[str, Any]] = []
    q4 = await ctx.query("q4_spillover_candidates", {"entity_id": entity.wikidata_id, "spillover_limit": spillover_limit})
    spillover_ids = [r[0] for r in q4.rows]
    spillover_titles = {r[0]: r[1] for r in q4.rows}
    if spillover_ids:
        q5 = await ctx.query(
            "q5_spillover_series",
            {"spillover_ids": spillover_ids, "window_start": window_start.isoformat(), "window_end": window_end.isoformat()},
        )
        person_series: dict[str, dict[date, float]] = {}
        for wid, d, views in q5.rows:
            d = d if isinstance(d, date) else date.fromisoformat(d)
            person_series.setdefault(wid, {})[d] = float(views)

        pct_lifts: list[float] = []
        for pid, series in person_series.items():
            baseline = mean([series.get(d, 0.0) for d in pre_days])
            post_avg = mean([series.get(d, 0.0) for d in lift_days])
            pct_lift = ((post_avg - baseline) / baseline * 100.0) if baseline > 0 else None
            spillover_rows.append({"wikidata_id": pid, "label": spillover_titles.get(pid, pid), "pct_lift": pct_lift})
            if pct_lift is not None:
                pct_lifts.append(pct_lift)
        spillover_pct = round(mean(pct_lifts), 1) if pct_lifts else None
    else:
        spillover_pct = None

    findings = [
        Finding(key="abnormal_lift_views", label="Abnormal lift (views, +14d)", value=round(abnormal_lift_views), unit="views", query_id=q1.query_id),
        Finding(key="abnormal_lift_hours", label="Abnormal lift (attention-hours, +14d, est.)", value=round(abnormal_lift_hours), unit="hours", query_id=q1.query_id, extra={"minutes_per_view_assumption": ATTENTION_MINUTES_PER_VIEW}),
        Finding(key="half_life_days", label="Spike half-life", value=half_life_days if half_life_days is not None else "no decay observed in window", unit="days", query_id=q1.query_id),
        Finding(key="cohort_percentile", label="Percentile vs. same-genre cohort (+14d lift)", value=pct, unit="pct", query_id=q3.query_id),
        Finding(key="cohort_size_used", label="Cohort size used", value=len(scaled_cohort), unit="titles", query_id=q2.query_id),
        Finding(key="target_baseline_daily", label="Pre-window daily baseline", value=round(target_baseline), unit="views/day", query_id=q1.query_id),
    ]
    if spillover_pct is not None:
        findings.append(Finding(key="spillover_pct", label="Cast/crew spillover (avg % lift)", value=spillover_pct, unit="pct", query_id=q4.query_id, extra={"people": spillover_rows}))

    chart_data = {
        "event_date": event_date.isoformat(),
        "dates": [d.isoformat() for d in all_days],
        "actual": [round(actual[d], 1) for d in all_days],
        "counterfactual": [round(counterfactual[d], 1) for d in all_days],
        "spillover": spillover_rows,
    }

    return findings, chart_data, verdict
