"""ingest/pageviews.py - loads per-article daily pageviews from the Wikimedia
Pageviews REST API into cinesignal.pageviews_daily.

For every distinct (page_id, page_title) in cinesignal.entities (project is
always en.wikipedia, since wikidata.py only pulls enwiki sitelinks), fetches
the full daily series for START_DATE..END_DATE in one call per page:

  https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/
      {project}/{access}/{agent}/{article}/{granularity}/{start}/{end}

404 (no pageview data for that page) is skipped silently -- common for
lesser-known pages or pages created after the range. 429/5xx are retried
with backoff via common.request_with_retry.

Resumable: completed page_ids are checkpointed to
ingest/.checkpoints/pageviews.json after every buffer flush, so a re-run
skips pages already fetched (success, no-data, or permanent-fail alike).

Usage:
    python ingest/pageviews.py
    python ingest/pageviews.py --workers 12 --smoke-test
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from urllib.parse import quote

import requests

from common import get_client, load_checkpoint, log, request_with_retry, save_checkpoint

API_BASE = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
PROJECT = "en.wikipedia"
ACCESS = "all-access"
AGENT = "user"
GRANULARITY = "daily"
START_DATE = "20230901"
END_DATE = "20260901"

CHECKPOINT_NAME = "pageviews"
INSERT_BATCH = 50_000
DEFAULT_WORKERS = 12
PROGRESS_EVERY = 200


def build_url(title: str) -> str:
    article = quote(title.replace(" ", "_"), safe="")
    return f"{API_BASE}/{PROJECT}/{ACCESS}/{AGENT}/{article}/{GRANULARITY}/{START_DATE}/{END_DATE}"


def fetch_page_series(page_id: int, title: str, session: requests.Session) -> list[tuple]:
    """Returns list of (page_id, project, date, views) rows. Empty list on
    404 / no data. Raises on persistent non-404 failure."""
    url = build_url(title)
    resp = request_with_retry("GET", url, session=session, max_retries=6, timeout=30)
    if resp is None:
        return []  # 404: no pageview data for this page
    if resp.status_code != 200:
        raise RuntimeError(f"pageviews API HTTP {resp.status_code} for {title!r}: {resp.text[:200]}")
    data = resp.json()
    rows = []
    for item in data.get("items", []):
        ts = item["timestamp"]  # YYYYMMDDHH
        d = date(int(ts[0:4]), int(ts[4:6]), int(ts[6:8]))
        rows.append((page_id, PROJECT, d, int(item["views"])))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--smoke-test", action="store_true", help="only process ~300 pages")
    args = parser.parse_args()

    client = get_client()
    checkpoint = load_checkpoint(CHECKPOINT_NAME)
    done_ids = set(checkpoint.get("done_page_ids", []))
    total_rows_inserted = checkpoint.get("total_rows_inserted", 0)

    log("[pageviews] fetching distinct (page_id, page_title) spine from entities ...")
    rows = client.query(
        "SELECT page_id, any(page_title) AS page_title FROM cinesignal.entities "
        "WHERE project = 'en.wikipedia' GROUP BY page_id"
    ).result_rows
    spine = [(int(pid), title) for pid, title in rows]
    log(f"[pageviews] spine size: {len(spine)} distinct pages; {len(done_ids)} already done from checkpoint")

    todo = [(pid, title) for pid, title in spine if pid not in done_ids]
    if args.smoke_test:
        todo = todo[:300]
    log(f"[pageviews] {len(todo)} pages to fetch this run")

    if not todo:
        log("[pageviews] nothing to do, all pages already fetched")
        return

    session = requests.Session()
    buffer_lock = threading.Lock()
    buffer: list[tuple] = []
    newly_done: set[int] = set()

    start_time = time.time()
    processed = 0
    errors = 0

    def flush(force: bool = False):
        nonlocal buffer, total_rows_inserted
        with buffer_lock:
            if not buffer or (len(buffer) < INSERT_BATCH and not force):
                return
            to_insert = buffer
            buffer = []
        if to_insert:
            client.insert(
                "pageviews_daily",
                to_insert,
                column_names=["page_id", "project", "date", "views"],
            )
            total_rows_inserted += len(to_insert)
        checkpoint["done_page_ids"] = sorted(done_ids | newly_done)
        checkpoint["total_rows_inserted"] = total_rows_inserted
        save_checkpoint(CHECKPOINT_NAME, checkpoint)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fetch_page_series, pid, title, session): pid for pid, title in todo}
        for fut in as_completed(futures):
            pid = futures[fut]
            processed += 1
            try:
                rows = fut.result()
                with buffer_lock:
                    buffer.extend(rows)
                newly_done.add(pid)
            except Exception as exc:  # noqa: BLE001
                errors += 1
                log(f"  [pageviews] FAILED page_id={pid}: {exc}")
                # do not mark done -- resumable retry on next run
                continue

            if len(buffer) >= INSERT_BATCH:
                flush()

            if processed % PROGRESS_EVERY == 0:
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                log(
                    f"[pageviews] {processed}/{len(todo)} pages done "
                    f"({rate:.2f} pages/sec, {total_rows_inserted} rows inserted so far, {errors} errors)"
                )

    flush(force=True)
    elapsed = time.time() - start_time
    log(
        f"[pageviews] RUN DONE: {processed} pages processed, {errors} errors, "
        f"{total_rows_inserted} total rows inserted, {elapsed:.0f}s elapsed"
    )


if __name__ == "__main__":
    main()
