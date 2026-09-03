"""Interpreter: turns the deterministic Finding list + chart_data into a
short set of ranked "talking points" for the MemoComposer to write prose
around. It reasons only over already-computed structured JSON — it does not
see raw SQL, does not call tools, and cannot introduce a number that isn't
already in `findings`."""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from agent.config import PRO_MODEL
from agent.llm import run_structured
from agent.models import Finding

INTERPRETER_INSTRUCTION = """You are a film-industry attention analyst. You will be given:
- a playbook name and verdict
- a JSON list of deterministically-computed findings (key, label, value, unit, query_id)
- a JSON summary of chart data

Produce 3-6 ranked "key points" that a marketing executive would care about. Each key
point must be a direct, checkable claim about one or more findings — do not invent
numbers, dates, or comparisons not present in the findings/chart data. Reference which
finding key(s) support each point. Also write one punchy one-sentence headline.
Respond ONLY with the InterpretedInsights JSON schema."""


class KeyPoint(BaseModel):
    point: str
    supporting_finding_keys: list[str] = Field(default_factory=list)


class InterpretedInsights(BaseModel):
    headline: str
    key_points: list[KeyPoint]
    caveats: str = ""


async def interpret(playbook_name: str, verdict: str, findings: list[Finding], chart_data: dict[str, Any]) -> InterpretedInsights:
    chart_summary = {k: (v if not isinstance(v, list) else f"[{len(v)} points]") for k, v in chart_data.items()}
    user_message = json.dumps(
        {
            "playbook": playbook_name,
            "verdict": verdict,
            "findings": [f.model_dump() for f in findings],
            "chart_summary": chart_summary,
        },
        default=str,
    )
    return await run_structured(
        name="interpreter",
        model=PRO_MODEL,
        instruction=INTERPRETER_INSTRUCTION,
        user_message=user_message,
        output_schema=InterpretedInsights,
    )
