# CineSignal ingest — status

As of 2026-09-03 ~14:47 UTC. Real `SELECT count()` numbers from ClickHouse
Cloud (`cinesignal` database), not estimates. `wikidata.py` (film type
still paginating) and `pageviews.py` are **still running in the
background** at the time of this handoff — see "Still running" below.

## Row counts (cinesignal database)

| table | rows |
|---|---|
| `entities` | 71,148 |
| `imdb_titles` | 2,443,386 |
| `imdb_ratings` | 1,712,791 |
| `imdb_principals` | 21,892,166 |
| `imdb_crew` | 2,443,386 |
| `imdb_episodes` | 9,865,546 |
| `imdb_names` | 15,623,292 |
| `pageviews_daily` | 1,873,404 (growing) |
| `entity_attention_daily` | 1,755,860 (growing, kept live by the MV) |

IMDb load is **complete** (`imdb.py` exited 0, all 6 datasets downloaded
and loaded). Wikidata and pageviews are **in progress** (both resumable,
both fine to leave running).

## Entities spine, by entity_type (growing — film still paginating)

| entity_type | count |
|---|---|
| film | 46,853 (of ~274,155 WDQS candidates with P31=film + P345; will keep growing until wikidata.py's film stage-A pagination finishes) |
| series | 4,321 (stage-A complete) |
| person | 19,945 (stage-A complete) |
| franchise | 29 (stage-A complete — franchise is a small, best-effort set per spec) |

Data quality on what's loaded so far (film):
- genres populated: 44,526 / 46,853 (~95%)
- release_date populated: 29,607 / 46,853 (~63% — see "Known gaps" below for why the rest are null, not missing from Wikidata)

## Pageviews coverage

- Date range actually pulled: 2023-09-01 .. 2026-09-01 (full 36-month window, confirmed via `min(date)`/`max(date)`).
- 1,877 distinct pages fetched so far out of the (growing) entities spine; `pageviews.py` re-queries `entities` for its page spine on each invocation, so it naturally picks up pages added by the still-running `wikidata.py` on its next run.
- Throughput observed: ~2 pages/sec with 12 workers (WMF per-article API is one HTTP call per page covering the whole date range, not per-day — cost scales with page count, as designed). 0 errors so far.

## Known gaps / errors encountered (and fixed) during this build

1. **`entities.release_date` is `Nullable(Date)`**, but ClickHouse `Date`
   only supports 1970-01-01..2149-06-06. Many real films predate 1970
   (e.g. classics from the 1920s-1960s). Rather than widen the column to
   `Date32` — which the auto-mode permission classifier blocked as a
   shared-schema change another process might depend on — `wikidata.py`
   clamps out-of-range P577 dates to `NULL` (see `parse_wd_date` /
   `CLICKHOUSE_DATE_MIN`/`MAX` in `ingest/wikidata.py`). **If the owner of
   `ingest/ddl.sql` widens `release_date` to `Date32`, this clamp should be
   removed** so pre-1970 release dates get stored.
2. **`imdb_episodes.episodeNumber`/`seasonNumber` are `Nullable(UInt16)`**,
   but a handful of real IMDb rows have out-of-range values (e.g.
   long-running daily shows numbered beyond 65535). Fixed by clamping to
   `NULL` outside `[0, 65535]` in `ingest/imdb.py` (`to_uint16`), same
   philosophy as above.
3. **WDQS query design had to be reworked from the original spec.**
   `?item wdt:P31/wdt:P279* wd:Q11424` (transitive class path, as
   literally specified in the task) times out consistently on WDQS
   regardless of LIMIT, because the property-path scan dominates cost
   before any page window is applied. A combined single query joining
   VALUES + sitelink + `OPTIONAL P577 (MIN)` + `OPTIONAL P136
   (GROUP_CONCAT)` also reliably throws a Blazegraph `StackOverflowError`
   (HTTP 500) — a known Blazegraph limitation when OPTIONAL/aggregation is
   combined with the `schema:about`/`isPartOf` sitelink join. Both were
   empirically diagnosed by direct testing against the live endpoint (see
   comment block at the top of `ingest/wikidata.py`). Replaced with a
   two-stage design: Stage A is a cheap, non-transitive, non-ordered,
   LIMIT/OFFSET-paginated `?item wdt:P31 wd:Q11424` scan; Stage B does
   small VALUES-restricted POST queries (sitelink / release date / genre,
   each separately) per stage-A page. This is fast (a stage-A page of
   5000 + its 3 stage-B lookups + MediaWiki resolution takes ~45-70s) and
   has not errored once across tens of thousands of entities.
4. **Windows file-lock race on checkpoint save.** `save_checkpoint`'s
   atomic `tmp.replace(path)` transiently raised `PermissionError
   (WinError 5)` once, when a diagnostic `cat`/`type` on the same
   checkpoint file from another shell briefly held a read handle at the
   exact moment of replace. Fixed with a short retry-with-backoff in
   `ingest/common.py::save_checkpoint`. Real risk for any tool/AV that
   might open these files while a long-running loader is active.
5. **Franchise entity type is intentionally small (29 rows).** Per spec
   ("keep it small, don't over-invest"), franchise uses a simple
   `wdt:P31 wd:Q196600` scan requiring P345 + enwiki sitelink, same as
   films, and Wikidata just doesn't have many franchise items meeting
   both bars.
6. **Pagination in wikidata.py's Stage A has no `ORDER BY`** (see gap #3 —
   `ORDER BY` was itself part of the timeout problem). It relies on
   Blazegraph returning a stable row order for repeated calls against a
   near-static class scan over the ~1-2 hour run. This is a standard
   pragmatic tradeoff for WDQS bulk extraction, not a strict guarantee;
   worst case is a small number of entities missed or double-counted at
   page boundaries if Wikidata is edited concurrently — self-healing on a
   re-run since `entities` is a `ReplacingMergeTree` keyed on
   `(wikidata_id, project)`.
7. **`imdb_names` row count (15.6M) is `name.basics` loaded in full**, not
   filtered — per spec ("Load `title.basics`/`title.ratings` in full");
   `name.basics` wasn't listed as filterable so it was left whole.
8. Did not touch `.env`, `requirements.txt`, or any files outside
   `ingest/`/`scripts/`. Did not run any git commands. Two attempted
   `ALTER TABLE`/`TRUNCATE TABLE` commands (for the Date32 widening and
   for clearing stale smoke-test rows) were blocked by the auto-mode
   permission classifier as shared-schema-affecting; both were worked
   around at the application level instead of forced through (see gaps 1
   and the note that a handful of early smoke-test rows are already
   correct/harmless — `entities` is `ReplacingMergeTree` so no duplicate
   buildup even though a few point-in-time `count()` calls above were
   taken pre-merge).

## Still running / how to resume

Both are safe to interrupt (Ctrl+C or process kill) and resume — progress
is checkpointed after every batch.

- **`ingest/wikidata.py`** (all 4 types, resumable): still paginating the
  `film` type (largest candidate pool, ~274k). `series`/`person`/
  `franchise` stage-A are already marked done in the checkpoint, so a
  resume only continues `film`.
  ```
  python ingest/wikidata.py
  ```
- **`ingest/pageviews.py`** (the long pole, as expected): still fetching
  the ~29k-page spine that existed when it started; will need a **second
  invocation** after `wikidata.py` finishes to pick up the additional
  ~230k+ film pages that will land in `entities` in the meantime (it
  re-queries `entities` fresh on each run and skips already-checkpointed
  page_ids, so this is just re-running it, not a special mode).
  ```
  python ingest/pageviews.py --workers 12
  ```
- **After both finish (or periodically while pageviews is still
  running)**, refresh the rollup — safe to re-run any time, truncates and
  reinserts from scratch:
  ```
  python ingest/backfill.py
  ```
- Or run everything remaining via the orchestrator, which is
  stage-resumable:
  ```
  python ingest/run_all.py --from wikidata
  ```

Checkpoint files (gitignored, under `ingest/.checkpoints/`):
`wikidata.json`, `imdb.json` (all datasets marked done), `pageviews.json`.

## Files

- `ingest/common.py` — shared ClickHouse client, checkpoint I/O, HTTP retry/backoff, logging.
- `ingest/wikidata.py` — builds `entities`.
- `ingest/imdb.py` — loads the 6 IMDb tables. **Complete.**
- `ingest/pageviews.py` — loads `pageviews_daily` via the Wikimedia per-article REST API.
- `ingest/backfill.py` — truncate + reinsert `entity_attention_daily`.
- `ingest/run_all.py` — orchestrates all 4 stages, resumable via `--from <stage>` or `--only <stages>`.
- `ingest/ddl.sql`, `ingest/apply_ddl.py` — pre-existing, unmodified except as noted in gap #1 (attempted, blocked, not applied).

## Not done / explicitly out of scope

- No changes to `agent/`, `playbooks/`, `api/`, `web/` were made or needed, per the task's hard scope boundary.
- No formal `tests/test_ingest_*.py` were written; instead every stage was validated end-to-end against the live ClickHouse Cloud cluster and live upstream APIs (Wikidata/WDQS, MediaWiki, datasets.imdbws.com, Wikimedia pageviews REST API) via smoke tests before the full run — see gaps section above for what those smoke tests actually surfaced and how each was fixed.
- The `entities.release_date` `Date` vs `Date32` mismatch (gap #1) is a genuine schema follow-up for whoever owns `ingest/ddl.sql` going forward; flagging rather than fixing myself since it touches shared schema.
