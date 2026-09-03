"""ingest/imdb.py - downloads and loads IMDb TSV.GZ datasets into ClickHouse.

Downloads from https://datasets.imdbws.com/ into ingest/.cache/ (gitignored),
parses chunked (gzip streamed, tab-separated, \\N = NULL), and bulk-inserts
into imdb_titles, imdb_ratings, imdb_principals, imdb_names, imdb_crew,
imdb_episodes in ~100k-row batches.

To keep volume manageable, title.basics/title.principals/title.crew/
title.episode are restricted to titleType in
(movie, tvSeries, tvMiniSeries, short, tvMovie), and title.principals is
further filtered to tconsts that survived that filter. title.ratings and
name.basics are loaded in full (they're small/keyed and cheap to keep whole).

Resumable via ingest/.checkpoints/imdb.json: each dataset is marked
downloaded and loaded independently, so re-running skips finished work.

Usage:
    python ingest/imdb.py                  # all datasets
    python ingest/imdb.py --datasets title.basics,title.ratings
"""
from __future__ import annotations

import argparse
import csv
import gzip
import sys
from pathlib import Path
from typing import Callable, Iterable

import requests

from common import CACHE_DIR, get_client, load_checkpoint, log, request_with_retry, save_checkpoint

BASE_URL = "https://datasets.imdbws.com"
CHECKPOINT_NAME = "imdb"
INSERT_BATCH = 100_000

KEEP_TITLE_TYPES = {"movie", "tvSeries", "tvMiniSeries", "short", "tvMovie"}

DATASETS = [
    "title.basics",
    "title.ratings",
    "title.principals",
    "title.crew",
    "title.episode",
    "name.basics",
]


def nn(v: str) -> str | None:
    """Null-normalize an IMDb TSV field."""
    return None if v == r"\N" else v


def to_uint(v: str) -> int | None:
    v = nn(v)
    if v is None:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def to_uint16(v: str) -> int | None:
    """Like to_uint but clamps to NULL outside UInt16 range (0-65535).
    A handful of real IMDb rows have out-of-range season/episode numbers
    (e.g. long-running daily shows numbering episodes in the tens of
    thousands+); imdb_episodes.seasonNumber/episodeNumber are
    Nullable(UInt16), so we drop rather than corrupt/crash on these."""
    n = to_uint(v)
    if n is None:
        return None
    if n < 0 or n > 65535:
        return None
    return n


def to_float(v: str) -> float | None:
    v = nn(v)
    if v is None:
        return None
    try:
        return float(v)
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Download
# --------------------------------------------------------------------------

def download(dataset: str, checkpoint: dict) -> Path:
    dest = CACHE_DIR / f"{dataset}.tsv.gz"
    stage = checkpoint.setdefault("downloaded", {})
    if stage.get(dataset) and dest.exists():
        log(f"[imdb] {dataset}: already downloaded ({dest.stat().st_size} bytes), skipping")
        return dest

    url = f"{BASE_URL}/{dataset}.tsv.gz"
    log(f"[imdb] downloading {url} -> {dest}")
    resp = request_with_retry("GET", url, stream=True, timeout=120, max_retries=6)
    if resp is None or resp.status_code != 200:
        raise RuntimeError(f"Failed to download {url}: {resp.status_code if resp else 'no response'}")

    tmp = dest.with_suffix(".gz.part")
    total = 0
    with open(tmp, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
                total += len(chunk)
    tmp.replace(dest)
    log(f"[imdb] downloaded {dataset}: {total} bytes")
    stage[dataset] = True
    save_checkpoint(CHECKPOINT_NAME, checkpoint)
    return dest


# --------------------------------------------------------------------------
# Row iteration
# --------------------------------------------------------------------------

def iter_tsv_rows(path: Path) -> Iterable[dict]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        for row in reader:
            yield row


# --------------------------------------------------------------------------
# Per-dataset load functions
# --------------------------------------------------------------------------

def load_title_basics(client, path: Path, checkpoint: dict) -> set[str]:
    """Loads title.basics filtered to KEEP_TITLE_TYPES. Returns the set of
    surviving tconsts, so title.principals/crew/episode can be filtered too."""
    cols = ["tconst", "titleType", "primaryTitle", "originalTitle", "isAdult", "startYear", "endYear", "runtimeMinutes", "genres"]
    kept_tconsts: set[str] = set()
    batch = []
    skip_rows = checkpoint.get("loaded_rows", {}).get("title.basics", 0)
    row_idx = 0
    inserted = checkpoint.get("loaded_rows", {}).get("title.basics", 0)
    for row in iter_tsv_rows(path):
        row_idx += 1
        if row["titleType"] not in KEEP_TITLE_TYPES:
            continue
        kept_tconsts.add(row["tconst"])
        if row_idx <= skip_rows:
            continue
        batch.append((
            row["tconst"],
            row["titleType"],
            row["primaryTitle"],
            row["originalTitle"],
            to_uint(row["isAdult"]) or 0,
            to_uint(row["startYear"]),
            to_uint(row["endYear"]),
            to_uint(row["runtimeMinutes"]),
            nn(row["genres"]) or "",
        ))
        if len(batch) >= INSERT_BATCH:
            client.insert("imdb_titles", batch, column_names=cols)
            inserted += len(batch)
            batch = []
            checkpoint.setdefault("loaded_rows", {})["title.basics"] = row_idx
            save_checkpoint(CHECKPOINT_NAME, checkpoint)
            log(f"  [title.basics] {row_idx} rows scanned, {inserted} inserted, {len(kept_tconsts)} kept tconsts so far")
    if batch:
        client.insert("imdb_titles", batch, column_names=cols)
        inserted += len(batch)
    checkpoint.setdefault("loaded_rows", {})["title.basics"] = row_idx
    checkpoint["title_basics_done"] = True
    save_checkpoint(CHECKPOINT_NAME, checkpoint)
    log(f"[imdb] title.basics done: {inserted} rows inserted, {len(kept_tconsts)} kept tconsts")
    return kept_tconsts


def get_kept_tconsts(client) -> set[str]:
    rows = client.query("SELECT tconst FROM cinesignal.imdb_titles").result_rows
    return {r[0] for r in rows}


def load_title_ratings(client, path: Path, checkpoint: dict) -> None:
    cols = ["tconst", "averageRating", "numVotes"]
    batch = []
    row_idx = 0
    skip_rows = checkpoint.get("loaded_rows", {}).get("title.ratings", 0)
    inserted = skip_rows
    for row in iter_tsv_rows(path):
        row_idx += 1
        if row_idx <= skip_rows:
            continue
        batch.append((row["tconst"], to_float(row["averageRating"]) or 0.0, to_uint(row["numVotes"]) or 0))
        if len(batch) >= INSERT_BATCH:
            client.insert("imdb_ratings", batch, column_names=cols)
            inserted += len(batch)
            batch = []
            checkpoint.setdefault("loaded_rows", {})["title.ratings"] = row_idx
            save_checkpoint(CHECKPOINT_NAME, checkpoint)
            log(f"  [title.ratings] {row_idx} rows scanned, {inserted} inserted")
    if batch:
        client.insert("imdb_ratings", batch, column_names=cols)
        inserted += len(batch)
    checkpoint.setdefault("loaded_rows", {})["title.ratings"] = row_idx
    save_checkpoint(CHECKPOINT_NAME, checkpoint)
    log(f"[imdb] title.ratings done: {inserted} rows inserted")


def load_title_principals(client, path: Path, checkpoint: dict, keep_tconsts: set[str]) -> None:
    cols = ["tconst", "ordering", "nconst", "category", "job", "characters"]
    batch = []
    row_idx = 0
    skip_rows = checkpoint.get("loaded_rows", {}).get("title.principals", 0)
    inserted = skip_rows
    for row in iter_tsv_rows(path):
        row_idx += 1
        if row_idx <= skip_rows:
            continue
        if keep_tconsts and row["tconst"] not in keep_tconsts:
            continue
        batch.append((
            row["tconst"],
            to_uint(row["ordering"]) or 0,
            row["nconst"],
            nn(row["category"]) or "",
            nn(row["job"]) or "",
            nn(row["characters"]) or "",
        ))
        if len(batch) >= INSERT_BATCH:
            client.insert("imdb_principals", batch, column_names=cols)
            inserted += len(batch)
            batch = []
            checkpoint.setdefault("loaded_rows", {})["title.principals"] = row_idx
            save_checkpoint(CHECKPOINT_NAME, checkpoint)
            log(f"  [title.principals] {row_idx} rows scanned, {inserted} inserted")
    if batch:
        client.insert("imdb_principals", batch, column_names=cols)
        inserted += len(batch)
    checkpoint.setdefault("loaded_rows", {})["title.principals"] = row_idx
    save_checkpoint(CHECKPOINT_NAME, checkpoint)
    log(f"[imdb] title.principals done: {inserted} rows inserted")


def load_title_crew(client, path: Path, checkpoint: dict, keep_tconsts: set[str]) -> None:
    cols = ["tconst", "directors", "writers"]
    batch = []
    row_idx = 0
    skip_rows = checkpoint.get("loaded_rows", {}).get("title.crew", 0)
    inserted = skip_rows
    for row in iter_tsv_rows(path):
        row_idx += 1
        if row_idx <= skip_rows:
            continue
        if keep_tconsts and row["tconst"] not in keep_tconsts:
            continue
        batch.append((row["tconst"], nn(row["directors"]) or "", nn(row["writers"]) or ""))
        if len(batch) >= INSERT_BATCH:
            client.insert("imdb_crew", batch, column_names=cols)
            inserted += len(batch)
            batch = []
            checkpoint.setdefault("loaded_rows", {})["title.crew"] = row_idx
            save_checkpoint(CHECKPOINT_NAME, checkpoint)
            log(f"  [title.crew] {row_idx} rows scanned, {inserted} inserted")
    if batch:
        client.insert("imdb_crew", batch, column_names=cols)
        inserted += len(batch)
    checkpoint.setdefault("loaded_rows", {})["title.crew"] = row_idx
    save_checkpoint(CHECKPOINT_NAME, checkpoint)
    log(f"[imdb] title.crew done: {inserted} rows inserted")


def load_title_episode(client, path: Path, checkpoint: dict, keep_tconsts: set[str]) -> None:
    cols = ["tconst", "parentTconst", "seasonNumber", "episodeNumber"]
    batch = []
    row_idx = 0
    skip_rows = checkpoint.get("loaded_rows", {}).get("title.episode", 0)
    inserted = skip_rows
    for row in iter_tsv_rows(path):
        row_idx += 1
        if row_idx <= skip_rows:
            continue
        # keep episode if its parent series survived the titleType filter
        if keep_tconsts and row["parentTconst"] not in keep_tconsts:
            continue
        batch.append((row["tconst"], row["parentTconst"], to_uint16(row["seasonNumber"]), to_uint16(row["episodeNumber"])))
        if len(batch) >= INSERT_BATCH:
            client.insert("imdb_episodes", batch, column_names=cols)
            inserted += len(batch)
            batch = []
            checkpoint.setdefault("loaded_rows", {})["title.episode"] = row_idx
            save_checkpoint(CHECKPOINT_NAME, checkpoint)
            log(f"  [title.episode] {row_idx} rows scanned, {inserted} inserted")
    if batch:
        client.insert("imdb_episodes", batch, column_names=cols)
        inserted += len(batch)
    checkpoint.setdefault("loaded_rows", {})["title.episode"] = row_idx
    save_checkpoint(CHECKPOINT_NAME, checkpoint)
    log(f"[imdb] title.episode done: {inserted} rows inserted")


def load_name_basics(client, path: Path, checkpoint: dict) -> None:
    cols = ["nconst", "primaryName", "birthYear", "deathYear", "primaryProfession", "knownForTitles"]
    batch = []
    row_idx = 0
    skip_rows = checkpoint.get("loaded_rows", {}).get("name.basics", 0)
    inserted = skip_rows
    for row in iter_tsv_rows(path):
        row_idx += 1
        if row_idx <= skip_rows:
            continue
        batch.append((
            row["nconst"],
            row["primaryName"],
            to_uint(row["birthYear"]),
            to_uint(row["deathYear"]),
            nn(row["primaryProfession"]) or "",
            nn(row["knownForTitles"]) or "",
        ))
        if len(batch) >= INSERT_BATCH:
            client.insert("imdb_names", batch, column_names=cols)
            inserted += len(batch)
            batch = []
            checkpoint.setdefault("loaded_rows", {})["name.basics"] = row_idx
            save_checkpoint(CHECKPOINT_NAME, checkpoint)
            log(f"  [name.basics] {row_idx} rows scanned, {inserted} inserted")
    if batch:
        client.insert("imdb_names", batch, column_names=cols)
        inserted += len(batch)
    checkpoint.setdefault("loaded_rows", {})["name.basics"] = row_idx
    save_checkpoint(CHECKPOINT_NAME, checkpoint)
    log(f"[imdb] name.basics done: {inserted} rows inserted")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--datasets", default=",".join(DATASETS))
    args = parser.parse_args()
    wanted = [d.strip() for d in args.datasets.split(",") if d.strip()]

    client = get_client()
    checkpoint = load_checkpoint(CHECKPOINT_NAME)
    loaded_flag = checkpoint.setdefault("loaded_done", {})

    paths = {}
    for d in wanted:
        paths[d] = download(d, checkpoint)

    keep_tconsts: set[str] = set()

    if "title.basics" in wanted:
        if loaded_flag.get("title.basics"):
            log("[imdb] title.basics already loaded, fetching kept tconsts from ClickHouse")
            keep_tconsts = get_kept_tconsts(client)
        else:
            keep_tconsts = load_title_basics(client, paths["title.basics"], checkpoint)
            loaded_flag["title.basics"] = True
            save_checkpoint(CHECKPOINT_NAME, checkpoint)
    elif any(d in wanted for d in ("title.principals", "title.crew", "title.episode")):
        # need the filter set even if title.basics wasn't requested this run
        try:
            keep_tconsts = get_kept_tconsts(client)
            log(f"[imdb] loaded {len(keep_tconsts)} kept tconsts from existing imdb_titles")
        except Exception as exc:  # noqa: BLE001
            log(f"[imdb] could not fetch kept tconsts ({exc}); proceeding unfiltered")

    if "title.ratings" in wanted:
        if loaded_flag.get("title.ratings"):
            log("[imdb] title.ratings already loaded, skipping")
        else:
            load_title_ratings(client, paths["title.ratings"], checkpoint)
            loaded_flag["title.ratings"] = True
            save_checkpoint(CHECKPOINT_NAME, checkpoint)

    if "title.principals" in wanted:
        if loaded_flag.get("title.principals"):
            log("[imdb] title.principals already loaded, skipping")
        else:
            load_title_principals(client, paths["title.principals"], checkpoint, keep_tconsts)
            loaded_flag["title.principals"] = True
            save_checkpoint(CHECKPOINT_NAME, checkpoint)

    if "title.crew" in wanted:
        if loaded_flag.get("title.crew"):
            log("[imdb] title.crew already loaded, skipping")
        else:
            load_title_crew(client, paths["title.crew"], checkpoint, keep_tconsts)
            loaded_flag["title.crew"] = True
            save_checkpoint(CHECKPOINT_NAME, checkpoint)

    if "title.episode" in wanted:
        if loaded_flag.get("title.episode"):
            log("[imdb] title.episode already loaded, skipping")
        else:
            load_title_episode(client, paths["title.episode"], checkpoint, keep_tconsts)
            loaded_flag["title.episode"] = True
            save_checkpoint(CHECKPOINT_NAME, checkpoint)

    if "name.basics" in wanted:
        if loaded_flag.get("name.basics"):
            log("[imdb] name.basics already loaded, skipping")
        else:
            load_name_basics(client, paths["name.basics"], checkpoint)
            loaded_flag["name.basics"] = True
            save_checkpoint(CHECKPOINT_NAME, checkpoint)

    log("[imdb] ALL DONE")


if __name__ == "__main__":
    main()
