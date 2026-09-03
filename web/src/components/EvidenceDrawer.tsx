import { useEffect, useState } from "react";
import { getEvidence } from "../api/client";
import type { EvidenceResponse } from "../api/types";
import Spinner from "./Spinner";
import "./EvidenceDrawer.css";

const ROW_CAP = 50;

export default function EvidenceDrawer({
  queryId,
  onClose,
}: {
  queryId: string;
  onClose: () => void;
}) {
  const [data, setData] = useState<EvidenceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setData(null);
    getEvidence(queryId)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "failed to load evidence");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [queryId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const columns = data?.rows?.[0] ? Object.keys(data.rows[0]) : [];
  const shownRows = data?.rows?.slice(0, ROW_CAP) ?? [];
  const hiddenCount = data ? Math.max(0, (data.row_count ?? data.rows.length) - shownRows.length) : 0;

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <aside
        className="drawer"
        role="dialog"
        aria-label="Evidence detail"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="drawer-head">
          <div>
            <div className="eyebrow">EVIDENCE</div>
            <div className="mono drawer-query-id">{queryId}</div>
          </div>
          <button type="button" className="btn drawer-close" onClick={onClose}>
            close ✕
          </button>
        </div>

        {loading ? <Spinner label="pulling query trace…" /> : null}

        {error ? (
          <div className="drawer-error">
            Could not load evidence for <span className="mono">{queryId}</span>: {error}
          </div>
        ) : null}

        {data ? (
          <div className="drawer-body">
            <div className="drawer-proof-row">
              <div className="proof-chip proof-chip-hero">
                <span className="eyebrow">ELAPSED</span>
                <span className="mono proof-chip-value">
                  {data.elapsed_ms != null ? `${data.elapsed_ms.toLocaleString()} ms` : "—"}
                </span>
              </div>
              <div className="proof-chip proof-chip-hero">
                <span className="eyebrow">ROWS SCANNED</span>
                <span className="mono proof-chip-value">
                  {data.rows_scanned != null ? data.rows_scanned.toLocaleString() : "—"}
                </span>
              </div>
              <div className="proof-chip">
                <span className="eyebrow">ROWS RETURNED</span>
                <span className="mono proof-chip-value">{data.row_count ?? data.rows.length}</span>
              </div>
            </div>

            <div className="drawer-section-label eyebrow">SQL</div>
            <pre className="drawer-sql mono">{data.sql}</pre>

            {data.params && Object.keys(data.params).length > 0 ? (
              <>
                <div className="drawer-section-label eyebrow">PARAMS</div>
                <pre className="drawer-sql mono">{JSON.stringify(data.params, null, 2)}</pre>
              </>
            ) : null}

            <div className="drawer-section-label eyebrow">RESULT ROWS</div>
            {shownRows.length === 0 ? (
              <div className="drawer-empty-rows mono">no rows returned</div>
            ) : (
              <div className="drawer-table-wrap">
                <table className="drawer-table mono">
                  <thead>
                    <tr>
                      {columns.map((col) => (
                        <th key={col}>{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {shownRows.map((row, i) => (
                      <tr key={i}>
                        {columns.map((col) => (
                          <td key={col}>{formatCell(row[col])}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {hiddenCount > 0 ? (
              <div className="drawer-more-rows mono">+ {hiddenCount.toLocaleString()} more rows</div>
            ) : null}
          </div>
        ) : null}
      </aside>
    </div>
  );
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
