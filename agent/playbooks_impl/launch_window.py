"""P3 — Launch Window: rank candidate release weekends in a target quarter by
competition density (fewer/weaker same-quarter releases is better) and
seasonal genre demand (weeks where this genre historically draws more
attention is better)."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from agent.models import Finding, ResolvedEntity
from agent.runner import PlaybookContext
from agent.stats import mean

SEASONAL_LOOKBACK_YEARS = 5
COMPETITOR_BUZZ_LOOKBACK_DAYS = 90


def _quarter_bounds(year: int, quarter: int) -> tuple[date, date]:
    start_month = (quarter - 1) * 3 + 1
    start = date(year, start_month, 1)
    end_month = start_month + 2
    end_year = year + (1 if end_month > 12 else 0)
    end_month = end_month - 12 if end_month > 12 else end_month
    # last day of end_month
    next_month = date(end_year, end_month, 28) + timedelta(days=4)
    end = next_month - timedelta(days=next_month.day)
    return start, end


async def run(entity: ResolvedEntity, params: dict[str, Any], ctx: PlaybookContext) -> tuple[list[Finding], dict[str, Any], str]:
    year = int(params["year"])
    quarter = int(params["quarter"])
    genres = params.get("genres") or entity.genres

    findings: list[Finding] = []
    if not genres:
        findings.append(Finding(key="data_gap", label="No genre supplied or found on entity", value="insufficient_data", query_id="n/a"))
        return findings, {}, "INSUFFICIENT_DATA"

    quarter_start, quarter_end = _quarter_bounds(year, quarter)

    q1 = await ctx.query("q1_competition_density", {"quarter_start": quarter_start.isoformat(), "quarter_end": quarter_end.isoformat(), "genres": genres}, enrich=True)

    weekends = []
    all_competitor_ids: list[str] = []
    for weekend, count, competitors, competitor_ids in q1.rows:
        weekend_d = weekend if isinstance(weekend, date) else date.fromisoformat(weekend)
        weekends.append({"weekend": weekend_d, "competitor_count": int(count), "competitors": list(competitors), "competitor_ids": list(competitor_ids)})
        all_competitor_ids.extend(competitor_ids)
    all_competitor_ids = list(dict.fromkeys(all_competitor_ids))  # de-dupe, preserve order

    buzz_by_id: dict[str, float] = {}
    if all_competitor_ids:
        lookback_start = quarter_start - timedelta(days=COMPETITOR_BUZZ_LOOKBACK_DAYS)
        q2 = await ctx.query("q2_competitor_attention", {"competitor_ids": all_competitor_ids, "lookback_start": lookback_start.isoformat(), "lookback_end": quarter_end.isoformat()})
        buzz_by_id = {wid: float(v) for wid, v in q2.rows}

    for w in weekends:
        w["attention_mass"] = sum(buzz_by_id.get(cid, 0.0) for cid in w["competitor_ids"])

    seasonal_lookback_start = date(year - SEASONAL_LOOKBACK_YEARS, quarter_start.month, 1)
    q3 = await ctx.query("q3_seasonal_genre_demand", {"genres": genres, "lookback_start": seasonal_lookback_start.isoformat(), "lookback_end": quarter_end.isoformat()})
    seasonal_by_week = {int(week): float(avg_views) for week, avg_views, _ in q3.rows}
    overall_avg = mean(list(seasonal_by_week.values())) if seasonal_by_week else 0.0

    for w in weekends:
        week_num = w["weekend"].isocalendar()[1]
        seasonal_avg = seasonal_by_week.get(week_num)
        w["seasonal_index"] = round(seasonal_avg / overall_avg, 2) if seasonal_avg and overall_avg > 0 else None

    max_count = max((w["competitor_count"] for w in weekends), default=0) or 1
    max_mass = max((w["attention_mass"] for w in weekends), default=0.0) or 1.0
    for w in weekends:
        competition_penalty = 0.6 * (w["competitor_count"] / max_count) + 0.4 * (w["attention_mass"] / max_mass)
        seasonal_component = w["seasonal_index"] if w["seasonal_index"] is not None else 1.0
        w["combined_score"] = round(seasonal_component / (1.0 + competition_penalty), 3)

    ranked = sorted(weekends, key=lambda w: w["combined_score"], reverse=True)
    top3 = ranked[:3]

    for w in weekends:
        w["weekend"] = w["weekend"].isoformat()

    chart_data = {
        "quarter_start": quarter_start.isoformat(),
        "quarter_end": quarter_end.isoformat(),
        "weekends": weekends,
        "top3": [{"weekend": w["weekend"], "combined_score": w["combined_score"], "competitor_count": w["competitor_count"], "seasonal_index": w["seasonal_index"]} for w in top3],
    }

    findings.append(Finding(key="candidate_weekends", label="Candidate weekends evaluated", value=len(weekends), query_id=q1.query_id))
    for i, w in enumerate(top3, start=1):
        findings.append(Finding(key=f"top{i}_weekend", label=f"#{i} recommended weekend", value=w["weekend"], query_id=q1.query_id, extra=w))

    verdict = "RANKED" if top3 else "INSUFFICIENT_DATA"
    return findings, chart_data, verdict
