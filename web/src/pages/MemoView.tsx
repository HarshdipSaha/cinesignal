import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getMemo } from "../api/client";
import type {
  CampaignImpactChartData,
  LaunchWindowChartData,
  Memo,
  TitlePulseChartData,
} from "../api/types";
import Spinner from "../components/Spinner";
import EmptyState from "../components/EmptyState";
import StatCard from "../components/StatCard";
import VerdictBanner from "../components/VerdictBanner";
import CitationText from "../components/CitationText";
import EvidenceDrawer from "../components/EvidenceDrawer";
import CampaignImpactChart from "../components/charts/CampaignImpactChart";
import TitlePulseChart from "../components/charts/TitlePulseChart";
import LaunchWindowChart from "../components/charts/LaunchWindowChart";
import "./MemoView.css";

export default function MemoView() {
  const { memoId } = useParams<{ memoId: string }>();
  const [memo, setMemo] = useState<Memo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [drawerQueryId, setDrawerQueryId] = useState<string | null>(null);

  useEffect(() => {
    if (!memoId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    getMemo(memoId)
      .then((m) => {
        if (!cancelled) setMemo(m);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "failed to load memo");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [memoId]);

  if (loading) return <Spinner label="loading memo…" />;

  if (error || !memo) {
    return (
      <EmptyState
        title="Memo not found"
        detail={error ?? `No memo with id "${memoId}".`}
        action={
          <Link to="/" className="btn">
            back to search
          </Link>
        }
      />
    );
  }

  return (
    <div className="memo-page">
      <div className="memo-breadcrumb mono">
        <Link to="/">search</Link>
        <span>/</span>
        <span>{memo.entity?.label ?? memo.entity?.wikidata_id ?? "entity"}</span>
        <span>/</span>
        <span>{memo.playbook_id}</span>
      </div>

      <VerdictBanner verdict={memo.verdict} headline={memo.headline} />

      {memo.findings && memo.findings.length > 0 ? (
        <div className="memo-findings">
          {memo.findings.map((f) => (
            <div key={f.key} className="memo-finding-wrap">
              <StatCard label={f.label} value={formatValue(f.value)} unit={f.unit ?? undefined} />
              {f.query_id ? (
                <button
                  type="button"
                  className="memo-finding-evidence mono"
                  onClick={() => setDrawerQueryId(f.query_id!)}
                >
                  view evidence →
                </button>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      <div className="memo-chart card">
        <div className="eyebrow" style={{ marginBottom: "0.9rem" }}>
          CHART
        </div>
        {renderChart(memo)}
      </div>

      <div className="memo-sections">
        {(memo.sections ?? []).map((s, i) => (
          <div key={`${s.heading}-${i}`} className="memo-section">
            <h3 className="memo-section-heading">{s.heading}</h3>
            <CitationText
              body={s.body}
              queryIds={memo.query_ids ?? []}
              onCite={(qid) => setDrawerQueryId(qid)}
            />
          </div>
        ))}
      </div>

      {memo.validator_notes ? (
        <div className="memo-validator card mono">
          <span className="eyebrow">VALIDATOR</span> {memo.validator_notes}
        </div>
      ) : null}

      {drawerQueryId ? (
        <EvidenceDrawer queryId={drawerQueryId} onClose={() => setDrawerQueryId(null)} />
      ) : null}
    </div>
  );
}

function formatValue(value: number | string | null): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return value;
}

function renderChart(memo: Memo) {
  const data = memo.chart_data;
  if (!data || typeof data !== "object") {
    return (
      <EmptyState title="No chart data" detail="This memo did not return a chart_data payload." />
    );
  }
  switch (memo.playbook_id) {
    case "campaign_impact":
      return <CampaignImpactChart data={data as unknown as CampaignImpactChartData} />;
    case "title_pulse":
      return <TitlePulseChart data={data as unknown as TitlePulseChartData} />;
    case "launch_window":
      return <LaunchWindowChart data={data as unknown as LaunchWindowChartData} />;
    default:
      return (
        <EmptyState
          title="Unknown playbook chart"
          detail={`No chart renderer registered for playbook "${memo.playbook_id}".`}
        />
      );
  }
}
