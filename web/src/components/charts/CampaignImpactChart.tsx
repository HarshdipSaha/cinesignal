import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import type { CampaignImpactChartData } from "../../api/types";
import EmptyState from "../EmptyState";
import { CHART_COLORS, axisLineDim, baseOption } from "./echartsBase";

export default function CampaignImpactChart({ data }: { data: CampaignImpactChartData }) {
  const dates = Array.isArray(data.dates) ? data.dates : [];
  const actual = Array.isArray(data.actual) ? data.actual : [];
  const counterfactual = Array.isArray(data.counterfactual) ? data.counterfactual : [];

  if (dates.length === 0 || actual.length === 0) {
    return (
      <EmptyState
        title="No time series yet"
        detail="This memo didn't come back with an actual-vs-counterfactual series to chart."
      />
    );
  }

  const eventIndex = data.event_date ? dates.indexOf(data.event_date) : -1;

  const option: EChartsOption = {
    ...baseOption,
    legend: {
      data: ["Actual", "Counterfactual"],
      top: 0,
      left: 0,
      textStyle: { color: CHART_COLORS.textDim, fontSize: 11 },
      itemWidth: 14,
      itemHeight: 8,
    },
    xAxis: {
      type: "category",
      data: dates,
      ...axisLineDim,
    },
    yAxis: {
      type: "value",
      name: "attention",
      nameTextStyle: { color: CHART_COLORS.textFaint, fontSize: 10 },
      ...axisLineDim,
    },
    series: [
      {
        name: "Actual",
        type: "line",
        data: actual,
        symbol: "none",
        smooth: 0.2,
        lineStyle: { color: CHART_COLORS.accent, width: 2.5 },
        areaStyle: { color: "rgba(240,166,60,0.08)" },
        markLine: data.event_date
          ? {
              symbol: "none",
              silent: true,
              label: { formatter: "event", color: CHART_COLORS.textDim, fontSize: 10 },
              lineStyle: { color: CHART_COLORS.text, type: "dashed", width: 1 },
              data:
                eventIndex >= 0
                  ? [{ xAxis: eventIndex }]
                  : [{ xAxis: data.event_date }],
            }
          : undefined,
      },
      {
        name: "Counterfactual",
        type: "line",
        data: counterfactual,
        symbol: "none",
        smooth: 0.2,
        lineStyle: { color: CHART_COLORS.textDim, width: 1.75, type: "dashed" },
      },
    ],
  };

  return (
    <div>
      <ReactECharts option={option} style={{ height: 340, width: "100%" }} notMerge />
      {Array.isArray(data.spillover) && data.spillover.length > 0 ? (
        <div className="spillover-row">
          <div className="eyebrow" style={{ marginBottom: "0.5rem" }}>
            SPILLOVER
          </div>
          <div className="spillover-chips">
            {data.spillover.map((s) => (
              <span key={s.wikidata_id} className="chip mono">
                {s.label} {s.pct_lift >= 0 ? "+" : ""}
                {s.pct_lift.toFixed(1)}%
              </span>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
