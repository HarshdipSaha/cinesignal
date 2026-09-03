import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { resolveEntity } from "../api/client";
import type { EntitySummary } from "../api/types";
import Spinner from "../components/Spinner";
import EmptyState from "../components/EmptyState";
import "./Home.css";

// Static placeholder marquee numbers — swap these for real figures once a
// /api/summary-style endpoint exists. Kept here, front and center, on purpose.
const MARQUEE_STATS = [
  { label: "attention events indexed", value: "300M+" },
  { label: "titles & people tracked", value: "48,000+" },
  { label: "years of pageview history", value: "9" },
  { label: "playbooks on call", value: "3" },
];

const PLAYBOOKS: {
  id: "title_pulse" | "campaign_impact" | "launch_window";
  name: string;
  tagline: string;
  featured?: boolean;
}[] = [
  {
    id: "title_pulse",
    name: "Title Pulse",
    tagline: "Trend and anomaly-detect a single title's attention over time.",
  },
  {
    id: "campaign_impact",
    name: "Campaign Impact",
    tagline: "Actual-vs-counterfactual lift from a marketing beat, with spillover.",
    featured: true,
  },
  {
    id: "launch_window",
    name: "Launch Window",
    tagline: "Rank open weekends in a quarter by competitive attention pressure.",
  },
];

type Phase = "idle" | "loading" | "resolved" | "disambiguate" | "empty" | "error";

export default function Home() {
  const [query, setQuery] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [entity, setEntity] = useState<EntitySummary | null>(null);
  const [candidates, setCandidates] = useState<EntitySummary[]>([]);
  const [errorMsg, setErrorMsg] = useState<string>("");

  async function handleSearch(e: FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    setPhase("loading");
    setErrorMsg("");
    try {
      const res = await resolveEntity(q);
      if (res.best_match) {
        setEntity(res.best_match);
        setPhase("resolved");
      } else if (res.candidates && res.candidates.length > 0) {
        setCandidates(res.candidates);
        setPhase("disambiguate");
      } else {
        setPhase("empty");
      }
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "search failed");
      setPhase("error");
    }
  }

  function pickCandidate(c: EntitySummary) {
    setEntity(c);
    setPhase("resolved");
  }

  function resetSearch() {
    setPhase("idle");
    setEntity(null);
    setCandidates([]);
  }

  return (
    <div className="home">
      <section className="hero">
        <div className="eyebrow">SCREENING ROOM</div>
        <h1 className="hero-title">
          Point it at a title.
          <br />
          Get the <span className="hero-title-accent">signal</span>, cited.
        </h1>
        <p className="hero-sub">
          CineSignal runs evidence-backed playbooks over box-office attention data and
          shows its work — every number traces back to a query you can inspect.
        </p>

        <form className="search-form" onSubmit={handleSearch}>
          <input
            className="search-input mono"
            type="text"
            placeholder="Search a film, series, franchise, or person…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
          />
          <button type="submit" className="btn btn-primary" disabled={!query.trim()}>
            Resolve
          </button>
        </form>

        <div className="marquee">
          {MARQUEE_STATS.map((s) => (
            <div className="marquee-stat" key={s.label}>
              <div className="marquee-stat-value mono">{s.value}</div>
              <div className="marquee-stat-label eyebrow">{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="results">
        {phase === "loading" ? <Spinner label="resolving entity…" /> : null}

        {phase === "error" ? (
          <EmptyState
            title="Resolve failed"
            detail={errorMsg}
            action={
              <button type="button" className="btn" onClick={resetSearch}>
                try again
              </button>
            }
          />
        ) : null}

        {phase === "empty" ? (
          <EmptyState
            title={`No matches for “${query}”`}
            detail="The entity index may still be building, or try a different spelling."
          />
        ) : null}

        {phase === "disambiguate" ? (
          <div className="disambig">
            <div className="eyebrow" style={{ marginBottom: "0.75rem" }}>
              DID YOU MEAN
            </div>
            <ul className="disambig-list">
              {candidates.map((c) => (
                <li key={c.wikidata_id}>
                  <button type="button" className="disambig-item" onClick={() => pickCandidate(c)}>
                    <span className="disambig-item-label">{c.label}</span>
                    <span className="disambig-item-meta mono">
                      {[c.entity_type, c.year].filter(Boolean).join(" · ") || c.wikidata_id}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {phase === "resolved" && entity ? (
          <div className="entity-panel">
            <div className="entity-panel-head">
              <div>
                <div className="eyebrow">RESOLVED</div>
                <h2 className="entity-panel-name">{entity.label}</h2>
                <div className="entity-panel-meta mono">
                  {[entity.entity_type, entity.year].filter(Boolean).join(" · ")}
                  {"  "}
                  {entity.wikidata_id}
                </div>
              </div>
              <div className="entity-panel-actions">
                <Link to={`/explore/${encodeURIComponent(entity.wikidata_id)}`} className="btn">
                  browse attention data
                </Link>
                <button type="button" className="btn" onClick={resetSearch}>
                  new search
                </button>
              </div>
            </div>

            <div className="eyebrow" style={{ margin: "1.5rem 0 0.75rem" }}>
              RUN A PLAYBOOK
            </div>
            <div className="playbook-grid">
              {PLAYBOOKS.map((pb) => (
                <Link
                  key={pb.id}
                  to={`/run/${pb.id}/${encodeURIComponent(entity.wikidata_id)}`}
                  className={`playbook-card${pb.featured ? " playbook-card-featured" : ""}`}
                >
                  <div className="playbook-card-name">
                    {pb.name}
                    {pb.featured ? <span className="playbook-star"> ★</span> : null}
                  </div>
                  <p className="playbook-card-tagline">{pb.tagline}</p>
                  <span className="playbook-card-cta mono">run playbook →</span>
                </Link>
              ))}
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}
