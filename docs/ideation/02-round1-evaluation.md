# 02 — Round 1 Evaluation (honest /60 scoring)

> Skill applied: `hackathon-idea-evaluator` from `hameed0342j/svh` — 6 dimensions × 10, with
> anti-inflation rules. Target: **≥48/60** on *corrected* scoring before committing to build.
> Anti-inflation rules in force:
> R1 — score the TECH, not the metaphor (existing underlying tech ⇒ Novelty ≤ 7).
> R2 — data you don't have: −2 Feasibility. Paid/missing APIs: −1.
> R3 — Impact = technical potential × adoption probability.
> R4 — mock-data demos: −1 Demo-ability; judges can tell.

## Quick-kill round (scored briefly, eliminated with cause)

| Idea | Score | Kill reason |
|---|---|---|
| 2. SlateSim | ~37 | Needs per-title financials that don't exist publicly (R2 −2); demo is a chart of guesses |
| 4. CastingComps | ~39 | Novelty 5 — "data-driven casting" decks exist at every agency; ethically fraught to demo on real people |
| 12. DailiesDesk | ~37 | 100% synthetic data (R2 −2, R4 −1); judges from ClickHouse will ask "whose data is this?" |
| 13. RenderLedger | ~37 | Same synthetic-data trap |
| 14. QoEWatch | ~35 | Novelty 4 — QoE dashboards are ClickHouse's own marketing material; we'd be re-demoing their blog to their judges |
| 15. PostHouse Planner | ~33 | Synthetic + weak demo |
| 16. AwardsOracle | ~39 | Seasonal (no awards race in September), Impact 5 |
| 17. RepertoryProgrammer | ~36 | Charming but Impact 4 — audience is tiny and unbudgeted |
| 18. SpoilerSafe Stats | ~34 | Novelty 3 — it's "chat with IMDb"; the exact cliché we predicted the track drowns in |

## Full scoring — the six survivors

### 1. GreenlightIQ — comps-memo agent
| Dimension | Score | Justification |
|---|---|---|
| Novelty | 5 | Comps analysis is standard studio-analyst work; LLM-over-warehouse comps ≈ text-to-SQL family (R1 cap) |
| Feasibility | 6 | IMDb ratings/votes are a weak proxy for revenue; real box office is ToS-gray (R2 −1) |
| Scalability | 7 | Cohort queries over 10M titles — fine for ClickHouse |
| Impact | 7 | Greenlight decisions are $10M–$200M bets; but execs won't trust a hackathon memo (R3) |
| Demo-ability | 6 | Output is a text memo — no visual wow |
| Domain Fit | 9 | Core studio workflow |
| **TOTAL** | **40/60** | |

**Verdict:** Pivot — the memo *format* is valuable; the greenlight *use case* lacks demoable teeth.

### 3. TalentRadar — rising-star detector
| Dimension | Score | Justification |
|---|---|---|
| Novelty | 7 | Attention-*velocity* screening is fresh framing; underlying tech = time-series derivative + join (R1 cap 7) |
| Feasibility | 7 | Real data end-to-end (pageviews + IMDb principals) |
| Scalability | 7 | 50M principals rows × attention series — natural ClickHouse |
| Impact | 6 | Casting/agencies would love it, but adoption path unclear; "heat" lists already exist informally (R3) |
| Demo-ability | 7 | "Watch us find the next breakout" is fun but unverifiable live |
| Domain Fit | 8 | Real workflow (packaging/casting) |
| **TOTAL** | **42/60** | |

### 5. FanPulse — franchise attention monitor
| Dimension | Score | Justification |
|---|---|---|
| Novelty | 6 | Monitoring dashboards are a known genre (Google Trends adjacency caps this, R1) |
| Feasibility | 8 | Real data, well-documented ingestion path |
| Scalability | 8 | Billions of real rows — the honest ClickHouse story |
| Impact | 7 | Studios track "social listening" with expensive vendors; free-signal alternative is credible |
| Demo-ability | 7 | Pretty charts, but a monitor is passive — no decisive moment |
| Domain Fit | 8 | Marketing analytics is a real studio department |
| **TOTAL** | **44/60** | |

### 6. CampaignImpact — event-study agent ("marketing ROI in attention units")
| Dimension | Score | Justification |
|---|---|---|
| Novelty | 7 | Event-study methodology (finance econometrics) applied to film-marketing beats is genuinely non-obvious; underlying stats are standard, so R1 caps at 7 |
| Feasibility | 7 | Real data; event dates obtainable (trailer release dates from metadata/news); the stats are well-specified — no research risk |
| Scalability | 8 | Per-event window scans over billions of rows; cohort baselines — pure ClickHouse strength |
| Impact | 8 | Tentpole campaigns spend $100M+ with famously weak attribution; a measured "this trailer bought +34M attention-hours, half-life 6 days" is a real enterprise answer (R3: analysts, not execs, adopt first — plausible) |
| Demo-ability | 8 | Before/after event chart with counterfactual band = instant visual comprehension; real titles judges recognize |
| Domain Fit | 9 | Squarely a studio-crew (marketing dept) workflow named in the brief |
| **TOTAL** | **47/60** | |

**Verdict:** Build-candidate. Biggest risk: judges dismiss pageviews as a proxy → pre-empt with the
Mestyán/Yasseri/Kertész (2013) citation and a validation panel in the product.

### 7. ReleaseWindowOptimizer
| Dimension | Score | Justification |
|---|---|---|
| Novelty | 6 | Release-calendar analytics exist inside studios; yield-management framing is nice but framing ≠ tech (R1) |
| Feasibility | 7 | Real data (calendar from IMDb, demand curves from attention history) |
| Scalability | 7 | Seasonal cohort queries — fine |
| Impact | 7 | Date changes are eight-figure decisions; credible |
| Demo-ability | 7 | Calendar heatmap is decent, not thrilling |
| Domain Fit | 9 | Core distribution workflow |
| **TOTAL** | **43/60** | |

### 8. LocalizationLens
| Dimension | Score | Justification |
|---|---|---|
| Novelty | 7 | Per-language-edition attention as a dubbing-priority signal — haven't seen it anywhere (R1 cap: underlying tech is aggregation) |
| Feasibility | 7 | Language-split pageviews are real and public; mapping editions→territories is approximate |
| Scalability | 7 | ~300 language editions × titles × days |
| Impact | 7 | Localization budgets are real and rising (streaming); ranked-priority output is directly actionable |
| Demo-ability | 7 | World-map view is attractive; insight is subtle to a lay judge |
| Domain Fit | 8 | Streaming-era studio workflow |
| **TOTAL** | **43/60** | |

### 9. CineSeismograph
| Dimension | Score | Justification |
|---|---|---|
| Novelty | 7 | Real-time attention seismology + cause attribution is a fresh combination (R1 cap) |
| Feasibility | 6 | Needs near-real-time ingestion loop — extra moving parts in 16 days (−1) |
| Scalability | 8 | Streaming inserts + anomaly scans: ClickHouse sweet spot |
| Impact | 6 | Alerting on fame-quakes is cool; who pays and what do they *do* next is fuzzier (R3) |
| Demo-ability | 8 | Live quake detection with magnitude scale is theatrical |
| Domain Fit | 8 | Marketing/comms war-room |
| **TOTAL** | **43/60** | |

## Round 1 Ranking

| Rank | Idea | Score | Strength | Weakness |
|---|---|---|---|---|
| 1 | CampaignImpact | 47 | Non-obvious method + real data + $ impact | Proxy skepticism |
| 2 | FanPulse | 44 | Easiest to build, honest scale story | Passive monitor, low novelty |
| 3 | ReleaseWindowOptimizer | 43 | Core workflow | Novelty 6, muted demo |
| 3 | LocalizationLens | 43 | Freshest niche insight | Subtle demo |
| 3 | CineSeismograph | 43 | Theatrical demo | Real-time complexity, fuzzy buyer |
| 6 | TalentRadar | 42 | Fun screening story | Unverifiable claims |

## Evaluator's Combination Flag (rule: two 45–50 ideas sharing infrastructure → check for a 55+ merge)

Ideas 5, 6, 7, 8, 9 **all run on the identical warehouse** (pageviews × Wikidata P345 × IMDb) and
all output the same *shape* of artifact (evidence-backed decision memo). None alone clears 48.
Round 2 must test the merge: **one attention-analytics engine, several deterministic playbooks.**

→ Proceed to `03-round2-refinement.md`.
