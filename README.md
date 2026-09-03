# CineSignal

**The attention analytics desk for the film industry.** A google-adk / Vertex AI Gemini
multi-agent system that runs deterministic analyst playbooks over billions of real
Wikipedia-pageview rows (joined to the IMDb catalog in ClickHouse Cloud) and produces
evidence-backed decision memos — every number cited back to the exact query and rows
behind it.

Built for the **Agentic Cinema: The Blockbuster Hackathon** (ClickHouse track).
Full design spec: [`docs/plans/2026-08-24-cinesignal-spec.md`](docs/plans/2026-08-24-cinesignal-spec.md).

## Architecture

```
┌──────────────┐   ┌───────────────────────────── FastAPI (api/) ─────────────────────────────┐
│ React SPA    │──▶│ /api/resolve  /api/playbooks/{p}/run (SSE)  /api/memo/{id}  /api/evidence │
│ (web/)       │   │            │                                                              │
└──────────────┘   │            ▼                                                              │
                    │   Orchestrator (agent/tree.py)                                            │
                    │    ├─ EntityResolver   (agent/resolver.py — flash, google-adk LlmAgent)    │
                    │    ├─ PlaybookRunner   (agent/runner.py — deterministic, no LLM)           │
                    │    │    └─ agent/mcp_client.py ──▶ mcp-clickhouse (stdio subprocess)       │
                    │    ├─ Interpreter      (agent/interpreter.py — pro, google-adk LlmAgent)   │
                    │    ├─ MemoComposer     (agent/composer.py — pro, google-adk LlmAgent)      │
                    │    └─ NumberValidator  (agent/validator.py — deterministic, see note below)│
                    └────────────────────────────────────┬───────────────────────────────────────┘
                                                          ▼
                                    ClickHouse Cloud — pageviews_daily ⋈ entities ⋈ imdb_*
                                    + entity_attention_daily materialized view
```

**Model pinning:** `agent/config.py` — concrete Vertex AI Model Garden model IDs (`gemini-2.5-flash` /
`gemini-2.5-pro` as of 2026-09-03), each confirmed with a real `generate_content` call against this
project. Two dead ends worth knowing about if you touch this: the `-latest` aliases the Gemini
Developer API documents are **not** resolvable on Vertex's Model Garden (404), and `client.models.list()`
lists several newer models (`gemini-3.x-flash`, `gemini-3.x-pro-preview`) that themselves 404 on
`generate_content` for this project/region — being listed isn't the same as being invokable. Verify
with a live call, not just a catalog listing, before bumping these.

**Where google-adk / google-genai are actually called at runtime:** `agent/llm.py`
(`run_structured`, using `google.adk.agents.llm_agent.LlmAgent` + `google.adk.runners.Runner`
+ `google.adk.sessions.InMemorySessionService` against Vertex AI Gemini via `google-genai`),
consumed by `agent/resolver.py`, `agent/interpreter.py`, `agent/composer.py`.

**Where mcp-clickhouse is actually called at runtime:** `agent/mcp_client.py`
(`ClickHouseMCPSession`, spawning the real `mcp-clickhouse` console script over stdio and
calling its `run_query` MCP tool) — every playbook query, every entity search, and every
entity lookup goes through this, never a raw ClickHouse connection. Verified live during
Gate 0 (`scripts/test_mcp_clickhouse.py`).

**Determinism contract:** SQL lives only in `playbooks/*.yaml` as versioned templates with
`{{param}}` placeholders. `agent/sql_template.py` type-checks and literal-escapes every
parameter before it touches a query string — the LLM never writes or edits SQL, it only
chooses parameter values (via `agent/resolver.py`) and prose (via `agent/composer.py`). A
memo records `(playbook_id, playbook_version, params, query_ids)`; re-running the same
playbook with the same params reproduces identical numbers (`tests/test_golden_memos.py`).

**NumberValidator note:** the architecture sketch in the spec labels this step "flash" (an
LLM). It's implemented as deterministic code instead (`agent/validator.py`) — extract every
numeral from the composed memo, check it against the union of finding values and raw
evidence rows, reject if anything's untraceable. An LLM asked to "verify these numbers are
real" is exactly the kind of check an LLM is unreliable at; a set-membership check is
strictly stronger and is what the spec's own test plan ("inject a hallucinated numeral ->
memo must be rejected", `tests/test_validator.py`) actually needs. google-adk still does
real reasoning work in the other three LLM steps.

## The three playbooks

1. **Title Pulse** (`p1` / `title_pulse`) — attention health-check: daily series, percentile
   rank vs. a same-genre cohort each month, top anomaly days, 28-day momentum.
2. **Campaign Impact** ⭐ (`p2` / `campaign_impact`) — event study on a marketing beat:
   abnormal lift vs. a same-genre counterfactual cohort (baseline-scaled, median-aggregated),
   spike decay half-life, verdict vs. cohort distribution, spillover to cast/crew pages.
3. **Launch Window** (`p3` / `launch_window`) — ranks candidate release weekends in a target
   quarter by competition density + a 5-year seasonal genre demand curve.

Full methodology notes (including the documented `attention-hours` estimate assumption) are
in the docstrings at the top of `agent/playbooks_impl/*.py`.

## Repo layout

```
ingest/       Wikidata spine, IMDb catalog, Wikimedia pageviews ETL — see ingest/STATUS.md
playbooks/    Versioned SQL template YAML (the determinism boundary)
agent/        google-adk agent tree, MCP client, playbook engine, SQL templating
api/          FastAPI backend (SSE playbook runs, memo/evidence read-back)
web/          React + Vite + ECharts SPA
tests/        SQL template, validator, and determinism tests
scripts/      One-off smoke tests (Gate 0 MCP connectivity check)
docs/         Ideation + spec (pre-implementation planning artifacts)
```

## Running it locally

Prereqs: Python 3.12+, Node 20+, a ClickHouse Cloud (or self-hosted) instance, a GCP project
with Vertex AI enabled and `gcloud auth application-default login` run.

```bash
python -m venv venv && source venv/Scripts/activate   # or venv/bin/activate on macOS/Linux
pip install -r requirements.txt

cp .env.example .env   # fill in CLICKHOUSE_HOST/PORT/USER/PASSWORD, GOOGLE_CLOUD_PROJECT
python ingest/apply_ddl.py         # creates the cinesignal.* schema
python api/apply_state_ddl.py      # creates query_log/memos app-state tables

python scripts/test_mcp_clickhouse.py   # Gate 0: confirms the MCP path works end to end

# Load data (see ingest/STATUS.md for current row counts / resume instructions):
python ingest/run_all.py

# Backend:
uvicorn api.main:app --reload --port 8000

# Frontend (separate terminal):
cd web && npm install && npm run dev
```

Run tests: `python -m pytest tests/ -v` (template + validator tests need no external
services; the determinism test needs ClickHouse data and skips itself otherwise).

## Deploying

`Dockerfile` builds the SPA and bundles it into the same container as the FastAPI backend
(Cloud Run serves both from one process, per the spec's hosting choice). `cloudbuild.yaml`
builds, pushes, and deploys to Cloud Run, pulling ClickHouse credentials from Secret Manager
(never baked into the image). See the comments at the top of `cloudbuild.yaml` for the
one-time secret setup.

## Datasets & licenses

- **Wikimedia pageviews** — via the [Pageviews REST API](https://wikimedia.org/api/rest_v1/),
  CC0 / public domain aggregate statistics.
- **IMDb non-commercial datasets** — [datasets.imdbws.com](https://datasets.imdbws.com/),
  used under IMDb's non-commercial terms of use (hackathon/demo use).
- **Wikidata** — [query.wikidata.org](https://query.wikidata.org/), CC0.

## License

Apache-2.0 — see [`LICENSE`](LICENSE).
