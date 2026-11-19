"""Copy the local embedded Qdrant index to a Qdrant server (e.g. Qdrant Cloud free tier).

Reuses the ingested vectors, so nothing is re-embedded. The target collections are created
through VectorStore.ensure(), which also adds the payload indexes the filters need.

    uv run --no-sync python scripts/copy_index.py            # reads QDRANT_URL / QDRANT_API_KEY
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qdrant_client import AsyncQdrantClient
from qdrant_client import models as m

from app.core.config import get_settings
from app.rag.store import VectorStore

BATCH = 256


async def copy(src: AsyncQdrantClient, dst: AsyncQdrantClient, name: str) -> int:
    offset = None
    total = 0
    while True:
        points, offset = await src.scroll(
            name, limit=BATCH, offset=offset, with_payload=True, with_vectors=True
        )
        if points:
            await dst.upsert(
                name,
                points=[
                    m.PointStruct(id=p.id, vector=p.vector or {}, payload=p.payload)
                    for p in points
                ],
            )
            total += len(points)
            print(f"  {name}: {total}", end="\r", flush=True)
        if offset is None:
            print()
            return total


async def main() -> None:
    s = get_settings()
    if not s.qdrant_url or not s.qdrant_api_key:
        raise SystemExit("Set QDRANT_URL and QDRANT_API_KEY (backend/.env) first.")
    src = AsyncQdrantClient(path=s.qdrant_path)
    dst = VectorStore.from_settings(
        url=s.qdrant_url,
        path=s.qdrant_path,
        api_key=s.qdrant_api_key,
        collection=s.qdrant_collection,
        dim=s.embeddings_dim,
    )
    await dst.ensure()
    for name in (dst.collection, dst.parents):
        n = await copy(src, dst.client, name)
        remote = (await dst.client.count(name, exact=True)).count
        print(f"{name}: copied {n}, remote has {remote}")
    await src.close()
    await dst.client.close()


if __name__ == "__main__":
    asyncio.run(main())
