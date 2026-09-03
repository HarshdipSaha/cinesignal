import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import type { TitlePulseChartData } from "../../api/types";
import EmptyState from "../EmptyState";
import { CHART_COLORS, axisLineDim, baseOption } from "./echartsBase";

export default function TitlePulseChart({ data }: { data: TitlePulseChartData }) {
  const dates = Array.isArray(data.dates) ? data.dates : [];
  const views = Array.isArray(data.views) ? data.views : [];
  const anomalies = Array.isArray(data.anomaly_days) ? data.anomaly_days : [];
  const monthly = Array.isArray(data.monthly_percentile) ? data.monthly_percentile : [];

  if (dates.length === 0 || views.length === 0) {
    return (
      <EmptyState
        title="No attention series yet"
        detail="This memo didn't come back with a views-over-time series to chart."
      />
    );
  }

  const anomalyPoints = anomalies
    .map((a) => {
      const idx = dates.indexOf(a.date);
      if (idx === -1) return null;
      return [idx, views[idx], a] as const;
    })
    .filter((p): p is readonly [number, number, (typeof anomalies)[number]] => p !== null);

  const option: EChartsOption = {
    ...baseOption,
    xAxis: {
      type: "category",
      data: dates,
      ...axisLineDim,
    },
    yAxis: {
      type: "value",
      name: "views",
      nameTextStyle: { color: CHART_COLORS.textFaint, fontSize: 10 },
      ...axisLineDim,
    },
    series: [
      {
        name: "Views",
        type: "line",
        data: views,
        symbol: "none",
        smooth: 0.15,
        lineStyle: { color: CHART_COLORS.accent, width: 2.25 },
        areaStyle: { color: "rgba(240,166,60,0.07)" },
      },
      {
        name: "Anomaly",
        type: "scatter",
        data: anomalyPoints.map(([idx, v]) => [idx, v]),
        symbolSize: 11,
        itemStyle: {
          color: CHART_COLORS.bad,
          borderColor: "#1a0507",
          borderWidth: 1.5,
        },
        tooltip: {
          formatter: (params: unknown) => {
            const p = params as { dataIndex: number };
            const match = anomalyPoints.find(([idx]) => idx === p.dataIndex);
            if (!match) return "";
            const [, v, a] = match;
            return `${a.date}<br/>views: ${v.toLocaleString()}<br/>δ: ${a.delta_views ?? "—"}  z: ${
              a.z_score ?? "—"
            }`;
          },
        },
      },
    ],
  };

  return (
    <div>
      <ReactECharts option={option} style={{ height: 320, width: "100%" }} notMerge />
      {monthly.length > 0 ? (
        <div className="pulse-secondary">
          <div className="eyebrow" style={{ margin: "1rem 0 0.5rem" }}>
            MONTHLY PERCENTILE TREND
          </div>
          <ReactECharts
            option={{
              ...baseOption,
              grid: { left: 40, right: 16, top: 12, bottom: 28, containLabel: true },
              xAxis: { type: "category", data: monthly.map((m) => m.month), ...axisLineDim },
              yAxis: {
                type: "value",
                min: 0,
                max: 100,
                ...axisLineDim,
              },
              series: [
                {
                  type: "line",
                  data: monthly.map((m) => m.percentile),
                  symbol: "circle",
                  symbolSize: 6,
                  lineStyle: { color: CHART_COLORS.teal, width: 2 },
                  itemStyle: { color: CHART_COLORS.teal },
                },
              ],
            }}
            style={{ height: 160, width: "100%" }}
            notMerge
          />
        </div>
      ) : null}
    </div>
  );
}
