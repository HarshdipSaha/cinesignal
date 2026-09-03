# 06 — 🏆 BEST IDEA: CineSignal

> **Track:** ClickHouse · **Final corrected score:** 48/60 (evaluator target met)
> Survived: 18-idea divergent round → honest scoring → cascade merge → re-score → scale game & kill-list.
> Pitch structured with `hackathon-pitch-builder`; concept files: 00–05 in this folder.

## One-liner

**CineSignal is the attention analytics desk for the film industry** — a Gemini multi-agent
system that treats global fan attention as market tick data (billions of real Wikipedia pageview
rows in ClickHouse) and runs **deterministic analyst playbooks** that answer studio marketing and
distribution questions with **evidence-backed decision memos**.

## The Problem (enterprise friction, per the brief)

Studios spend **$100M+ marketing a single tentpole** and still argue in conference rooms about
whether the trailer "worked." Social-listening vendors are expensive, sampled, and unauditable.
Meanwhile 300M people a day vote with their attention on Wikipedia — a free, absolute-count,
per-language, per-day signal that is **peer-reviewed as a box-office predictor** (Mestyán, Yasseri
& Kertész, PLoS ONE 2013) — and nobody in the workflow can query it.

## The Product

| Piece | What it does |
|---|---|
| **The Warehouse** | ClickHouse Cloud holding the *film attention universe*: Wikimedia per-article daily pageviews (≥1B real rows target, 300M floor) joined via **Wikidata P345** to the full IMDb catalog (titles, people, franchises, genres, release dates) |
| **The Engine** | `AttentionQuery` — versioned, parameterized SQL templates (the LLM never writes SQL). Rollups via materialized views; sub-second aggregations |
| **The Agents** | google-adk tree on Vertex AI Gemini: Orchestrator → EntityResolver → PlaybookRunner (deterministic SequentialAgent; steps call ClickHouse through the official **`mcp-clickhouse` MCP server**) → Interpreter → MemoComposer → NumberValidator |
| **The Playbooks** | ① **Title Pulse** — attention health-check vs. genre cohort. ② **Campaign Impact** ⭐ — finance-grade event study on a marketing beat: abnormal lift vs. counterfactual cohort baseline, decay half-life, spillover to cast/franchise pages. ③ **Launch Window** — competition density + seasonal demand → ranked release windows. ④ *(stretch)* **Localization Priority** — per-language over/under-index → dubbing territory ranking |
| **The Memo** | The deliverable: a decision document where **every number links to the exact query and rows behind it** (evidence chain). Re-running a memo reproduces it exactly |
| **Fan Explorer** | Public read-only page — fans explore any franchise's attention history (Design criterion + the "fans" audience) |

## Why this wins the ClickHouse track specifically

1. **Real scale, real data** — most entries will demo mock rows; we live-scan billions of genuine
   rows in front of engineers who query billions of rows for a living.
2. **ClickHouse is load-bearing** — cohort counterfactuals over the full history per interaction;
   this demo is impossible on Postgres, and the judges will know it.
3. **Official MCP integration done right** — the agent's tools are MCP calls executing versioned
   templates: deterministic, reproducible, safe. A pointed contrast to the text-to-SQL chat bots
   this track will drown in.

## The three non-obvious moves (Quality of the Idea criterion)

- **Inversion:** everyone predicts box office; we *measure marketing cause-and-effect*. Fans
  aren't the audience — **fans are the sensor network**.
- **Collision:** finance event-study econometrics × film marketing. A trailer drop is an earnings
  call: abnormal lift, half-life, spillover β.
- **Anti-chat:** memos, not chat. "Deterministic, multi-step agent" — the brief's own words.

## 3-Minute Demo Video Script (pitch-builder format)

- **[0:00–0:15] HOOK** — "Studios spend a hundred million dollars marketing one film — and can't
  tell you what the trailer did. We measured it. Live."
- **[0:15–0:45] PROBLEM** — attribution gap; vendors expensive & unauditable; the free signal
  nobody queries (flash the 2013 PLoS ONE citation).
- **[0:45–1:15] SOLUTION** — one architecture slide, 5 boxes: Wikimedia+IMDb → ClickHouse →
  mcp-clickhouse → ADK/Gemini agents → Memo. State the row count on screen.
- **[1:15–2:30] LIVE DEMO** — type a real franchise → Title Pulse renders in seconds ("that scan
  crossed 1.8 billion rows") → run **Campaign Impact** on its latest trailer → the WOW chart:
  spike vs. counterfactual band, "+41M attention-hours, half-life 6 days, 22% spillover to the
  lead actor" → click a number → the exact SQL + rows appear (evidence chain) → memo exports.
- **[2:30–2:45] SCALE** — "Same schema ClickHouse runs at trillion-row scale; playbooks are
  stateless templates — a studio's whole slate gets memos nightly."
- **[2:45–3:00] ASK** — "Pilot with one studio marketing team; hourly streaming next. CineSignal:
  greenlight decisions, measured."

## Compliance checklist (Stage One pass/fail)

- [ ] Hosted URL: Cloud Run (web platform) ✓ planned
- [ ] Runtime Google AI: `google-adk` + `google-genai` (Vertex AI Gemini) imported & called ✓ planned
- [ ] Runtime Partner: official `mcp-clickhouse` server → ClickHouse Cloud cluster ✓ planned
- [ ] Public repo + OSI licence (Apache-2.0, visible in About) ✓ planned
- [ ] ≤3-min public YouTube demo video, English ✓ scripted above
- [ ] New work, contest period only ✓
- [ ] No non-Google AI anywhere in the product ✓ (Gemini only)
- [ ] Devpost form: track = ClickHouse ✓

**Next artifact:** detailed build spec → `../plans/2026-08-24-cinesignal-spec.md`.
