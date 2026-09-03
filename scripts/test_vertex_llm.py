"""Minimal Vertex AI / google-adk smoke test. ONE cheap flash call, nothing
more — this exists to verify credentials + wiring work, not to be run
repeatedly (mind the hackathon's $100 credit). Run: python scripts/test_vertex_llm.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel

from agent.config import FLASH_MODEL
from agent.llm import run_structured


class Ack(BaseModel):
    ok: bool
    note: str


async def main() -> None:
    print(f"Calling {FLASH_MODEL} via google-adk LlmAgent + Vertex AI (one call)...")
    result = await run_structured(
        name="smoke_test",
        model=FLASH_MODEL,
        instruction="Respond only with the Ack JSON schema: ok=true, note='cinesignal vertex smoke test passed'.",
        user_message="ping",
        output_schema=Ack,
    )
    print("Result:", result)
    assert result.ok, "model did not acknowledge"
    print("PASS")


if __name__ == "__main__":
    asyncio.run(main())
