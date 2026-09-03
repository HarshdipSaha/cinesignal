"""ingest/backfill.py - idempotently repopulate entity_attention_daily.

The materialized view cinesignal.entity_attention_daily_mv only catches rows
inserted into pageviews_daily AFTER the MV was created, so after any
pageviews load we must truncate-and-reinsert the rollup from scratch. This
is always safe to re-run.

Usage: python ingest/backfill.py
"""
from __future__ import annotations

from common import get_client, log

TRUNCATE_SQL = "TRUNCATE TABLE cinesignal.entity_attention_daily"

INSERT_SQL = """
INSERT INTO cinesignal.entity_attention_daily
SELECT
    e.wikidata_id AS wikidata_id,
    p.project     AS project,
    p.date        AS date,
    sum(p.views)  AS views
FROM cinesignal.pageviews_daily AS p
INNER JOIN cinesignal.entities AS e
    ON p.page_id = e.page_id AND p.project = e.project
GROUP BY e.wikidata_id, p.project, p.date
"""


def main() -> None:
    client = get_client()

    before = client.query("SELECT count() FROM cinesignal.entity_attention_daily").result_rows[0][0]
    log(f"[backfill] entity_attention_daily before: {before} rows")

    log("[backfill] truncating cinesignal.entity_attention_daily")
    client.command(TRUNCATE_SQL)

    log("[backfill] reinserting from pageviews_daily JOIN entities ...")
    client.command(INSERT_SQL)

    after = client.query("SELECT count() FROM cinesignal.entity_attention_daily").result_rows[0][0]
    log(f"[backfill] entity_attention_daily after: {after} rows")
    log("[backfill] DONE")


if __name__ == "__main__":
    main()
