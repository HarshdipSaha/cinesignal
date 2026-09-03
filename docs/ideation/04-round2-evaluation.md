# 04 — Round 2 Evaluation (re-scores)

> Skill applied: `hackathon-idea-evaluator`, same anti-inflation rules as Round 1.
> Candidates: **A. CineSignal** (platform: engine + 3 playbooks + stretch), **B. CampaignImpact
> standalone** (one playbook, max polish). Both target the ClickHouse track.

## A. CineSignal — attention analytics desk (engine + 3 playbooks)

| Dimension | Score | Justification |
|---|---|---|
| Novelty | 7 | R1 cap holds (aggregation + LLM synthesis exist), but the *combination* — real billion-row fan-attention warehouse + finance-grade event studies + deterministic no-text-to-SQL playbooks — is not something judges will see twice in this track |
| Feasibility | 7 | All real data with documented ingestion paths; the cascade means 3 playbooks share one engine (each marginal playbook ≈ 1 day); risk concentrated in ingestion week — see stress test |
| Scalability | 8 | The architecture *is* the scale story: MergeTree partitions, materialized-view rollups, sub-second aggregations over billions of rows — live, not hypothetical |
| Impact | 8 | Specific audience (studio marketing/distribution analysts), specific pain ($100M+ campaigns, weak attribution; localization budget triage), free-signal alternative to expensive social-listening vendors; Mestyán et al. 2013 grounds the proxy scientifically |
| Demo-ability | 9 | Real titles judges know; live sub-second scans over ~2B real rows; the event-study chart with counterfactual band is a genuine WOW; memo with clickable evidence chain closes the loop. No mock-data penalty — that's rare in this track |
| Domain Fit | 9 | Marketing/distribution/localization are studio-crew workflows named in the brief; fans double as both the sensor network and a public explorer audience |
| **TOTAL** | **48/60** | ✅ Meets the ≥48 build threshold |

**Biggest risk:** ingestion week slips → demo runs on 300M rows instead of 2B. (Still real, still fast — degraded, not dead.)
**How to gain +3–5:** ship the Localization playbook (novelty width), add the public fan-explorer
page (Design criterion), pre-compute demo entities so live latency is consistently sub-second.

## B. CampaignImpact standalone

| Dimension | Score | Justification |
|---|---|---|
| Novelty | 7 | Same cap |
| Feasibility | 8 | Smallest possible scope; two spare days appear |
| Scalability | 8 | Same warehouse |
| Impact | 7 | One question answered instead of a desk an analyst lives in; weaker "complete product" story (judging criterion #2 explicitly rewards completeness) |
| Demo-ability | 8 | Same flagship chart, but the demo has one act instead of three |
| Domain Fit | 9 | Same |
| **TOTAL** | **47/60** | |

## Decision Table

| Rank | Idea | Score | Strength | Weakness |
|---|---|---|---|---|
| 1 | **A. CineSignal** | **48/60** | Complete product; three-act demo; every judging criterion covered | More build surface |
| 2 | B. Standalone | 47/60 | Safety margin | Reads as a feature, not a product |

**Call:** Build **A**, with **B as the pre-agreed descope line** (B = A minus playbooks 1 & 3 —
same engine, same schema, no architectural rework). The descope decision gate is set for **day 8**
in the spec.

→ Final stress test in `05-round3-stress-test.md` before declaring BEST IDEA.
