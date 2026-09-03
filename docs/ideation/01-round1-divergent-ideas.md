# 01 — Round 1: Divergent Ideas (ClickHouse Track)

> Skills applied: `collision-zone-thinking`, `inversion-exercise` from `hameed0342j/svh`.
> Goal: quantity + novelty. No filtering yet — evaluation happens in `02-round1-evaluation.md`.
> Every idea must satisfy: Gemini/ADK agent + **`mcp-clickhouse` used at runtime** + a real
> media & entertainment workflow (filmmakers, screenwriters, studio crews, or fans).

## Step 0 — The Data Reality Check (done FIRST, per track strategy)

ClickHouse ideas live or die on data. Real, legally usable, *large* media datasets we can actually load:

| Dataset | Size | Real? | Access |
|---|---|---|---|
| **Wikimedia pageviews** (per-article, hourly/daily dumps) | Billions of rows/year | ✅ Real, live, public | dumps.wikimedia.org, CC0-ish licence; ClickHouse even documents `wikistat` as a showcase dataset |
| **IMDb non-commercial datasets** (titles, ratings, crew, principals) | ~50M+ rows, refreshed daily | ✅ Real | datasets.imdbws.com TSVs |
| **Wikidata** (maps IMDb tt-IDs ↔ Wikipedia articles via property **P345**) | Join table, ~1M film/person entities | ✅ Real | SPARQL/dump |
| GDELT global news events (film mentions) | Huge | ✅ Real | Public BigQuery/CSV |
| MovieLens 25M ratings | 25M rows | ✅ Real | Free, research licence |
| Box-office revenue (Mojo/The-Numbers) | Small | ⚠️ Scraping, ToS-gray | Avoid as core |
| Streaming QoE / render-farm logs / shot logs / social firehose | — | ❌ Synthetic or paywalled | Evaluator −2 penalty |

**Key unlock discovered here:** Wikidata P345 gives a clean join between the IMDb catalog and
Wikipedia article titles, which means **every film, franchise, actor, and director can be joined to
a real, multi-year, daily attention time series** — billions of genuine rows, exactly the shape
ClickHouse is famous for. Several ideas below exploit this.

## Collision Zone (treat X like Y)

| Collision | Emergent properties | Where it breaks | Insight |
|---|---|---|---|
| **Fan attention × tick data / quant trading** | Momentum, moving averages, volatility, drawdowns, **event studies** ("trailer drop = earnings call"), abnormal-return windows | No tradable price; attention ≠ purchase intent | Marketing beats can be *measured* like market events — attention is the studio's asset price |
| **Attention spikes × seismology** | Foreshocks (leaks/rumors), mainshock (announcement), aftershocks (discourse), magnitude scales, epicenters (which language community first) | Earthquakes aren't caused by PR teams | Real-time anomaly detection + cause attribution over the pageview stream |
| **Localization × epidemiology** | Attention spreads across language communities like contagion; dubbing = deciding where to "vaccinate" next; R₀ of a franchise per territory | Contagion needs contact networks; proxy only | Per-language Wikipedia editions = free, real, per-territory demand signal for dubbing/subbing priority |
| **Film slate × portfolio theory** | Diversification, correlated genre risk, hedging tentpoles with mid-budget | Films aren't liquid assets | Slate-level risk analytics instead of per-title gut feel |
| **Release calendar × airline yield management** | Demand forecasting per window, competitor capacity, overbooking ≈ crowded weekends | Seats are commodities; films aren't | Release-window optimization as a yield problem |
| **Dailies/shot logs × supply-chain telemetry** | Coverage gaps = stockouts; reshoots = expedited freight | Data is private per production | On-set analytics idea family (data problem flagged) |

## Inversion Exercise

| Everyone assumes | Inverted | What it reveals |
|---|---|---|
| "AI should *predict box office*" (every hackathon does this) | Don't predict revenue — **measure marketing cause-and-effect after the fact** | Attribution/ROI measurement is the unsexy enterprise friction; prediction demos are a judged-to-death cliché |
| "Fans are the audience" | **Fans are the sensor network** | 300M daily Wikipedia readers are a free, real, global panel |
| "Buzz is soft/unmeasurable" | Treat buzz as **hard tick data** with reproducible statistics | Deterministic SQL playbooks, not vibes |
| "Chat with your database" | **No chat.** Fixed, deterministic analyst playbooks that output signed decision memos | Matches the brief's literal words: "deterministic, multi-step agent"; sidesteps the text-to-SQL cliché AND its reliability problems |
| "Dashboards are the product" | **Memos are the product** — a decision document with evidence, produced by an agent | "Complete product experience" (judging criterion #2), not another Grafana clone |
| "More marketing is always better" | Detect **saturation** — when the next trailer buys nothing | A finding worth real money |

## The 18 Ideas

### A. Development / Greenlight (studio execs)
1. **GreenlightIQ** — Comps-memo agent: pick 20 true comparables for a pitched project (genre ×
   era × talent × attention trajectory) from IMDb + attention data; output a greenlight memo.
2. **SlateSim** — Portfolio-theory risk simulation across a studio's announced slate; correlated
   genre/date risk. *(Needs financials → data problem.)*
3. **TalentRadar** — Rising-star detector: attention *velocity* (d/dt of pageviews) × credit
   growth from IMDb principals; agent writes scouting cards for casting/agencies.
4. **CastingComps** — Data-backed casting shortlists: bankability index per actor from ratings,
   billing positions, attention trends.

### B. Marketing / Distribution (the attention-data family)
5. **FanPulse** — Franchise attention health monitor: multi-year daily attention per
   title/franchise/star, benchmarked against genre cohorts.
6. **CampaignImpact** — *Event-study* agent: quantify exactly what a trailer drop, casting
   announcement, or controversy did to attention — abnormal lift vs. counterfactual baseline,
   decay half-life, and cross-title spillover. "Marketing ROI in attention units."
7. **ReleaseWindowOptimizer** — Yield-management view of the release calendar: competition
   density, seasonal genre demand curves, and attention runway → best 3 windows with evidence.
8. **LocalizationLens** — Dubbing/subbing priority: per-language-edition attention shows *where*
   a title is over/under-indexing → ranked localization investment list per territory.
9. **CineSeismograph** — Streaming anomaly detector on the attention feed: detects "quakes,"
   sizes magnitude, attributes cause (joins metadata + news events), alerts marketing.
10. **FandomAtlas** — Map of where a fandom lives (language editions ≈ territories) and how it
    migrates over a franchise's life; fan-facing explorer + studio view.
11. **FranchiseDecay** — Sequel-fatigue diagnostics: attention decay curves across installments;
    "the data says rest this IP for 2 years."

### C. Production / Post Ops (studio crews)
12. **DailiesDesk** — Shot-log & coverage analytics for on-set crews. *(Synthetic data.)*
13. **RenderLedger** — Render-farm log cost analytics agent. *(Synthetic data.)*
14. **QoEWatch** — Streaming quality-of-experience war room. *(Synthetic data.)*
15. **PostHouse Planner** — Post-production capacity planning. *(Synthetic data.)*

### D. Awards / Exhibition / Fans
16. **AwardsOracle** — Awards-season momentum tracker: attention races between contenders.
17. **RepertoryProgrammer** — Art-house cinema programming agent: which classics are trending
    where → repertory calendar suggestions.
18. **SpoilerSafe Stats** — Fan-facing stats explorer for franchises. *(Chat-with-data cliché risk.)*

## Observations Before Scoring

- Ideas **5–11 all share one warehouse**: (Wikimedia pageviews × Wikidata P345 × IMDb metadata).
  That smells like a `simplification-cascades` moment — park it for Round 2.
- Ideas 12–15 are the "obvious enterprise ops" family, but all require synthetic data → the
  evaluator's Rule 2 and Rule 4 will hit them hard.
- Idea 6 (CampaignImpact) is the only one whose *methodology* (event studies) is borrowed from
  another field entirely — collision-zone thinking says that's where novelty lives.
- Published research backs the impact story: Mestyán, Yasseri & Kertész (2013) showed Wikipedia
  activity predicts box-office success — citable evidence that the proxy is credible.

→ Proceed to `02-round1-evaluation.md` for honest scoring.
