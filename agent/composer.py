"""MemoComposer: writes the memo's prose sections, citing evidence with
[qN] markers. It receives a fixed citation index (query_id -> qN, built
deterministically from execution order in agent/tree.py) and is instructed
to cite ONLY from that index — it cannot mint a new [qN] or a number that
isn't present in the findings it was given."""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from agent.config import PRO_MODEL
from agent.interpreter import InterpretedInsights
from agent.llm import run_structured
from agent.models import Finding, ResolvedEntity

COMPOSER_INSTRUCTION = """You are writing a decision memo for a film studio marketing team. You will be
given: the resolved entity, the playbook name/verdict, a JSON list of deterministic
findings (each with a query_id), a citation index mapping query_id -> its [qN] marker,
and pre-ranked key points from an analyst.

Rules:
- Every specific number you state MUST come from the findings list, and MUST be
  immediately followed by the [qN] marker from the citation index for that finding's
  query_id. Do not use a [qN] marker that is not in the citation index. Do not state a
  number that has no corresponding finding.
- Write 2-4 sections. Section 1 should always be "Summary" with the headline verdict.
  Include a "Methodology & Caveats" section that briefly notes any assumptions (e.g. the
  attention-hours estimate, or the verdict-classification method) if relevant.
- Tone: precise, confident, boardroom-ready. No hedging filler, no "in conclusion".
- Respond ONLY with the ComposedMemo JSON schema."""


class ComposedSection(BaseModel):
    heading: str
    body: str


class ComposedMemo(BaseModel):
    headline: str
    sections: list[ComposedSection]


async def compose(
    entity: ResolvedEntity,
    playbook_name: str,
    verdict: str,
    findings: list[Finding],
    insights: InterpretedInsights,
    citation_index: dict[str, str],
) -> ComposedMemo:
    user_message = json.dumps(
        {
            "entity": entity.model_dump(),
            "playbook": playbook_name,
            "verdict": verdict,
            "findings": [f.model_dump() for f in findings],
            "citation_index": citation_index,
            "analyst_headline": insights.headline,
            "analyst_key_points": [kp.model_dump() for kp in insights.key_points],
            "analyst_caveats": insights.caveats,
        },
        default=str,
    )
    return await run_structured(
        name="memo_composer",
        model=PRO_MODEL,
        instruction=COMPOSER_INSTRUCTION,
        user_message=user_message,
        output_schema=ComposedMemo,
    )
