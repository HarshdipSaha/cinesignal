# 05 — Round 3: Stress Test (Scale Game + Risk Kill-List)

> Skills applied: `scale-game`, plus the evaluator's red-flag checklist and a judge-criteria map.
> Subject: **CineSignal** (winner of Round 2). Purpose: try to kill it before committing 16 days.

## Scale Game

| Dimension | At demo scale | At 1000x | What breaks | Design response |
|---|---|---|---|---|
| Rows | ~1–2B pageview rows (3 yrs, film universe) | Full wikistat firehose, all pages, 10+ yrs (~1T) | Raw per-page scans get slow; storage cost | Partition by month, `ORDER BY (page_id, date)`; daily materialized rollups per entity; demo claim stays honest: "this exact schema is what ClickHouse runs at trillion-row scale" |
| Entities | 1 title queried | Studio slate: 10k titles nightly batch memos | Playbook fan-out; MCP session limits | Playbooks are stateless SQL templates → trivially batchable server-side; memo queue |
| Users | 1 judge | 1,000 analysts concurrently | Gemini quota, not ClickHouse | Cache memo results keyed by (playbook, entity, window); ClickHouse handles concurrent reads natively |
| Freshness | Daily dump lag (~1 day) | Real-time (hourly stream) | Ingestion loop becomes a service | Wikimedia publishes hourly files → incremental insert job; already designed as append-only, so streaming is an ops change, not a schema change |
| Events | Trailer dates entered manually for demo titles | Auto-detected for all titles | Event detection quality | Anomaly-detection SQL (z-score on daily deltas) already powers Title Pulse's "top events" — reuse it |
| Smaller (1/1000x) | — | 1 indie film, 1 page | Cohort baselines too thin | Fall back to genre-median baseline; state confidence in the memo |

**Survives.** Nothing structural breaks in either direction; every response is a config/ops change,
not a redesign. This is the "judges LOVE a scalability story" slide, with receipts.

## Risk Kill-List (attempted murder of the idea)

| # | Risk | Severity | Mitigation | Kills it? |
|---|---|---|---|---|
| 1 | **Ingestion week overruns** (dump volume, parsing, Wikidata joins) | HIGH | Ingest via ClickHouse-native `url()`/`s3()` table functions where possible; start with 12 months + top ~500k film-universe pages (still >300M real rows), widen window as time allows; ingestion runs while agent code is written in parallel | No — degrades scale, demo still real |
| 2 | "Pageviews are just Google Trends" judge objection | MED | Trends is relative/sampled/rate-limited with no raw access; we have absolute counts, per-language splits, full SQL over raw rows, joinable to the IMDb graph — none of which Trends offers. Plus academic validation (Mestyán et al. 2013). Pre-write this rebuttal into the FAQ section of the memo UI | No |
| 3 | ClickHouse Cloud trial expires/credits insufficient | MED | Trial gives ~$300/30 days — start the trial ~Aug 26 so it spans judging period start; keep a `docker compose` self-hosted fallback (rules allow self-hosted); pause compute when idle | No |
| 4 | MCP integration friction with ADK | MED | `mcp-clickhouse` is official and documented; ADK `MCPToolset` supports stdio/SSE servers. Fallback within rules: run MCP server alongside backend on Cloud Run. Prototype this in the first 2 days (walking skeleton) precisely because it's the track's pass/fail artery | No |
| 5 | Gemini hallucinates numbers into memos | MED | Numbers are injected from SQL results as structured JSON; memo template forces citations `[q3]` per claim; a validator agent cross-checks every numeral in prose against the result set before rendering | No |
| 6 | Entity ambiguity ("Batman" → 40 pages) | LOW | Resolution step surfaces candidates (Wikidata labels + IMDb year/type); user confirms; demo uses pre-resolved entities | No |
| 7 | Wikimedia licensing | LOW | Pageview data is CC0; IMDb datasets are free for non-commercial — hackathon OK; state licences in README | No |
| 8 | Someone else builds the same thing | LOW | The moat is the ingestion + methodology + determinism; a weekend text-to-SQL clone will look categorically different in front of ClickHouse engineers | No |

**Red-flag check (evaluator):** score 48 ≥ 40 ✓ · Feasibility 7 ≥ 5 ✓ · Demo 9 ≥ 5 ✓ ·
Novelty 7 ≥ 4 ✓. No abandon conditions triggered.

## Judge-Criteria Map (the four official Stage-Two criteria)

| Criterion | How CineSignal answers it |
|---|---|
| **Technological Implementation** | google-adk multi-agent tree (Sequential root + Parallel research fan-out) on Vertex AI Gemini; official `mcp-clickhouse` as the agent's data limb; billions of real rows; materialized-view rollups; Cloud Run + Secret Manager; every Google/Partner service is load-bearing, none decorative |
| **Design** | A complete product: entity search → playbook run with live progress → decision memo with evidence chain → export/share; plus a public fan-explorer page. Not a notebook, not a chat box |
| **Potential Impact** | Named audience (studio marketing/distribution analysts), quantified pain ($100M+ tentpole campaigns with weak attribution; localization triage), validated signal (peer-reviewed proxy), free-data economics vs. paid social-listening vendors |
| **Quality of the Idea** | Non-obvious on three axes: fans-as-sensor-network inversion, finance event-study collision, and memos-not-chat determinism. Demonstrates real understanding of how studio decisions actually get made |

## Final Verdict

**CineSignal survives all three rounds. Declared BEST IDEA.**
Runner-up (descope line): CampaignImpact standalone, activated only at the day-8 gate.

→ Full concept + pitch: `06-BEST-IDEA.md` · Build spec: `../plans/2026-08-24-cinesignal-spec.md`
