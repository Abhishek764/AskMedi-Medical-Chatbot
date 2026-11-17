"""Walk the medicine check end to end against the local index, printing what a person sees.

uv run python scripts/medicine_check.py "I have a headache, what can I take?" adult none thinners
"""

from __future__ import annotations

import asyncio
import sys

from app.core.config import get_settings
from app.core.container import Container
from app.rag.pipeline import UserContext


async def main(question: str, answers: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    c = Container(get_settings())
    await c.startup()
    state = None
    try:
        steps = [None, *[(i + 1, a.split(",")) for i, a in enumerate(answers)]]
        for step in steps:
            ctx = UserContext(triage=state, triage_answer=step)
            print(f"\n>>> {question if step is None else step}")
            async for ev in c.pipeline.answer_stream(question, [], ctx):
                if ev.type == "result":
                    state = ev.data["record"].triage_state
                elif ev.type == "triage":
                    print("Q:", ev.data["question"], [o["id"] for o in ev.data["options"]])
                elif ev.type == "medicines":
                    for m in ev.data["items"]:
                        print(
                            f"- {m['name']} | {m.get('active_ingredient', '')}\n  Directions: {m.get('directions', '')[:300]}"
                        )
                    for e in ev.data["excluded"]:
                        print(f"  (not shown: {e['name']}, {e['reason']})")
                elif ev.type in ("sentence", "refusal", "emergency"):
                    print(f"[{ev.type}]", ev.data.get("text") or ev.data.get("message"))
    finally:
        await c.shutdown()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2:]))
