import type { Verdict } from "../api/types";
import "./VerdictBanner.css";

const VERDICT_TONE: Record<string, "good" | "bad" | "neutral" | "dim"> = {
  BREAKOUT: "good",
  RISING: "good",
  IN_LINE: "neutral",
  STABLE: "neutral",
  RANKED: "neutral",
  UNDERPERFORMED: "bad",
  DECLINING: "bad",
  INSUFFICIENT_DATA: "dim",
};

export function verdictTone(verdict: Verdict): "good" | "bad" | "neutral" | "dim" {
  return VERDICT_TONE[verdict] ?? "dim";
}

export default function VerdictBanner({
  verdict,
  headline,
}: {
  verdict: Verdict;
  headline: string;
}) {
  const tone = verdictTone(verdict);
  return (
    <div className={`verdict verdict-${tone}`}>
      <span className="verdict-badge mono">{String(verdict).replace(/_/g, " ")}</span>
      <h1 className="verdict-headline">{headline}</h1>
    </div>
  );
}
