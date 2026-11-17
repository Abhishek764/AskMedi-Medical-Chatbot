"""Ask the local pipeline a question from the terminal (uses .env settings and local corpus).

uv run python scripts/ask.py "What are the symptoms of dengue?" [--role provider]
"""

from __future__ import annotations

import argparse
import asyncio

from app.core.config import get_settings
from app.core.container import Container
from app.rag.pipeline import UserContext


async def main(question: str, role: str) -> None:
    container = Container(get_settings())
    await container.startup()
    try:
        async for ev in container.pipeline.answer_stream(question, [], UserContext(role=role)):
            if ev.type == "sentence":
                print(ev.data["text"], ev.data["citations"])
            elif ev.type == "citations":
                for c in ev.data["items"]:
                    print(
                        f"  [{c['position']}] {c['title']} › {c['section']} ({c['source']}) {c['score']}"
                    )
            elif ev.type == "result":
                rec = ev.data["record"]
                print(
                    f"-- status={rec.status} reason={rec.refusal_reason} latency={rec.latency_ms}ms"
                )
            elif ev.type in ("refusal", "crisis", "emergency", "banner"):
                print(f"[{ev.type}]", ev.data.get("message", "")[:200])
    finally:
        await container.shutdown()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--role", default="public")
    a = ap.parse_args()
    asyncio.run(main(a.question, a.role))
