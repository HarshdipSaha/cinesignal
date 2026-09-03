"""One-shot structured LLM calls through google-adk (Runner + InMemorySessionService),
against Vertex AI Gemini. Every LLM-facing agent in CineSignal (resolver
disambiguation, interpreter, memo composer, number validator) goes through
this single helper so the ADK Runner wiring only has to be gotten right once.
"""
from __future__ import annotations

import json
import re
import uuid
from typing import TypeVar

from pydantic import BaseModel

from agent import config  # noqa: F401 — sets Vertex AI env vars on import

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text).strip()


async def run_structured(
    *,
    name: str,
    model: str,
    instruction: str,
    user_message: str,
    output_schema: type[T],
) -> T:
    """Run a single-turn LlmAgent call and parse its response as `output_schema`."""
    from google.adk.agents.llm_agent import LlmAgent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    agent = LlmAgent(name=name, model=model, instruction=instruction, output_schema=output_schema)

    session_service = InMemorySessionService()
    user_id = "cinesignal"
    session = await session_service.create_session(app_name=config.APP_NAME, user_id=user_id)
    runner = Runner(app_name=config.APP_NAME, agent=agent, session_service=session_service)

    message = types.Content(role="user", parts=[types.Part(text=user_message)])

    final_text: str | None = None
    async for event in runner.run_async(user_id=user_id, session_id=session.id, new_message=message):
        content = getattr(event, "content", None)
        if content is not None and getattr(content, "parts", None):
            texts = [p.text for p in content.parts if getattr(p, "text", None)]
            if texts:
                final_text = "\n".join(texts)

    if final_text is None:
        raise RuntimeError(f"LlmAgent '{name}' produced no text output")

    cleaned = _strip_fences(final_text)
    try:
        return output_schema.model_validate_json(cleaned)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"LlmAgent '{name}' output failed schema validation: {exc}\nRaw output: {final_text[:1000]}") from exc


def new_request_id() -> str:
    return uuid.uuid4().hex[:10]
