"""EntityResolver: free-text query -> ResolvedEntity.

Search itself is a fixed, deterministic SQL template executed through the
same mcp-clickhouse MCP session as everything else (never raw user text
concatenated straight into SQL — see sql_template.bind_search_text). The
flash LLM's only job is judgment: given already-fetched candidate rows,
decide which one (if any) the user meant. It never sees or writes SQL.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from agent.config import FLASH_MODEL
from agent.llm import run_structured
from agent.mcp_client import get_shared_session, reset_shared_session
from agent.models import ResolvedEntity
from agent.sql_template import bind_search_text

SEARCH_SQL_TEMPLATE = """
SELECT wikidata_id, page_title, entity_type, tconst, nconst, genres, release_date
FROM cinesignal.entities
WHERE positionCaseInsensitive(page_title, {query}) > 0
ORDER BY length(page_title) ASC
LIMIT 15
"""


class _Candidate(BaseModel):
    wikidata_id: str
    label: str
    entity_type: str
    year: int | None = None
    tconst: str = ""
    nconst: str = ""
    genres: list[str] = Field(default_factory=list)


def _row_to_candidate(row: list) -> _Candidate:
    wikidata_id, page_title, entity_type, tconst, nconst, genres, release_date = row
    year = None
    if release_date:
        try:
            year = int(str(release_date)[:4])
        except ValueError:
            year = None
    genre_list = [g.strip() for g in (genres or "").split(",") if g.strip()]
    return _Candidate(
        wikidata_id=wikidata_id, label=page_title, entity_type=entity_type,
        year=year, tconst=tconst or "", nconst=nconst or "", genres=genre_list,
    )


class DisambiguationChoice(BaseModel):
    wikidata_id: str | None = Field(description="wikidata_id of the best-matching candidate, or null if none clearly match")
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


RESOLVER_INSTRUCTION = """You are an entity-resolution judge for a film-attention-analytics tool.
You will be given a user's free-text search query and a JSON list of candidate entities
(each has wikidata_id, label, entity_type, year, genres). Pick the single candidate the
user most likely meant. If the query is ambiguous between two very different things
(e.g. a common word that matches unrelated titles) and no candidate is a clearly better
fit, set wikidata_id to null. Respond ONLY with the DisambiguationChoice JSON schema —
no prose, no SQL, no tool calls. You are not permitted to invent a wikidata_id that is
not in the candidate list."""


class ResolverError(Exception):
    pass


async def resolve(query: str, entity_type: str | None = None) -> tuple[ResolvedEntity | None, list[ResolvedEntity]]:
    """Returns (best_match_or_None, all_candidates). If best_match is None and
    candidates is non-empty, the caller should present candidates for disambiguation."""
    sql = SEARCH_SQL_TEMPLATE.format(query=bind_search_text(query)).strip()

    session = await get_shared_session()
    result = await session.run_query(sql, query_id=f"resolve:{query[:40]}")

    if result.error:
        await reset_shared_session()
        raise ResolverError(result.error)

    candidates = [_row_to_candidate(r) for r in result.rows]
    if entity_type:
        candidates = [c for c in candidates if c.entity_type == entity_type] or candidates

    if not candidates:
        return None, []

    exact = [c for c in candidates if c.label.lower() == query.strip().lower()]
    if len(exact) == 1:
        return _to_resolved(exact[0]), [_to_resolved(c) for c in candidates]

    if len(candidates) == 1:
        return _to_resolved(candidates[0]), [_to_resolved(candidates[0])]

    choice = await run_structured(
        name="entity_resolver",
        model=FLASH_MODEL,
        instruction=RESOLVER_INSTRUCTION,
        user_message=f"Query: {query!r}\nCandidates: {[c.model_dump() for c in candidates]}",
        output_schema=DisambiguationChoice,
    )

    resolved_candidates = [_to_resolved(c) for c in candidates]
    if choice.wikidata_id:
        match = next((c for c in candidates if c.wikidata_id == choice.wikidata_id), None)
        if match:
            return _to_resolved(match), resolved_candidates

    return None, resolved_candidates


async def get_by_id(wikidata_id: str) -> ResolvedEntity | None:
    """Fetch one entity by its wikidata_id — used once the frontend has
    already resolved a search result and just needs the full record to
    kick off a playbook run."""
    from agent.sql_template import bind_wikidata_id

    sql = (
        "SELECT wikidata_id, page_title, entity_type, tconst, nconst, genres, release_date "
        "FROM cinesignal.entities WHERE wikidata_id = "
        f"{bind_wikidata_id(wikidata_id)} LIMIT 1"
    )
    session = await get_shared_session()
    result = await session.run_query(sql, query_id=f"lookup:{wikidata_id}")
    if result.error:
        await reset_shared_session()
    if result.error or not result.rows:
        return None
    return _to_resolved(_row_to_candidate(result.rows[0]))


def _to_resolved(c: _Candidate) -> ResolvedEntity:
    return ResolvedEntity(
        wikidata_id=c.wikidata_id, label=c.label, entity_type=c.entity_type,  # type: ignore[arg-type]
        year=c.year, tconst=c.tconst, nconst=c.nconst, genres=c.genres,
    )
