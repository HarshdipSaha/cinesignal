import type { ReactNode } from "react";

export default function EmptyState({
  title,
  detail,
  action,
}: {
  title: string;
  detail?: string;
  action?: ReactNode;
}) {
  return (
    <div
      className="card"
      style={{
        padding: "2.5rem 2rem",
        textAlign: "center",
        color: "var(--text-dim)",
      }}
    >
      <div
        className="eyebrow"
        style={{ marginBottom: "0.6rem", color: "var(--text-faint)" }}
      >
        NO SIGNAL
      </div>
      <div style={{ fontFamily: "var(--font-display)", fontSize: "1.4rem", color: "var(--text)" }}>
        {title}
      </div>
      {detail ? (
        <p style={{ maxWidth: 440, margin: "0.75rem auto 0", fontSize: "0.88rem" }}>{detail}</p>
      ) : null}
      {action ? <div style={{ marginTop: "1.25rem" }}>{action}</div> : null}
    </div>
  );
}
