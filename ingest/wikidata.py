"""ingest/wikidata.py - builds the cinesignal.entities spine.

Pulls films, TV series, film-industry people, and a best-effort franchise
set from the Wikidata Query Service, requiring an IMDb id (P345) and an
enwiki sitelink on every entity. Resolves enwiki page_title -> page_id via
the MediaWiki API, and inserts into ClickHouse `entities` in batches.

Query strategy (empirically tuned against live WDQS -- see notes below):

  Stage A: a *simple* two-triple-pattern query (P31 direct class + P345),
  with NO ORDER BY and NO sitelink join, paginated via LIMIT/OFFSET. This
  is cheap (a few seconds even at deep offsets for a 270k-row class like
  film) because WDQS/Blazegraph doesn't have to compute a full sort or a
  wide join before applying the page window.

  Stage B: for each stage-A page (a batch of QIDs), a handful of small
  POST queries restricted to those QIDs via VALUES -- one for the enwiki
  sitelink title, one (film/series only) for raw P577 rows (release date;
  MIN is done in Python, not SPARQL), and one (film/series only) for P136
  genre labels (GROUP_CONCAT is fine here on its own).

  Two things were tried and empirically rejected during development:
    - `?item wdt:P31/wdt:P279* wd:Q11424` (transitive class path): times
      out consistently, even at LIMIT 500, because the property path scan
      dominates cost regardless of page size.
    - A single combined query joining VALUES + sitelink + OPTIONAL P577
      (MIN) + OPTIONAL P136 (GROUP_CONCAT) in one GROUP BY: reliably
      throws a Blazegraph `StackOverflowError` (HTTP 500) -- a known
      Blazegraph limitation when OPTIONAL/aggregation is combined with
      the schema:about/isPartOf sitelink join. Splitting into separate
      un-aggregated (or singly-aggregated) queries avoids it entirely.

Because Stage A has no ORDER BY, pagination is not strictly guaranteed
stable across calls if Wikidata is edited mid-scan; in practice this is
fine for a bulk spine build that takes on the order of an hour.

Resumable: progress checkpointed to ingest/.checkpoints/wikidata.json
(stage-A pagination offset per type).

Usage:
    python ingest/wikidata.py                     # full run, all types
    python ingest/wikidata.py --types film,series  # only these types
    python ingest/wikidata.py --smoke-test         # tiny run to sanity-check
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Iterable

import requests

from common import get_client, load_checkpoint, log, request_with_retry, save_checkpoint

WDQS_URL = "https://query.wikidata.org/sparql"
MW_API_URL = "https://en.wikipedia.org/w/api.php"

CHECKPOINT_NAME = "wikidata"
PAGE_SIZE = 5000
OFFSET_FLOOR = 500  # smallest page we'll fall back to on repeated stage-A failure

# Wikidata class QIDs
Q_FILM = "Q11424"
Q_TV_SERIES = "Q5398426"
Q_FRANCHISE = "Q196600"
OCCUPATIONS = ["Q33999", "Q2526255", "Q3282637", "Q28389"]  # actor, director, producer, screenwriter

ENTITY_TYPES = ["film", "series", "person", "franchise"]
PROJECT = "en.wikipedia"
HAS_GENRE_RELEASE = {"film", "series"}

INSERT_BATCH = 5000
MW_WORKERS = 10


def chunked(seq: list, n: int) -> Iterable[list]:
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def qid_from_uri(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


# --------------------------------------------------------------------------
# SPARQL plumbing
# --------------------------------------------------------------------------

def sparql_get(query: str, timeout: int = 55) -> dict:
    resp = request_with_retry(
        "GET", WDQS_URL,
        params={"query": query, "format": "json"},
        headers={"Accept": "application/sparql-results+json"},
        timeout=timeout, max_retries=3,
    )
    if resp is None:
        raise RuntimeError("WDQS returned 404 (unexpected)")
    if resp.status_code != 200:
        raise RuntimeError(f"WDQS GET HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def sparql_post(query: str, timeout: int = 55) -> dict:
    resp = request_with_retry(
        "POST", WDQS_URL,
        data={"query": query, "format": "json"},
        headers={"Accept": "application/sparql-results+json", "Content-Type": "application/x-www-form-urlencoded"},
        timeout=timeout, max_retries=3,
    )
    if resp is None:
        raise RuntimeError("WDQS returned 404 (unexpected)")
    if resp.status_code != 200:
        raise RuntimeError(f"WDQS POST HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


# --------------------------------------------------------------------------
# Stage A: simple class+P345 pagination (no ORDER BY, no sitelink join)
# --------------------------------------------------------------------------

def stage_a_query(entity_type: str, limit: int, offset: int) -> str:
    if entity_type == "person":
        values = " ".join(f"wd:{q}" for q in OCCUPATIONS)
        return f"""
SELECT DISTINCT ?item ?tconst WHERE {{
  VALUES ?occ {{ {values} }}
  ?item wdt:P106 ?occ .
  ?item wdt:P345 ?tconst .
}}
LIMIT {limit} OFFSET {offset}
"""
    class_qid = {"film": Q_FILM, "series": Q_TV_SERIES, "franchise": Q_FRANCHISE}[entity_type]
    return f"""
SELECT ?item ?tconst WHERE {{
  ?item wdt:P31 wd:{class_qid} .
  ?item wdt:P345 ?tconst .
}}
LIMIT {limit} OFFSET {offset}
"""


def stage_a_pages(entity_type: str, checkpoint: dict):
    """Generator yielding (page, new_offset, is_last) tuples, one per
    stage-A page. `page` is a {qid: tconst} dict.

    IMPORTANT: this generator does NOT persist `new_offset`/done itself
    (other than for its own internal error-skip recovery, which never
    yields data). Persisting checkpoint progress for a *yielded* page is
    the caller's responsibility, and must only happen after the caller
    has successfully processed and inserted that page. Why: a Python
    generator only resumes the code *after* `yield` when the caller asks
    for the next item, so if the checkpoint save lived here (after
    yield), it would only run once the caller comes back for page N+1 --
    meaning any early `break` (e.g. --smoke-test) or an external kill of
    the process right after page N was fully processed would lose page
    N's already-completed progress, causing wasteful (though harmless,
    thanks to entities being a ReplacingMergeTree) reprocessing on
    resume. Having the caller persist `new_offset` itself, in the same
    step where it confirms the page was inserted, makes "this page is
    done" an atomic, immediately-durable fact instead of one deferred to
    the next loop iteration."""
    stage = checkpoint.setdefault("main", {}).setdefault(entity_type, {})
    if stage.get("done"):
        return
    offset = stage.get("offset", 0)
    limit = PAGE_SIZE
    consecutive_failures = 0
    while True:
        query = stage_a_query(entity_type, limit, offset)
        try:
            data = sparql_get(query)
        except Exception as exc:  # noqa: BLE001
            consecutive_failures += 1
            log(f"  [{entity_type}] stage-A query failed at offset={offset} limit={limit}: {exc}")
            if limit > OFFSET_FLOOR:
                limit = max(OFFSET_FLOOR, limit // 2)
                log(f"  [{entity_type}] retrying stage-A with smaller limit={limit}")
                continue
            if consecutive_failures >= 5:
                log(f"  [{entity_type}] giving up on stage-A at offset={offset} after repeated failures; skipping ahead by {OFFSET_FLOOR}")
                offset += OFFSET_FLOOR
                stage["offset"] = offset
                save_checkpoint(CHECKPOINT_NAME, checkpoint)
                consecutive_failures = 0
                limit = PAGE_SIZE
                continue
            time.sleep(5 * consecutive_failures)
            continue

        consecutive_failures = 0
        rows = data.get("results", {}).get("bindings", [])
        if not rows:
            stage["done"] = True
            save_checkpoint(CHECKPOINT_NAME, checkpoint)
            return

        page = {}
        for row in rows:
            qid = qid_from_uri(row["item"]["value"])
            page[qid] = row["tconst"]["value"]

        new_offset = offset + len(rows)
        is_last = len(rows) < limit
        yield page, new_offset, is_last

        # Resumes here only once the caller asks for the next page, i.e.
        # only after it has (per the contract above) already persisted
        # new_offset/is_last for the page we just yielded. Safe to adopt
        # as our own loop state and keep going.
        offset = new_offset
        if is_last:
            return
        limit = PAGE_SIZE


# --------------------------------------------------------------------------
# Stage B: VALUES-restricted lookups (sitelink / release date / genres)
# --------------------------------------------------------------------------

def _values_clause(qids: list[str]) -> str:
    return " ".join(f"wd:{q}" for q in qids)


def fetch_sitelinks(qids: list[str]) -> dict[str, str]:
    if not qids:
        return {}
    q = f"""
SELECT ?item ?sitelinkTitle WHERE {{
  VALUES ?item {{ {_values_clause(qids)} }}
  ?article schema:about ?item ;
           schema:isPartOf <https://en.wikipedia.org/> ;
           schema:name ?sitelinkTitle .
}}
"""
    try:
        data = sparql_post(q)
    except Exception as exc:  # noqa: BLE001
        log(f"  [stage-B sitelinks] failed for {len(qids)} qids: {exc}")
        return {}
    out = {}
    for row in data.get("results", {}).get("bindings", []):
        out[qid_from_uri(row["item"]["value"])] = row["sitelinkTitle"]["value"]
    return out


def fetch_release_dates(qids: list[str]) -> dict[str, "date"]:
    if not qids:
        return {}
    q = f"""
SELECT ?item ?releaseDate WHERE {{
  VALUES ?item {{ {_values_clause(qids)} }}
  ?item wdt:P577 ?releaseDate .
}}
"""
    try:
        data = sparql_post(q)
    except Exception as exc:  # noqa: BLE001
        log(f"  [stage-B release_dates] failed for {len(qids)} qids: {exc}")
        return {}
    out: dict[str, date] = {}
    for row in data.get("results", {}).get("bindings", []):
        qid = qid_from_uri(row["item"]["value"])
        d = parse_wd_date(row["releaseDate"]["value"])
        if d is None:
            continue
        if qid not in out or d < out[qid]:
            out[qid] = d
    return out


def fetch_genres(qids: list[str]) -> dict[str, str]:
    if not qids:
        return {}
    q = f"""
SELECT ?item (GROUP_CONCAT(DISTINCT ?genreLabel; separator=",") AS ?genres) WHERE {{
  VALUES ?item {{ {_values_clause(qids)} }}
  ?item wdt:P136 ?genre .
  ?genre rdfs:label ?genreLabel .
  FILTER(LANG(?genreLabel) = "en")
}}
GROUP BY ?item
"""
    try:
        data = sparql_post(q)
    except Exception as exc:  # noqa: BLE001
        log(f"  [stage-B genres] failed for {len(qids)} qids: {exc}")
        return {}
    out = {}
    for row in data.get("results", {}).get("bindings", []):
        qid = qid_from_uri(row["item"]["value"])
        genres = clean_genres(row.get("genres", {}).get("value", ""))
        if genres:
            out[qid] = genres
    return out


def clean_genres(raw: str) -> str:
    if not raw:
        return ""
    parts = [p.strip() for p in raw.split(",")]
    parts = [p for p in parts if p]
    seen, out = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return ",".join(out)


CLICKHOUSE_DATE_MIN = date(1970, 1, 1)
CLICKHOUSE_DATE_MAX = date(2149, 6, 6)


def parse_wd_date(raw: str) -> "date | None":
    """Parse a Wikidata P577 date. Returns None for unparseable values AND
    for dates outside ClickHouse's Date column range (1970-01-01 ..
    2149-06-06) -- the entities.release_date column is Nullable(Date), not
    Date32, so pre-1970 films (a real and common case) can't be stored
    exactly; we drop rather than corrupt/wrap them. See STATUS.md."""
    if not raw:
        return None
    try:
        d = date.fromisoformat(raw[:10])
    except ValueError:
        return None
    if d < CLICKHOUSE_DATE_MIN or d > CLICKHOUSE_DATE_MAX:
        return None
    return d


# --------------------------------------------------------------------------
# MediaWiki page_id resolution (parallelized)
# --------------------------------------------------------------------------

def _resolve_titles_chunk(chunk: list[str], session: requests.Session) -> dict[str, int]:
    params = {"action": "query", "titles": "|".join(chunk), "format": "json", "redirects": 1}
    resp = request_with_retry("GET", MW_API_URL, params=params, session=session, max_retries=5)
    if resp is None or resp.status_code != 200:
        return {}
    try:
        data = resp.json()
    except ValueError:
        return {}
    query = data.get("query", {})
    pages = query.get("pages", {})

    title_map = {t: t for t in chunk}
    for norm in query.get("normalized", []):
        frm, to = norm["from"], norm["to"]
        for orig, cur in list(title_map.items()):
            if cur == frm:
                title_map[orig] = to
    for red in query.get("redirects", []):
        frm, to = red["from"], red["to"]
        for orig, cur in list(title_map.items()):
            if cur == frm:
                title_map[orig] = to

    final_to_pageid: dict[str, int] = {}
    for pid, pinfo in pages.items():
        try:
            pid_int = int(pid)
        except ValueError:
            continue
        if pid_int < 0:
            continue
        final_to_pageid[pinfo["title"]] = pid_int

    result = {}
    for orig, final in title_map.items():
        if final in final_to_pageid:
            result[orig] = final_to_pageid[final]
    return result


def resolve_page_ids(titles: list[str], session: requests.Session) -> dict[str, int]:
    """Map original (sitelink) title -> enwiki page_id, following normalization
    and redirects. Titles with no resolvable page are omitted. Parallelized
    across chunks of 50 (MediaWiki API's max titles/call)."""
    result: dict[str, int] = {}
    chunks = list(chunked(titles, 50))
    if not chunks:
        return result
    with ThreadPoolExecutor(max_workers=MW_WORKERS) as pool:
        futures = [pool.submit(_resolve_titles_chunk, c, session) for c in chunks]
        for fut in as_completed(futures):
            try:
                result.update(fut.result())
            except Exception as exc:  # noqa: BLE001
                log(f"  [MW resolve] chunk failed: {exc}")
    return result


# --------------------------------------------------------------------------
# Main processing
# --------------------------------------------------------------------------

COLUMNS = [
    "wikidata_id", "page_id", "project", "page_title", "entity_type",
    "tconst", "nconst", "genres", "release_date",
]


def process_type(entity_type: str, client, checkpoint: dict, session: requests.Session, smoke_test: bool) -> int:
    # .setdefault (not .get!) so this is the SAME dict object stage_a_pages
    # attaches to checkpoint["main"][entity_type] -- we write stage["offset"]
    # directly below, and that write must land in the real checkpoint, not
    # an orphaned copy.
    stage = checkpoint.setdefault("main", {}).setdefault(entity_type, {})
    if stage.get("done"):
        log(f"[wikidata] {entity_type}: already complete per checkpoint")
        return checkpoint.get("counts", {}).get(entity_type, 0)

    total_inserted = checkpoint.get("counts", {}).get(entity_type, 0)
    log(f"[wikidata] {entity_type}: starting at stage-A offset={stage.get('offset', 0)}")

    for page, new_offset, is_last in stage_a_pages(entity_type, checkpoint):
        qids = list(page.keys())
        t0 = time.time()

        sitelink_map = fetch_sitelinks(qids)
        release_map = fetch_release_dates(qids) if entity_type in HAS_GENRE_RELEASE else {}
        genre_map = fetch_genres(qids) if entity_type in HAS_GENRE_RELEASE else {}

        titles = list(set(sitelink_map.values()))
        title_to_pageid = resolve_page_ids(titles, session)

        records = []
        for qid in qids:
            title = sitelink_map.get(qid)
            if title is None:
                continue
            page_id = title_to_pageid.get(title)
            if page_id is None:
                continue
            imdb_id = page[qid]
            tconst = imdb_id if entity_type != "person" else ""
            nconst = imdb_id if entity_type == "person" else ""
            genres = genre_map.get(qid, "")
            release_date = release_map.get(qid)
            records.append((qid, page_id, PROJECT, title, entity_type, tconst, nconst, genres, release_date))

        for batch in chunked(records, INSERT_BATCH):
            if batch:
                client.insert("entities", batch, column_names=COLUMNS)
                total_inserted += len(batch)

        # Persist progress for THIS page now, in the same step that
        # confirms it was inserted -- see stage_a_pages' docstring for why
        # this must not be deferred to a later generator resumption.
        stage["offset"] = new_offset
        if is_last:
            stage["done"] = True
        checkpoint.setdefault("counts", {})[entity_type] = total_inserted
        save_checkpoint(CHECKPOINT_NAME, checkpoint)
        log(
            f"  [{entity_type}] page: {len(qids)} qids -> {len(records)} resolved & inserted "
            f"(total so far: {total_inserted}, page took {time.time() - t0:.1f}s)"
        )

        if smoke_test and total_inserted >= 200:
            log(f"[wikidata] smoke-test cap reached for {entity_type}")
            break

    log(f"[wikidata] {entity_type} done: {total_inserted} entities inserted")
    return total_inserted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--types", default=",".join(ENTITY_TYPES), help="comma-separated subset of film,series,person,franchise")
    parser.add_argument("--smoke-test", action="store_true", help="tiny run to sanity-check end to end")
    args = parser.parse_args()

    types = [t.strip() for t in args.types.split(",") if t.strip()]
    for t in types:
        if t not in ENTITY_TYPES:
            print(f"Unknown entity type: {t}", file=sys.stderr)
            sys.exit(1)

    client = get_client()
    checkpoint = load_checkpoint(CHECKPOINT_NAME)
    session = requests.Session()

    grand_total = 0
    for t in types:
        grand_total += process_type(t, client, checkpoint, session, args.smoke_test)

    log(f"[wikidata] ALL DONE. Grand total entities inserted this run/resume: {grand_total}")


if __name__ == "__main__":
    main()
