# 03 — Round 2: Refinement & Combination

> Skills applied: `simplification-cascades`, `inversion-exercise`, `collision-zone-thinking`
> (second pass), evaluator's Combination Strategy.
> Input: six survivors from Round 1, none ≥48. Hypothesis: the five attention-family ideas are one product.

## The Simplification Cascade

**Before (five separate "products"):**
- FanPulse: monitor a title's attention over time
- CampaignImpact: measure what an event did to attention
- ReleaseWindowOptimizer: compare attention/competition across calendar windows
- LocalizationLens: split attention by language edition
- CineSeismograph: detect anomalies in the attention stream

**Insight:** *Every studio question here is the same query shape —*
> **an attention time series × a metadata dimension × a comparison window → explained by events → delivered as a decision memo.**

**After:** ONE engine — `AttentionQuery` (parameterized SQL templates over one schema) — plus a
library of **deterministic playbooks** that sequence 4–8 engine calls and hand the numbers to
Gemini for interpretation and memo writing.

**Eliminated:** 5 products → 1 platform with 4 playbooks. One warehouse. One ingestion pipeline.
One memo renderer. (Cascade test passed: every idea fits the abstraction with zero special-casing;
CineSeismograph's streaming mode is the only partial fit → demoted to stretch goal.)

## The Merged Concept — working name: **CineSignal**

> **The attention analytics desk for the film industry.** A multi-agent Gemini system that treats
> global fan attention as market tick data — billions of real Wikipedia pageview rows in
> ClickHouse — and runs deterministic analyst playbooks that answer studio questions with
> evidence-backed decision memos.

**Who it serves (named in the hackathon brief):** studio crews — specifically marketing,
distribution, and localization teams; secondarily filmmakers pitching with data, and fans (public
explorer mode).

**MVP playbooks (ship 3, stretch 1):**
1. **Title Pulse** — full attention health-check for any title/franchise/person: trajectory,
   genre-cohort benchmark, momentum, top attention events auto-detected. *(absorbs FanPulse)*
2. **Campaign Impact** — event study on a marketing beat: abnormal lift vs. counterfactual
   baseline (genre-cohort control), decay half-life, spillover to cast/franchise pages, verdict.
   *(the flagship — absorbs CampaignImpact)* **← demo centerpiece**
3. **Launch Window** — competition density + seasonal demand for a target date range; ranked
   window recommendations. *(absorbs ReleaseWindowOptimizer)*
4. *(Stretch)* **Localization Priority** — per-language attention over/under-index → ranked
   dubbing territories. *(absorbs LocalizationLens)*
5. *(Post-hackathon roadmap only)* Seismograph streaming alerts, TalentRadar screening.

## Second-pass Inversions (product shape)

| Assumption | Inversion | Adopted? |
|---|---|---|
| Agent = chat box over the DB | Agent = **analyst that runs a fixed pipeline and signs a memo**; chat only for follow-ups on a finished memo | ✅ Core identity — matches "deterministic, multi-step agent" verbatim and dodges the text-to-SQL cliché |
| LLM writes the SQL | **SQL is templated and versioned; the LLM never writes SQL.** Gemini resolves entities, picks parameters, interprets results, writes prose | ✅ Determinism, safety, reproducibility — a memo can be re-run and produce the same numbers |
| Show the agent thinking | Show the **evidence chain**: every number in the memo links to the exact query + rows behind it | ✅ "Judges can distinguish mock from real" — we make real-ness inspectable |
| Bigger model = better | Small fast model for entity resolution, big model only for memo synthesis | ✅ Cost + latency |

## Second-pass Collision (demo language)

Attention × quant trading gives the memo its vocabulary — judges grasp it instantly:
- "**Attention-hours**" = volume metric (Σ daily views over window)
- "**Abnormal lift**" = actual − counterfactual baseline (cohort-controlled)
- "**Half-life**" = days for the spike to decay 50%
- "**Spillover β**" = how much a title event moves its cast/franchise pages
- The Campaign Impact memo reads like an earnings-day event study — for a trailer drop.

## What makes this hard to copy in a weekend (moat for judging)

1. The **data engineering** — billions of real rows ingested, joined via Wikidata P345, rolled up
   with materialized views. Every other team demos on 10k mock rows.
2. The **methodology** — cohort-controlled counterfactuals, not "views went up."
3. The **determinism** — versioned SQL playbooks: same input, same memo, every run. ClickHouse
   judges (an AI/ML engineering director + full-stack AI engineer) will recognize both 1 and 3.

## Standalone finalist kept alive (anti-groupthink check)

Per the evaluator's red-flag discipline, we keep **CampaignImpact-standalone** (no platform, one
playbook, maximal polish) as Finalist B. If Round 3 stress-testing shows the platform can't be
built in 16 days, we descope to B without changing architecture — B is literally playbook #2 of A.

→ Re-scored in `04-round2-evaluation.md`.
