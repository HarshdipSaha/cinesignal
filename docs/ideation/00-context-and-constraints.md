# 00 — Context & Constraints

> Agentic Cinema: The Blockbuster Hackathon (Google Cloud × Devpost)
> Distilled from `details/main.txt`, `details/rules.txt`, `details/resources.txt` on 2026-08-24.
> Deadline: **Sept 9, 2026, 2:00 PM PT** (Sept 10, 2:30 AM IST) — **~16 working days left.**

> ## 🔒 USER DECISION (2026-08-24): Track locked to **CLICKHOUSE**.
> All ideation below targets the ClickHouse track only: the agent must actively use ClickHouse at
> runtime via the official **`mcp-clickhouse` MCP server** against a ClickHouse Cloud or
> self-hosted cluster. ClickHouse Agent Skills during development: optional, encouraged.

## The Challenge (verbatim essence)

Build a **functional, production-ready AI agent or multi-agent network — powered by Gemini and
Google Cloud Agent Builder — that integrates a Partner Entity's product or MCP server** to solve
critical bottlenecks across the **entertainment and media value chain**, targeting the workflows of
**filmmakers, screenwriters, studio crews, or fans**.

The overview page adds the key phrase judges will pattern-match on:

> "Show off a **deterministic, multi-step agent** that solves **enterprise friction**."

## Hard Requirements (Stage One is pass/fail — miss one and you're out)

1. **Hosted project URL** (web, Android, or iOS).
2. **≤3-minute demo video** on YouTube/Vimeo, public, English or English subtitles, showing the
   real product functioning (not a cinematic trailer).
3. **Public open-source repo** (GitHub/GitLab/Bitbucket) with an OSI license **detectable in the
   About section** (put LICENSE at repo root, set it in repo metadata).
4. Repo must show **runtime use of Google Cloud AI** — imported and actually called. Accepted
   packages: `google-adk`, `google-genai`, `google-generativeai`, `google-cloud-aiplatform`.
5. Repo must show **runtime use of the chosen Partner's service** (not just README mentions).
6. **New project only** — created during the contest period (starts July 27, 2026).
7. **AI restriction:** only Google Cloud AI tools + the partner's built-in AI features. **No
   OpenAI, Anthropic, AWS, or Microsoft AI anywhere in the project.** Non-AI third-party services
   (hosting, DBs, web frameworks) are fine.
   - ⚠️ *Compliance note to decide consciously:* the restriction is written around what the
     project uses; the IBM/Replit tracks separately mandate partner tools "as part of the
     development process." Safest reading: keep the **shipped product** 100% Google-AI-only, and
     don't advertise non-Google AI dev tooling in the submission materials.

## Partner Tracks (judged separately — you only compete within your track)

| Track | Runtime requirement | Solo-dev friction | Verdict |
|---|---|---|---|
| **IBM** | Must be *built with IBM Bob* (dev process requirement); Confluent optional | Unknown tool, dev-process lock-in, hard to prove | ❌ Avoid |
| **Grafana Labs** | Must call the **Grafana Cloud MCP server** (`mcp-grafana`) at runtime | Need a telemetry stack to observe → heavy synthetic-data setup | ⚠️ Possible |
| **Parallel** | Must call **Parallel Search API** at runtime (`parallel-web` SDK, LangChain tool, or grounding config) | Lightest integration, but will attract every "research agent" wrapper | — |
| **ClickHouse** | Must use the **ClickHouse MCP server** (`mcp-clickhouse`) at runtime against a real cluster | Need large, believable datasets → the single biggest design constraint | ✅ **LOCKED (user decision)** |
| **Replit** | Must be *built with Replit Agent* AND deployed on `replit.app`/`replit.dev` | Dev-process lock-in + likely the most crowded track (lowest entry barrier) | ❌ Avoid |

**Track strategy (ClickHouse-locked):** the track's judges are ClickHouse AI/ML engineers — they
will instantly smell a token integration ("we stored our app rows in ClickHouse") or a thin
text-to-SQL chat wrapper. To win this track the idea must make ClickHouse's *actual superpower*
(interactive aggregation over billions of time-series/event rows) load-bearing for the demo, and it
must run on **real data at real scale** — the `hackathon-idea-evaluator` skill explicitly penalizes
mock-data demos. Finding a large, legally usable, real media dataset is therefore the first-class
ideation constraint, not an afterthought.

## Judging Criteria (Stage Two, equal weight)

1. **Technological Implementation** — quality of build; how effectively Google Cloud + Partner are used.
2. **Design** — a complete, coherent *product*, not a proof of concept.
3. **Potential Impact** — credible, specific case for a real problem for a real audience.
4. **Quality of the Idea** — creative, **non-obvious** use of the services; genuine understanding of the problem space.

## Predicted Competitive Landscape (what everyone else will build)

8,000 participants. Expect saturation in:
- Script/storyboard/trailer **generators** (Imagen, Veo, Lyria demos re-skinned)
- "Chat with your movie database" text-to-SQL bots
- Script coverage / loglines / pitch-deck writers
- Generic "research agent" wrappers around Parallel
- Incident-response demos copied from Grafana's own examples

**Implication:** the winning wedge is a *real, unglamorous, expensive* industry workflow that
generative-AI tourists don't know exists. Deep domain specificity is the moat — judging criterion
#4 says so explicitly.

## Prize Math

$15,000/track (7.5k / 4.5k / 3k). Track-isolated judging means **track choice is a strategic
variable as important as the idea itself.**

## Constraints Snapshot

- Solo builder, ~16 days, evenings/weekends realistic budget ≈ 60–80 hours.
- $100 Google Cloud credit (form deadline Aug 31 — **request immediately**).
- Parallel offers free API credits for hackathons (verify quota early).
- Must run on web (simplest platform target).
- Team can be added later (max 4) but plan assumes solo.

## Skills Used for This Ideation (per user instruction)

From `hameed0342j/svh` (`hackathon-skills/` + `superpowers-skills/`):
`collision-zone-thinking`, `inversion-exercise`, `hackathon-idea-evaluator` (6-dimension /60
rubric with anti-inflation rules), `scale-game`, `simplification-cascades`,
`hackathon-pitch-builder`, superpowers `brainstorming` + `writing-plans`.
From `asadullah48/hackathon-skills-marketplace`: `hackathon-todo-advanced` (used as a template for
phase-structured planning, submission checklists, and MCP/agent architecture patterns).

## Ideation Pipeline (what the next files contain)

1. `01-round1-divergent-ideas.md` — 18 ClickHouse-track ideas (collision-zone + inversion applied)
2. `02-round1-evaluation.md` — honest /60 scoring, shortlist
3. `03-round2-refinement.md` — top ideas refined: combinations, inversions, cascades
4. `04-round2-evaluation.md` — re-scores, two finalists
5. `05-round3-stress-test.md` — scale game, risk kill-list, judge-criteria mapping
6. `06-BEST-IDEA.md` — the winner, full concept + pitch skeleton
7. `../plans/2026-08-24-best-idea-spec.md` — detailed build spec for the winner
