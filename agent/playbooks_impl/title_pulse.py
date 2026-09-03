"""P1 — Title Pulse: attention health-check vs. a same-genre cohort.

Methodology: monthly percentile rank of the target within its cohort (incl.
itself), top-10 |z-score| anomaly days on day-over-day view deltas, and
28-day momentum (last 28d vs. prior 28d)."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from agent.models import Finding, ResolvedEntity
from agent.runner import PlaybookContext
from agent.stats import mean, percentile_rank, series_to_map, zscores

DEFAULT_COHORT_SIZE = 50
DEFAULT_LOOKBACK_DAYS = 365 * 3  # 36 months


def _parse_date(v: Any) -> date:
    return v if isinstance(v, date) else datetime.strptime(str(v), "%Y-%m-%d").date()


async def run(entity: ResolvedEntity, params: dict[str, Any], ctx: PlaybookContext) -> tuple[list[Finding], dict[str, Any], str]:
    end_date = _parse_date(params["end_date"]) if params.get("end_date") else date.today()
    start_date = _parse_date(params["start_date"]) if params.get("start_date") else end_date - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    genres = params.get("genres") or entity.genres
    cohort_size = int(params.get("cohort_size", DEFAULT_COHORT_SIZE))

    q1 = await ctx.query(
        "q1_daily_series",
        {"entity_id": entity.wikidata_id, "start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        enrich=True,
    )
    series = series_to_map(q1.rows)
    dates_sorted = sorted(series.keys())

    findings: list[Finding] = []
    if not dates_sorted:
        findings.append(Finding(key="data_gap", label="No attention data in range", value="insufficient_data", query_id=q1.query_id))
        return findings, {}, "INSUFFICIENT_DATA"

    # Momentum: last 28d vs. prior 28d.
    last28 = [d for d in dates_sorted if d > end_date - timedelta(days=28)]
    prior28 = [d for d in dates_sorted if end_date - timedelta(days=56) < d <= end_date - timedelta(days=28)]
    last28_sum = sum(series[d] for d in last28)
    prior28_sum = sum(series[d] for d in prior28)
    momentum_pct = round(((last28_sum - prior28_sum) / prior28_sum) * 100.0, 1) if prior28_sum > 0 else None

    # Anomaly days: z-score of day-over-day deltas.
    deltas: list[tuple[date, float]] = []
    for i in range(1, len(dates_sorted)):
        d, prev = dates_sorted[i], dates_sorted[i - 1]
        deltas.append((d, series[d] - series[prev]))
    z = zscores([v for _, v in deltas]) if deltas else []
    anomalies = sorted(zip([d for d, _ in deltas], [v for _, v in deltas], z), key=lambda t: abs(t[2]), reverse=True)[:10]
    anomaly_days = [{"date": d.isoformat(), "delta_views": round(v), "z_score": round(zz, 2)} for d, v, zz in anomalies]

    chart_data: dict[str, Any] = {
        "dates": [d.isoformat() for d in dates_sorted],
        "views": [round(series[d]) for d in dates_sorted],
        "anomaly_days": anomaly_days,
    }

    findings.append(Finding(key="momentum_pct", label="28-day momentum", value=momentum_pct if momentum_pct is not None else "n/a", unit="pct", query_id=q1.query_id))
    findings.append(Finding(key="total_views", label="Total views in range", value=round(sum(series.values())), unit="views", query_id=q1.query_id))
    findings.append(Finding(key="top_anomaly_day", label="Largest anomaly day", value=anomaly_days[0]["date"] if anomaly_days else "n/a", query_id=q1.query_id, extra={"anomalies": anomaly_days}))

    verdict = "INSUFFICIENT_DATA"
    if genres:
        q2 = await ctx.query("q2_cohort_candidates", {"entity_id": entity.wikidata_id, "genres": genres, "cohort_size": cohort_size})
        cohort_ids = [r[0] for r in q2.rows]
        if cohort_ids:
            all_ids = cohort_ids + [entity.wikidata_id]
            q3 = await ctx.query("q3_cohort_monthly", {"cohort_ids": all_ids, "start_date": start_date.isoformat(), "end_date": end_date.isoformat()})
            by_month: dict[str, dict[str, float]] = {}
            for wid, month, views in q3.rows:
                month_key = month if isinstance(month, str) else month.isoformat()
                by_month.setdefault(month_key, {})[wid] = float(views)

            monthly_percentiles = []
            for month_key in sorted(by_month.keys()):
                pop = by_month[month_key]
                target_v = pop.get(entity.wikidata_id)
                if target_v is None:
                    continue
                pct = percentile_rank(target_v, list(pop.values()))
                monthly_percentiles.append({"month": month_key, "percentile": pct, "views": round(target_v)})

            chart_data["monthly_percentile"] = monthly_percentiles
            if monthly_percentiles:
                latest_pct = monthly_percentiles[-1]["percentile"]
                findings.append(Finding(key="latest_cohort_percentile", label="Percentile vs. same-genre cohort (latest month)", value=latest_pct, unit="pct", query_id=q3.query_id))
                trend = "RISING" if len(monthly_percentiles) >= 2 and monthly_percentiles[-1]["percentile"] > monthly_percentiles[-2]["percentile"] else "STABLE_OR_DECLINING"
                if momentum_pct is not None and momentum_pct > 15:
                    verdict = "RISING"
                elif momentum_pct is not None and momentum_pct < -15:
                    verdict = "DECLINING"
                else:
                    verdict = "STABLE"
                findings.append(Finding(key="percentile_trend", label="Month-over-month percentile trend", value=trend, query_id=q3.query_id))

    return findings, chart_data, verdict
