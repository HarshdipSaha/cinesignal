"""ingest/run_all.py - orchestrates the full CineSignal ingest pipeline.

Stages, in order (each is independently resumable via its own checkpoint
file in ingest/.checkpoints/):
    1. wikidata.py   -- builds the entities spine
    2. imdb.py        -- loads IMDb catalog tables (independent of stage 1)
    3. pageviews.py   -- loads per-article daily pageviews (depends on entities)
    4. backfill.py    -- repopulates entity_attention_daily rollup

Usage:
    python ingest/run_all.py                      # full pipeline
    python ingest/run_all.py --from pageviews      # resume from a stage
    python ingest/run_all.py --only wikidata,imdb  # run only these stages
"""
from __future__ import annotations

import argparse
import runpy
import sys
import time
from pathlib import Path

from common import log

STAGES = ["wikidata", "imdb", "pageviews", "backfill"]
SCRIPT_DIR = Path(__file__).resolve().parent


def run_stage(name: str) -> None:
    script = SCRIPT_DIR / f"{name}.py"
    log(f"===== STAGE START: {name} ({script}) =====")
    t0 = time.time()
    old_argv = sys.argv
    sys.argv = [str(script)]
    try:
        runpy.run_path(str(script), run_name="__main__")
    finally:
        sys.argv = old_argv
    log(f"===== STAGE DONE: {name} ({time.time() - t0:.0f}s) =====")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="from_stage", default=None, help="resume starting at this stage")
    parser.add_argument("--only", default=None, help="comma-separated subset of stages to run")
    args = parser.parse_args()

    if args.only:
        stages = [s.strip() for s in args.only.split(",") if s.strip()]
    elif args.from_stage:
        if args.from_stage not in STAGES:
            print(f"Unknown stage: {args.from_stage}", file=sys.stderr)
            sys.exit(1)
        stages = STAGES[STAGES.index(args.from_stage):]
    else:
        stages = STAGES

    for s in stages:
        if s not in STAGES:
            print(f"Unknown stage: {s}", file=sys.stderr)
            sys.exit(1)

    log(f"[run_all] pipeline stages this run: {stages}")
    for stage in stages:
        run_stage(stage)
    log("[run_all] PIPELINE COMPLETE")


if __name__ == "__main__":
    main()
