export default function Spinner({ label }: { label?: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "0.75rem",
        padding: "2rem",
        color: "var(--text-dim)",
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: 16,
          height: 16,
          borderRadius: "50%",
          border: "2px solid var(--border)",
          borderTopColor: "var(--accent)",
          animation: "spin 0.8s linear infinite",
          flexShrink: 0,
        }}
      />
      <span className="mono" style={{ fontSize: "0.78rem", letterSpacing: "0.06em" }}>
        {label ?? "loading…"}
      </span>
    </div>
  );
}
