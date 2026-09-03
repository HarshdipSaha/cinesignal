-- CineSignal warehouse schema.
-- Run via `python ingest/apply_ddl.py`. Idempotent (CREATE ... IF NOT EXISTS).

CREATE DATABASE IF NOT EXISTS cinesignal;

-- Raw Wikimedia per-article daily pageviews, filtered at ingest time to the
-- film-universe page set (see ingest/pageviews.py). One row per (page, project, day).
CREATE TABLE IF NOT EXISTS cinesignal.pageviews_daily
(
    page_id UInt64,
    project LowCardinality(String),   -- 'en.wikipedia', 'ja.wikipedia', ...
    date    Date,
    views   UInt32
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(date)
ORDER BY (page_id, project, date);

-- The join spine: Wikipedia page <-> Wikidata entity <-> IMDb id.
-- Populated from Wikidata (P345 = IMDb id, P4947 = pageview equivalence, P31 = instance-of).
CREATE TABLE IF NOT EXISTS cinesignal.entities
(
    wikidata_id String,
    page_id     UInt64,
    project     LowCardinality(String),
    page_title  String,
    entity_type Enum8('film' = 1, 'series' = 2, 'person' = 3, 'franchise' = 4),
    tconst      String DEFAULT '',   -- IMDb title id (films/series)
    nconst      String DEFAULT '',   -- IMDb name id (people)
    genres      String DEFAULT '',  -- denormalized comma-joined genre list, for cohort filters
    release_date Nullable(Date) DEFAULT NULL
)
ENGINE = ReplacingMergeTree
ORDER BY (wikidata_id, project);

-- IMDb catalog tables, loaded verbatim (TSV) from datasets.imdbws.com.
CREATE TABLE IF NOT EXISTS cinesignal.imdb_titles
(
    tconst          String,
    titleType       LowCardinality(String),
    primaryTitle    String,
    originalTitle   String,
    isAdult         UInt8,
    startYear       Nullable(UInt16),
    endYear         Nullable(UInt16),
    runtimeMinutes  Nullable(UInt32),
    genres          String
)
ENGINE = ReplacingMergeTree
ORDER BY tconst;

CREATE TABLE IF NOT EXISTS cinesignal.imdb_ratings
(
    tconst        String,
    averageRating Float32,
    numVotes      UInt32
)
ENGINE = ReplacingMergeTree
ORDER BY tconst;

CREATE TABLE IF NOT EXISTS cinesignal.imdb_principals
(
    tconst     String,
    ordering   UInt8,
    nconst     String,
    category   LowCardinality(String),
    job        String,
    characters String
)
ENGINE = MergeTree
ORDER BY (tconst, ordering);

CREATE TABLE IF NOT EXISTS cinesignal.imdb_names
(
    nconst            String,
    primaryName       String,
    birthYear         Nullable(UInt16),
    deathYear         Nullable(UInt16),
    primaryProfession String,
    knownForTitles    String
)
ENGINE = ReplacingMergeTree
ORDER BY nconst;

CREATE TABLE IF NOT EXISTS cinesignal.imdb_crew
(
    tconst    String,
    directors String,
    writers   String
)
ENGINE = ReplacingMergeTree
ORDER BY tconst;

CREATE TABLE IF NOT EXISTS cinesignal.imdb_episodes
(
    tconst        String,
    parentTconst  String,
    seasonNumber  Nullable(UInt16),
    episodeNumber Nullable(UInt16)
)
ENGINE = ReplacingMergeTree
ORDER BY tconst;

-- Rollup MV that powers every playbook: daily attention per entity, already
-- summed across the raw pageviews rows for that entity's page(s).
CREATE TABLE IF NOT EXISTS cinesignal.entity_attention_daily
(
    wikidata_id String,
    project     LowCardinality(String),
    date        Date,
    views       UInt64
)
ENGINE = SummingMergeTree
ORDER BY (wikidata_id, project, date);

CREATE MATERIALIZED VIEW IF NOT EXISTS cinesignal.entity_attention_daily_mv
TO cinesignal.entity_attention_daily
AS
SELECT
    e.wikidata_id AS wikidata_id,
    p.project     AS project,
    p.date        AS date,
    p.views       AS views
FROM cinesignal.pageviews_daily AS p
INNER JOIN cinesignal.entities AS e
    ON p.page_id = e.page_id AND p.project = e.project;

-- Backfill helper (MVs only see new inserts; run once after each pageviews load
-- to populate the rollup with pre-existing rows). Also exposed as a plain query
-- so playbooks can run without waiting on a manual backfill during dev.
CREATE VIEW IF NOT EXISTS cinesignal.entity_attention_daily_live AS
SELECT
    e.wikidata_id AS wikidata_id,
    p.project     AS project,
    p.date        AS date,
    sum(p.views)  AS views
FROM cinesignal.pageviews_daily AS p
INNER JOIN cinesignal.entities AS e
    ON p.page_id = e.page_id AND p.project = e.project
GROUP BY e.wikidata_id, p.project, p.date;
