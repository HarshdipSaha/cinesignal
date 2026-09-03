import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { getExplore } from "../api/client";
import type { ExploreResponse } from "../api/types";
import Spinner from "../components/Spinner";
import EmptyState from "../components/EmptyState";
import { CHART_COLORS, axisLineDim, baseOption } from "../components/charts/echartsBase";
import "./FanExplorer.css";

const MONTH_OPTIONS = [12, 24, 36, 60];

export default function FanExplorer() {
  const { entityId } = useParams<{ entityId: string }>();
  const [months, setMonths] = useState(36);
  const [data, setData] = useState<ExploreResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!entityId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    getExplore(entityId, months)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "failed to load");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [entityId, months]);

  if (loading) return <Spinner label="loading attention series…" />;

  if (error) {
    return (
      <EmptyState
        title="Could not load this entity"
        detail={error}
        action={
          <Link to="/" className="btn">
            back to search
          </Link>
        }
      />
    );
  }

  if (!data) return null;

  const series = Array.isArray(data.series) ? data.series : [];

  return (
    <div className="explore-page">
      <div className="memo-breadcrumb mono">
        <Link to="/">search</Link>
        <span>/</span>
        <span>fan explorer</span>
      </div>

      <div className="explore-head">
        <div>
          <div className="eyebrow">FAN EXPLORER</div>
          <h1 className="explore-title">{data.entity?.label ?? entityId}</h1>
          <div className="explore-meta mono">
            {[data.entity?.entity_type, ...(data.entity?.genres ?? [])].filter(Boolean).join(" · ")}
          </div>
        </div>
        <div className="explore-months">
          {MONTH_OPTIONS.map((m) => (
            <button
              key={m}
              type="button"
              className={`explore-month-btn mono${m === months ? " active" : ""}`}
              onClick={() => setMonths(m)}
            >
              {m}mo
            </button>
          ))}
        </div>
      </div>

      <div className="card explore-chart">
        {series.length === 0 ? (
          <EmptyState
            title="No attention data yet"
            detail="Ingestion for this entity hasn't landed rows yet — check back soon."
          />
        ) : (
          <ReactECharts option={buildOption(series)} style={{ height: 380, width: "100%" }} notMerge />
        )}
      </div>

      <p className="explore-share mono">
        shareable link — this page needs no agent run and no evidence chain.
      </p>
    </div>
  );
}

function buildOption(series: ExploreResponse["series"]): EChartsOption {
  return {
    ...baseOption,
    xAxis: {
      type: "category",
      data: series.map((p) => p.date),
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
        type: "line",
        data: series.map((p) => p.views),
        symbol: "none",
        smooth: 0.15,
        lineStyle: { color: CHART_COLORS.teal, width: 2.25 },
        areaStyle: { color: "rgba(73,201,190,0.08)" },
      },
    ],
  };
}
