"""Full end-to-end integration smoke test: EntityResolver -> PlaybookRunner
-> Interpreter -> MemoComposer -> NumberValidator, against real ClickHouse
data and real Vertex AI. Costs a handful of LLM calls (not a loop) — run
deliberately, not in CI. Run: python scripts/test_full_pipeline.py <query> <playbook>
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import resolver, tree  # noqa: E402


async def main() -> None:
    query = sys.argv[1] if len(sys.argv) > 1 else "Apollo 18"
    playbook_id = sys.argv[2] if len(sys.argv) > 2 else "title_pulse"

    print(f"Resolving {query!r}...")
    best, candidates = await resolver.resolve(query)
    print(f"best_match={best}")
    print(f"candidates={len(candidates)}")
    entity = best or (candidates[0] if candidates else None)
    if entity is None:
        print("No entity found, aborting.")
        return

    params: dict = {}
    if playbook_id == "campaign_impact":
        params = {"event_date": "2024-06-01"}

    print(f"\nRunning playbook {playbook_id!r} for {entity.label} ({entity.wikidata_id})...")

    async def on_event(event_type: str, data: dict) -> None:
        print(f"  [{event_type}] {data}")

    memo = await tree.run_playbook(playbook_id, entity, params, on_event)

    print("\n=== MEMO ===")
    print("memo_id:", memo.memo_id)
    print("verdict:", memo.verdict)
    print("headline:", memo.headline)
    print("validated:", memo.validated, memo.validator_notes)
    for s in memo.sections:
        print(f"\n-- {s.heading} --\n{s.body}")
    print("\nfindings:")
    for f in memo.findings:
        print(" ", f.key, "=", f.value, f.unit, f"[{f.query_id}]")


if __name__ == "__main__":
    asyncio.run(main())
