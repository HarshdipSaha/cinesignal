import type { EChartsOption } from "echarts";

// Shared studio-dark ECharts defaults. Individual charts spread this in and
// override series/axes as needed.
export const CHART_COLORS = {
  accent: "#f0a63c",
  accentStrong: "#ffc773",
  teal: "#49c9be",
  good: "#5fd68a",
  bad: "#f2586b",
  neutral: "#9aa0ff",
  text: "#eeece4",
  textDim: "#8d8d97",
  textFaint: "#5b5b64",
  border: "#26262c",
  grid: "#1c1c21",
};

export const baseOption: EChartsOption = {
  textStyle: {
    fontFamily: "IBM Plex Mono, monospace",
    color: CHART_COLORS.textDim,
  },
  backgroundColor: "transparent",
  tooltip: {
    trigger: "axis",
    backgroundColor: "#111114",
    borderColor: CHART_COLORS.border,
    textStyle: { color: CHART_COLORS.text, fontFamily: "IBM Plex Mono, monospace", fontSize: 12 },
    axisPointer: {
      lineStyle: { color: CHART_COLORS.border },
    },
  },
  grid: {
    left: 48,
    right: 24,
    top: 28,
    bottom: 40,
    containLabel: true,
  },
};

export const axisLineDim = {
  axisLine: { lineStyle: { color: CHART_COLORS.border } },
  axisLabel: { color: CHART_COLORS.textFaint, fontSize: 11 },
  splitLine: { lineStyle: { color: CHART_COLORS.grid } },
};
