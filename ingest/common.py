"""Shared helpers for the CineSignal ingest pipeline.

Kept dependency-light and self-contained so each stage script
(wikidata.py, imdb.py, pageviews.py, backfill.py, run_all.py) can import
from here without circular concerns.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
import clickhouse_connect
import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "ingest" / ".cache"
CHECKPOINT_DIR = ROOT / "ingest" / ".checkpoints"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = "CineSignal/1.0 (hackathon project; https://github.com/HarshdipSaha/cinesignal)"


def get_client():
    """Return a fresh clickhouse-connect client using creds from .env."""
    load_dotenv(ROOT / ".env")
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ["CLICKHOUSE_PORT"]),
        username=os.environ["CLICKHOUSE_USER"],
        password=os.environ["CLICKHOUSE_PASSWORD"],
        secure=True,
        database="cinesignal",
    )


# --------------------------------------------------------------------------
# Checkpointing
# --------------------------------------------------------------------------

def load_checkpoint(name: str) -> dict:
    path = CHECKPOINT_DIR / f"{name}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_checkpoint(name: str, data: dict) -> None:
    path = CHECKPOINT_DIR / f"{name}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    # os.replace can transiently fail on Windows (PermissionError/WinError 5)
    # if another process briefly holds a read handle on the destination
    # (e.g. a `cat`/`type` for diagnostics, an AV scan, a backup indexer).
    # Retry a few times with a short backoff rather than crashing a long
    # running ingest job over a momentary lock.
    last_exc: Exception | None = None
    for attempt in range(5):
        try:
            tmp.replace(path)
            return
        except PermissionError as exc:
            last_exc = exc
            time.sleep(0.2 * (attempt + 1))
    if last_exc:
        raise last_exc


# --------------------------------------------------------------------------
# HTTP with retry/backoff for shared infra (WMF, WDQS, MediaWiki, imdbws)
# --------------------------------------------------------------------------

def request_with_retry(
    method: str,
    url: str,
    *,
    max_retries: int = 6,
    backoff_base: float = 1.5,
    timeout: float = 60.0,
    session: requests.Session | None = None,
    **kwargs: Any,
) -> requests.Response | None:
    """GET/etc with retry on 429/5xx and network errors. Returns None on
    permanent 404 (caller should treat as "no data"). Raises on other
    persistent failures after exhausting retries."""
    sess = session or requests
    headers = kwargs.pop("headers", {}) or {}
    headers.setdefault("User-Agent", USER_AGENT)
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = sess.request(method, url, headers=headers, timeout=timeout, **kwargs)
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            time.sleep(backoff_base ** attempt)
            continue

        if resp.status_code == 404:
            return None
        if resp.status_code == 429 or resp.status_code >= 500:
            retry_after = resp.headers.get("Retry-After")
            sleep_s = float(retry_after) if retry_after and retry_after.isdigit() else backoff_base ** attempt
            time.sleep(min(sleep_s, 60))
            continue
        return resp
    if last_exc:
        raise last_exc
    return resp  # last non-2xx response after exhausting retries


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)
