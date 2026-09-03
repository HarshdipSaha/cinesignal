"""Shared data contracts between the playbook engine, the LLM agents, and the API."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ResolvedEntity(BaseModel):
    wikidata_id: str
    label: str
    entity_type: Literal["film", "series", "person", "franchise"]
    year: int | None = None
    tconst: str = ""
    nconst: str = ""
    genres: list[str] = Field(default_factory=list)


class StepEvidence(BaseModel):
    """One executed, evidence-logged playbook step."""

    step_id: str
    title: str
    query_id: str
    sql: str
    params: dict[str, Any]
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    elapsed_ms: int
    rows_scanned: int | None = None
    error: str | None = None


class Finding(BaseModel):
    """A single deterministic, numeric claim computed by playbook code (never
    by the LLM) and citable in the memo as [qN]."""

    key: str
    label: str
    value: float | int | str
    unit: str = ""
    query_id: str
    extra: dict[str, Any] = Field(default_factory=dict)


class MemoSection(BaseModel):
    heading: str
    body: str  # prose containing [qN] citation markers referencing query_id suffixes


class Memo(BaseModel):
    memo_id: str
    playbook_id: str
    playbook_version: int
    entity: ResolvedEntity
    params: dict[str, Any]
    verdict: str = ""
    headline: str = ""
    sections: list[MemoSection]
    findings: list[Finding]
    chart_data: dict[str, Any] = Field(default_factory=dict)
    query_ids: list[str]
    validated: bool = False
    validator_notes: str = ""


class PlaybookRunEvent(BaseModel):
    """One SSE event emitted while a playbook runs."""

    type: Literal["stage", "step", "finding", "memo", "error"]
    stage: str = ""
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
