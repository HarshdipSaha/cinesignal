-- Application-state tables (evidence chain + memo persistence).
-- Separate from ingest/ddl.sql (owned by the ingestion lane) — apply via
-- `python api/apply_state_ddl.py`. Idempotent.

CREATE TABLE IF NOT EXISTS cinesignal.query_log
(
    query_id     String,
    memo_id      String DEFAULT '',
    step_id      String,
    sql          String,
    params       String,   -- JSON-encoded param dict
    columns      String DEFAULT '[]',  -- JSON-encoded column name list, for zipping rows_json
    rows_json    String,   -- JSON-encoded result rows (array-of-arrays, capped size upstream)
    row_count    UInt32,
    rows_scanned UInt64 DEFAULT 0,
    elapsed_ms   UInt32,
    created_at   DateTime DEFAULT now()
)
ENGINE = MergeTree
ORDER BY (query_id, created_at);

CREATE TABLE IF NOT EXISTS cinesignal.memos
(
    memo_id          String,
    playbook_id      String,
    playbook_version UInt16,
    entity_id        String,
    entity_label     String,
    params           String,  -- JSON
    verdict          String DEFAULT '',
    memo_json        String,  -- full structured memo (sections, chart data, citations)
    query_ids        String,  -- JSON array, the evidence chain for this memo
    created_at       DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree
ORDER BY memo_id;
