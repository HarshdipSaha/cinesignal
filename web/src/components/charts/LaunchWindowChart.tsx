import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import type { LaunchWindowChartData, LaunchWeekend } from "../../api/types";
import EmptyState from "../EmptyState";
import { CHART_COLORS, axisLineDim, baseOption } from "./echartsBase";

export default function LaunchWindowChart({ data }: { data: LaunchWindowChartData }) {
  const weekends = Array.isArray(data.weekends) ? data.weekends : [];

  if (weekends.length === 0) {
    return (
      <EmptyState
        title="No candidate weekends yet"
        detail="This memo didn't come back with a scored weekend window to chart."
      />
    );
  }

  const topSet = new Set((data.top3 ?? []).map((w) => w.weekend));

  const sorted = [...weekends].sort(
    (a, b) => (b.combined_score ?? 0) - (a.combined_score ?? 0),
  );

  const option: EChartsOption = {
    ...baseOption,
    grid: { left: 90, right: 32, top: 12, bottom: 32, containLabel: true },
    xAxis: {
      type: "value",
      name: "combined score",
      nameTextStyle: { color: CHART_COLORS.textFaint, fontSize: 10 },
      ...axisLineDim,
    },
    yAxis: {
      type: "category",
      data: sorted.map((w) => w.weekend).reverse(),
      ...axisLineDim,
      axisLabel: { color: CHART_COLORS.textDim, fontSize: 11 },
    },
    series: [
      {
        type: "bar",
        data: sorted
          .map((w) => ({
            value: w.combined_score ?? 0,
            itemStyle: {
              color: topSet.has(w.weekend) ? CHART_COLORS.accent : CHART_COLORS.teal,
              opacity: topSet.has(w.weekend) ? 1 : 0.55,
            },
          }))
          .reverse(),
        barWidth: "55%",
      },
    ],
  };

  return (
    <div>
      <ReactECharts option={option} style={{ height: Math.max(220, sorted.length * 34), width: "100%" }} notMerge />
      <div className="eyebrow" style={{ margin: "1.25rem 0 0.5rem" }}>
        WEEKEND DETAIL
      </div>
      <div className="drawer-table-wrap">
        <table className="drawer-table mono">
          <thead>
            <tr>
              <th>weekend</th>
              <th>score</th>
              <th>competitors</th>
              <th>attention mass</th>
              <th>seasonal idx</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((w) => (
              <tr key={w.weekend} style={topSet.has(w.weekend) ? { color: "var(--accent-strong)" } : undefined}>
                <td>
                  {w.weekend}
                  {topSet.has(w.weekend) ? " ★" : ""}
                </td>
                <td>{fmt(w.combined_score)}</td>
                <td>{fmtCompetitors(w)}</td>
                <td>{fmt(w.attention_mass)}</td>
                <td>{fmt(w.seasonal_index)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function fmt(n: number | undefined | null): string {
  if (n === undefined || n === null || Number.isNaN(n)) return "—";
  return typeof n === "number" ? n.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(n);
}

function fmtCompetitors(w: LaunchWeekend): string {
  if (w.competitor_count != null) return String(w.competitor_count);
  if (Array.isArray(w.competitors)) return String(w.competitors.length);
  return "—";
}
