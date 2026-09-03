import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, runPlaybook } from "../api/client";
import type { PlaybookId, PlaybookStreamEvent } from "../api/types";
import StepTimeline, { type TimelineEntry } from "../components/StepTimeline";
import "./PlaybookRun.css";

const PLAYBOOK_LABEL: Record<PlaybookId, string> = {
  title_pulse: "Title Pulse",
  campaign_impact: "Campaign Impact",
  launch_window: "Launch Window",
};

const VALID_PLAYBOOKS: PlaybookId[] = ["title_pulse", "campaign_impact", "launch_window"];

export default function PlaybookRun() {
  const { playbook, entityId } = useParams<{ playbook: string; entityId: string }>();
  const navigate = useNavigate();

  const isValidPlaybook = VALID_PLAYBOOKS.includes(playbook as PlaybookId);
  const needsForm = playbook === "campaign_impact";

  const [started, setStarted] = useState(!needsForm);
  const [eventDate, setEventDate] = useState("");
  const [cohortSize, setCohortSize] = useState("");

  const [entries, setEntries] = useState<TimelineEntry[]>([]);
  const [status, setStatus] = useState<"running" | "done" | "error">("running");
  const [errorMsg, setErrorMsg] = useState<string>("");
  const seqRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!isValidPlaybook || !entityId || !started) return;

    const controller = new AbortController();
    abortRef.current = controller;
    setEntries([]);
    setStatus("running");
    setErrorMsg("");

    const params: Record<string, unknown> = {};
    if (playbook === "campaign_impact") {
      params.event_date = eventDate;
      if (cohortSize.trim()) {
        const n = Number(cohortSize);
        if (!Number.isNaN(n)) params.cohort_size = n;
      }
    }

    function push(event: PlaybookStreamEvent) {
      seqRef.current += 1;
      setEntries((prev) => [...prev, { id: `${seqRef.current}`, event }]);
      if (event.type === "done" && event.memo_id) {
        setStatus("done");
        navigate(`/memo/${encodeURIComponent(event.memo_id)}`);
      } else if (event.type === "error") {
        setStatus("error");
        setErrorMsg(event.message ?? "the agent reported an error");
      }
    }

    runPlaybook(playbook as PlaybookId, { entity_id: entityId, params }, push, controller.signal).catch(
      (err) => {
        if (controller.signal.aborted) return;
        setStatus("error");
        setErrorMsg(
          err instanceof ApiError
            ? `${err.message} (status ${err.status})`
            : err instanceof Error
              ? err.message
              : "stream failed",
        );
      },
    );

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isValidPlaybook, entityId, playbook, started]);

  if (!isValidPlaybook || !entityId) {
    return (
      <div className="card" style={{ padding: "2rem" }}>
        Unknown playbook or missing entity. Head back to{" "}
        <Link to="/">search</Link>.
      </div>
    );
  }

  const label = PLAYBOOK_LABEL[playbook as PlaybookId];

  return (
    <div className="run-page">
      <div className="eyebrow">RUNNING PLAYBOOK</div>
      <h1 className="run-title">{label}</h1>
      <div className="run-entity mono">entity: {entityId}</div>

      {needsForm && !started ? (
        <form
          className="run-form card"
          onSubmit={(e) => {
            e.preventDefault();
            if (!eventDate) return;
            setStarted(true);
          }}
        >
          <p className="run-form-hint">
            Campaign Impact measures lift around a marketing beat — tell it when the beat
            happened.
          </p>
          <label className="run-form-field">
            <span className="eyebrow">EVENT DATE (required)</span>
            <input
              type="date"
              required
              value={eventDate}
              onChange={(e) => setEventDate(e.target.value)}
              className="mono"
            />
          </label>
          <label className="run-form-field">
            <span className="eyebrow">COHORT SIZE (optional)</span>
            <input
              type="number"
              min={1}
              placeholder="server default"
              value={cohortSize}
              onChange={(e) => setCohortSize(e.target.value)}
              className="mono"
            />
          </label>
          <button type="submit" className="btn btn-primary" disabled={!eventDate}>
            run campaign impact
          </button>
        </form>
      ) : (
        <>
          <div className="run-status-row">
            {status === "running" ? (
              <span className="chip chip-stage mono">
                <span className="run-pulse-dot" /> agent working
              </span>
            ) : null}
            {status === "done" ? <span className="chip chip-done mono">memo ready — redirecting…</span> : null}
            {status === "error" ? <span className="chip chip-error mono">run failed</span> : null}
          </div>

          {status === "error" ? (
            <div className="run-error card">
              <div className="eyebrow" style={{ marginBottom: "0.5rem", color: "var(--bad)" }}>
                ERROR
              </div>
              {errorMsg}
            </div>
          ) : null}

          <div className="run-timeline card">
            <StepTimeline entries={entries} />
          </div>
        </>
      )}
    </div>
  );
}
