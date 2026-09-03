import type { PlaybookStreamEvent } from "../api/types";
import "./StepTimeline.css";

export interface TimelineEntry {
  id: string;
  event: PlaybookStreamEvent;
}

export default function StepTimeline({ entries }: { entries: TimelineEntry[] }) {
  if (entries.length === 0) {
    return <div className="timeline-empty mono">waiting for the agent to check in…</div>;
  }

  return (
    <ol className="timeline">
      {entries.map(({ id, event }) => (
        <li key={id} className={`timeline-row timeline-row-${event.type}`}>
          <span className="timeline-rail" aria-hidden="true" />
          {renderEntry(event)}
        </li>
      ))}
    </ol>
  );
}

function renderEntry(event: PlaybookStreamEvent) {
  switch (event.type) {
    case "stage":
      return (
        <div className="timeline-content">
          <div className="timeline-title">
            <span className="chip chip-stage mono">STAGE</span>
            <span>{event.stage ?? "update"}</span>
          </div>
          {event.message ? <div className="timeline-detail">{event.message}</div> : null}
          {event.headline ? (
            <div className="timeline-detail timeline-detail-strong">{event.headline}</div>
          ) : null}
        </div>
      );
    case "step": {
      const hasError = Boolean(event.error);
      return (
        <div className="timeline-content">
          <div className="timeline-title">
            <span className={`chip mono ${hasError ? "chip-error" : "chip-step"}`}>
              {hasError ? "FAILED" : "STEP"}
            </span>
            <span>{event.title ?? event.step_id ?? "step"}</span>
          </div>
          <div className="timeline-meta mono">
            {event.query_id ? <span>{event.query_id}</span> : null}
            {event.row_count != null ? <span>{event.row_count.toLocaleString()} rows</span> : null}
            {event.elapsed_ms != null ? <span>{event.elapsed_ms.toLocaleString()} ms</span> : null}
          </div>
          {hasError ? <div className="timeline-detail timeline-detail-error">{event.error}</div> : null}
        </div>
      );
    }
    case "error":
      return (
        <div className="timeline-content">
          <div className="timeline-title">
            <span className="chip chip-error mono">ERROR</span>
          </div>
          <div className="timeline-detail timeline-detail-error">{event.message ?? "unknown error"}</div>
        </div>
      );
    case "done":
      return (
        <div className="timeline-content">
          <div className="timeline-title">
            <span className="chip chip-done mono">DONE</span>
            <span>memo ready</span>
          </div>
          {event.memo_id ? (
            <div className="timeline-meta mono">
              <span>{event.memo_id}</span>
              <span>{event.validated ? "validated" : "unvalidated"}</span>
            </div>
          ) : null}
        </div>
      );
    default:
      return null;
  }
}
