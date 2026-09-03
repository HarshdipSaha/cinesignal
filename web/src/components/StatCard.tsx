import type { ReactNode } from "react";
import "./StatCard.css";

export default function StatCard({
  label,
  value,
  unit,
  accent = false,
  footnote,
}: {
  label: string;
  value: ReactNode;
  unit?: string | null;
  accent?: boolean;
  footnote?: ReactNode;
}) {
  return (
    <div className={`stat-card${accent ? " stat-card-accent" : ""}`}>
      <div className="stat-card-label eyebrow">{label}</div>
      <div className="stat-card-value">
        <span className="mono">{value}</span>
        {unit ? <span className="stat-card-unit mono">{unit}</span> : null}
      </div>
      {footnote ? <div className="stat-card-footnote mono">{footnote}</div> : null}
    </div>
  );
}
