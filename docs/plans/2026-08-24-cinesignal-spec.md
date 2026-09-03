# CineSignal — Detailed Build Spec

> Superpowers `writing-plans` format: assumes a skilled engineer with **zero context**.
> Product definition: `../ideation/06-BEST-IDEA.md`. Date: 2026-08-24.
> Hard deadline: **Sept 9, 2026, 2:00 PM PT** (Sept 10, 2:30 AM IST). ~16 days.
> **STOP-LINE per user instruction: this spec is the last artifact of the ideation phase.
> No implementation until the user green-lights the build.**

---

## 1. Goal & Non-Goals

**Goal:** Ship a hosted, judged-ready web product where a user picks any film/franchise/person,
runs one of 3 deterministic analyst playbooks, and receives a decision memo whose every number is
backed by live ClickHouse queries over ≥300M (target ≥1B) real Wikipedia-pageview rows joined to
the IMDb catalog — orchestrated by a google-adk / Gemini multi-agent system calling the official
`mcp-clickhouse` MCP server at runtime.

**Non-goals (explicitly cut — YAGNI):** user accounts/auth, payments, real-time streaming
ingestion (roadmap slide only), freeform text-to-SQL chat, mobile apps, admin panels,
multi-tenancy, TalentRadar/Seismograph playbooks.

## 2. Technology Stack

| Layer | Choice | Why |
|---|---|---|
| Warehouse | **ClickHouse Cloud** (trial; self-hosted Docker fallback) | Track requirement; scale story |
| Agent↔DB | **`mcp-clickhouse`** (official MCP server), read-only creds | Track's checked artifact |
| Agents | **google-adk** (Python) on **Vertex AI Gemini** (`gemini-2.5-flash` for resolution/validation, `gemini-2.5-pro` for memo synthesis — pin whatever's current at build time) via `google-genai` | Rules: accepted packages, runtime-called |
| Backend | Python 3.12, **FastAPI**, SSE for playbook progress | Solo-dev speed |
| Frontend | **React + Vite + ECharts** (single SPA, dark "studio" theme) | Judging criterion: complete product feel |
| Hosting | **Cloud Run** (single container: FastAPI serves SPA + API; MCP server as subprocess) | Google Cloud runtime requirement |
| Secrets | **Secret Manager** (ClickHouse creds, nothing else) | Rules resources push this |
| Ingestion | Python scripts + ClickHouse `url()`/`s3()` table functions; run from a GCE spot VM or local machine | One-time batch |
| Repo | GitHub public, **Apache-2.0**, licence set in About | Stage One pass/fail |

## 3. Architecture

```
┌──────────────┐   ┌───────────────────────────── Cloud Run ─────────────────────────────┐
│ React SPA    │──▶│ FastAPI  /api/resolve  /api/playbooks/{id}/run (SSE)  /api/memo/{id} │
│ (ECharts)    │   │            │                                                         │
└──────────────┘   │            ▼                                                         │
                   │   google-adk agent tree (Vertex AI Gemini via google-genai)          │
                   │   Orchestrator (SequentialAgent)                                     │
                   │    ├─ EntityResolver        (flash: name → wikidata_id/tconst)       │
                   │    ├─ PlaybookRunner        (deterministic: N templated steps)       │
                   │    │    └─ tools = MCPToolset ──▶ mcp-clickhouse (stdio subprocess)  │
                   │    ├─ Interpreter           (pro: structured findings from JSON)     │
                   │    ├─ MemoComposer          (pro: memo w/ [qN] citations)            │
                   │    └─ NumberValidator       (flash: every numeral ∈ result sets?)    │
                   └───────────────────────────────────┬──────────────────────────────────┘
                                                       ▼
                                    ClickHouse Cloud  (attention warehouse)
                                    pageviews_daily ⋈ entities ⋈ imdb_*  + MVs
```

**Determinism contract:** SQL lives in `playbooks/*.yaml` as versioned parameterized templates.
Gemini chooses *parameters and prose*, never SQL text. A memo records (playbook_version,
params, query_ids) → re-run reproduces identical numbers.

## 4. Data Model (ClickHouse DDL sketch)

```sql
CREATE TABLE pageviews_daily (
  page_id UInt64, project LowCardinality(String),  -- 'en.wikipedia', 'ja.wikipedia', …
  date Date, views UInt32
) ENGINE = MergeTree PARTITION BY toYYYYMM(date) ORDER BY (page_id, date);

CREATE TABLE entities (            -- the film universe join spine
  wikidata_id String, page_id UInt64, project LowCardinality(String),
  page_title String, entity_type Enum8('film'=1,'series'=2,'person'=3,'franchise'=4),
  tconst String DEFAULT '', nconst String DEFAULT ''   -- IMDb ids via Wikidata P345/P4947
) ENGINE = ReplacingMergeTree ORDER BY (wikidata_id, project);

-- imdb_titles / imdb_ratings / imdb_principals / imdb_crew: loaded verbatim from IMDb TSVs.

CREATE MATERIALIZED VIEW entity_attention_daily     -- rollup powering every playbook
ENGINE = SummingMergeTree ORDER BY (wikidata_id, project, date)
AS SELECT e.wikidata_id, p.project, p.date, sum(p.views) AS views
FROM pageviews_daily p JOIN entities e USING (page_id, project)
GROUP BY e.wikidata_id, p.project, p.date;
```

**Ingestion scope ladder** (start bottom, climb as time allows):
floor = en.wikipedia, 12 months, film-universe pages only (≈300M rows) →
target = +5 major languages, 36 months (≈1–2B rows) → stretch = all languages.

## 5. The Three Playbooks (deterministic step lists)

**P1 Title Pulse:** resolve → q1 daily series (36mo) → q2 genre-cohort percentile per month →
q3 top-10 anomaly days (z-score on Δviews) → q4 momentum (28d vs prior 28d) → interpret → memo.

**P2 Campaign Impact ⭐:** resolve + event date (user-picked or from q3 anomalies) →
q1 event-window series (−60d, +30d) → q2 counterfactual = median trajectory of 50 same-genre
cohort titles date-aligned, scaled to pre-window baseline → q3 abnormal lift = Σ(actual −
counterfactual) over +14d, in views & attention-hours → q4 half-life of the spike →
q5 spillover: same window on cast/franchise entity pages → interpret → memo with verdict
(UNDERPERFORMED / IN-LINE / BREAKOUT vs cohort event distribution).

**P3 Launch Window:** target quarter → q1 competition density per candidate weekend (titles with
release dates ± attention mass) → q2 seasonal genre demand curve (5y same-genre weekly index) →
q3 candidate ranking table → interpret → memo with top-3 windows + evidence.

*(Stretch P4 Localization Priority: per-project over/under-index vs global share → ranked territories.)*

## 6. API Surface

```
GET  /api/resolve?q=dune          → [{wikidata_id, label, type, year, tconst}]
POST /api/playbooks/{p1|p2|p3}/run {entity_id, params}  → SSE: step events → memo_id
GET  /api/memo/{memo_id}          → memo JSON (sections, charts data, evidence chain)
GET  /api/evidence/{query_id}     → {sql, params, rows, elapsed_ms, rows_scanned}
GET  /api/explore/{entity_id}     → public fan-explorer series (no agent, direct query)
```
`rows_scanned` and `elapsed_ms` are displayed in the UI on purpose — they ARE the demo.

## 7. Frontend Pages

1. **Home/Search** — entity search, marquee stat ("1.8B attention events indexed").
2. **Playbook Run** — live step timeline (agent progress via SSE), then memo view: verdict
   banner, event-study chart (actual vs counterfactual band), stat cards, prose with `[qN]`
   citation chips → click opens Evidence drawer (SQL + rows + scan stats).
3. **Fan Explorer** — public attention chart for any entity, shareable URL.

## 8. Phased Plan (16 days, day-8 descope gate)

> Each phase ends with a **verification gate** — do not proceed on red.
> Parallel lanes: ingestion (I) can run while agent/app (A) is coded.

**Phase 0 — Foundations (Aug 25–26)**
- [ ] GCP project; request $100 credit form (**deadline Aug 31 — do first**); enable Vertex AI
- [ ] ClickHouse Cloud trial (start ~Aug 26 so trial spans submission); create DB + read-only agent user
- [ ] GitHub repo `cinesignal`, Apache-2.0 LICENSE at root, licence visible in About
- [ ] Walking skeleton: `google-adk` hello-agent + `MCPToolset` → `mcp-clickhouse` → `SELECT 1` on the cluster; deploy skeleton to Cloud Run
- ✅ **Gate 0:** agent answers a question via MCP against ClickHouse Cloud, from a Cloud Run URL. *(De-risks track's pass/fail artery on day 2.)*

**Phase 1 — Warehouse (Aug 26–31, lane I)**
- [ ] Load IMDb TSVs (7 tables) — script `ingest/imdb.py`
- [ ] Build `entities` spine from Wikidata (P345/P4947/P31 filter: films, series, humans-with-film-occupations, franchises) — `ingest/wikidata.py`
- [ ] Pageviews: download Wikimedia per-article daily dumps, filter to spine page set, insert — `ingest/pageviews.py` (checkpointed, resumable); floor scope first, then widen
- [ ] Create `entity_attention_daily` MV; spot-check 5 known titles against Wikipedia's own pageview tool
- ✅ **Gate 1:** ≥300M rows; known-title sanity checks within ±2%; p95 playbook-shaped query < 1s

**Phase 2 — Engine + P2 flagship (Aug 28–Sept 3, lane A)**
- [ ] `playbooks/` YAML template format + loader + param binding + query-id logging
- [ ] Agent tree: EntityResolver, PlaybookRunner (steps→MCP), Interpreter, MemoComposer (structured output w/ `[qN]`), NumberValidator (reject memo if any numeral ∉ results)
- [ ] P2 Campaign Impact end-to-end in CLI; golden test: same input → identical numbers twice
- ✅ **Gate 2:** P2 memo for a real 2026 tentpole trailer is correct, cited, reproducible

**Phase 3 — Product (Sept 1–5)**
- [ ] FastAPI endpoints + SSE; SPA: search, run timeline, memo view, evidence drawer, fan explorer
- [ ] P1 and P3 playbooks (each ≈1 day on the shared engine)
- [ ] **Sept 1 = Day 8 DESCOPE GATE:** if Gate 2 not green → cut P1/P3 + explorer, ship Campaign-Impact-only (Finalist B, per `04-round2-evaluation.md`)
- ✅ **Gate 3:** full flow on Cloud Run URL, cold-start < 5s, demo entities pre-cached

**Phase 4 — Polish & Submission (Sept 5–9)**
- [ ] README: architecture diagram, exact run instructions, dataset licences, **explicit pointers to runtime `google-adk`/`google-genai` and `mcp-clickhouse` usage in code** (Stage One is checked, possibly by automated tools)
- [ ] Record 3-min demo video per script in `06-BEST-IDEA.md`; upload YouTube public; backup take
- [ ] Devpost form: track=ClickHouse, hosted URL, repo URL, video URL, text description (features, stack, findings/learnings)
- [ ] Dry-run Stage One as a hostile judge: fresh clone, follow README, everything works
- [ ] **Submit Sept 8 (24h buffer). Never Sept 9.**

## 9. Testing Approach

- **Golden memos:** 3 fixture entities; playbook runs must reproduce stored numbers exactly (determinism is a *feature under test*).
- **SQL template tests:** each template against a 1M-row local Docker ClickHouse fixture.
- **Validator tests:** inject a hallucinated numeral → memo must be rejected.
- **Latency budget test:** all P2 queries < 1s p95 on the cloud cluster.
- Skipped consciously: UI unit tests (manual pass), load tests (single-judge audience).

## 10. Risk Register (from `05-round3-stress-test.md`, with owners-in-time)

| Risk | Trigger date | Response |
|---|---|---|
| Ingestion slips | Gate 1 red on Aug 31 | Stay at floor scope (300M rows) — demo claim adjusts, nothing else changes |
| ADK↔MCP friction | Gate 0 red on Aug 26 | Fall back to `clickhouse-connect` behind a thin tool + keep MCP for the resolver path — **but MCP must remain in the runtime path (track rule); escalate to user if truly blocked** |
| Trial credits die pre-judging | Sept | Self-host ClickHouse on GCE/Docker (rules allow); dataset re-load scripted |
| Gemini quota/costs | Any | Flash-first routing; memo cache; $100 credit + free tier |

## 11. File Layout (target repo)

```
cinesignal/
  LICENSE  README.md  Dockerfile  cloudbuild.yaml
  ingest/{imdb.py, wikidata.py, pageviews.py, ddl.sql}
  playbooks/{title_pulse.yaml, campaign_impact.yaml, launch_window.yaml}
  agent/{tree.py, resolver.py, runner.py, interpreter.py, composer.py, validator.py, mcp.py}
  api/{main.py, sse.py, memos.py}
  web/  (Vite SPA)
  tests/{test_templates.py, test_golden_memos.py, test_validator.py}
```

---

**Status: SPEC COMPLETE — ideation phase ends here per user instruction ("stop after BEST IDEA").**
Build begins only on explicit go-ahead. First actions on go: Phase 0 checklist, top to bottom.
