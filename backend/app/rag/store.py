"""Qdrant store: one collection of children (dense + BM25 sparse) and one of parents.

Local embedded mode (QDRANT_URL unset) for dev and tests; Qdrant Cloud in production.
Children are searched with server-side hybrid fusion (prefetch dense + BM25 → RRF).
"""

from __future__ import annotations

from dataclasses import dataclass

from qdrant_client import AsyncQdrantClient
from qdrant_client import models as m

from app.rag.bm25 import SparseVec
from app.rag.types import LICENCE_ALLOWLIST, Chunk, Parent


@dataclass
class Hit:
    id: str
    score: float
    payload: dict[str, object]


class VectorStore:
    def __init__(self, client: AsyncQdrantClient, collection: str, dim: int) -> None:
        self.client = client
        self.collection = collection
        self.parents = f"{collection}-parents"
        self.dim = dim

    @classmethod
    def from_settings(
        cls, *, url: str | None, path: str, api_key: str | None, collection: str, dim: int
    ) -> VectorStore:
        client = (
            AsyncQdrantClient(url=url, api_key=api_key) if url else AsyncQdrantClient(path=path)
        )
        return cls(client, collection, dim)

    async def ensure(self) -> None:
        if not await self.client.collection_exists(self.collection):
            await self.client.create_collection(
                self.collection,
                vectors_config={"dense": m.VectorParams(size=self.dim, distance=m.Distance.COSINE)},
                sparse_vectors_config={"bm25": m.SparseVectorParams(modifier=m.Modifier.IDF)},
            )
            for field, schema in [
                ("doc_id", m.PayloadSchemaType.KEYWORD),
                ("doc_type", m.PayloadSchemaType.KEYWORD),
                ("licence", m.PayloadSchemaType.KEYWORD),
                ("lang", m.PayloadSchemaType.KEYWORD),
                ("retracted", m.PayloadSchemaType.BOOL),
                ("dosing", m.PayloadSchemaType.BOOL),
                ("year", m.PayloadSchemaType.INTEGER),
            ]:
                await self.client.create_payload_index(self.collection, field, schema)
        if not await self.client.collection_exists(self.parents):
            await self.client.create_collection(self.parents, vectors_config={})

    async def upsert(
        self,
        parents: list[Parent],
        chunks: list[Chunk],
        dense: list[list[float]],
        sparse: list[SparseVec],
    ) -> None:
        if parents:
            await self.client.upsert(
                self.parents,
                [
                    m.PointStruct(
                        id=p.id,
                        vector={},
                        payload={"doc_id": p.doc_id, "header": p.header, "text": p.text},
                    )
                    for p in parents
                ],
            )
        for i in range(0, len(chunks), 128):
            batch = range(i, min(i + 128, len(chunks)))
            await self.client.upsert(
                self.collection,
                [
                    m.PointStruct(
                        id=chunks[j].id,
                        vector={
                            "dense": dense[j],
                            "bm25": m.SparseVector(
                                indices=sparse[j].indices, values=sparse[j].values
                            ),
                        },
                        payload={**chunks[j].payload, "text": chunks[j].text},
                    )
                    for j in batch
                ],
            )

    async def delete_doc(self, doc_id: str) -> None:
        flt = m.Filter(must=[m.FieldCondition(key="doc_id", match=m.MatchValue(value=doc_id))])
        await self.client.delete(self.collection, points_selector=m.FilterSelector(filter=flt))
        await self.client.delete(self.parents, points_selector=m.FilterSelector(filter=flt))

    @staticmethod
    def safety_filter(*, allow_dosing: bool, lang: str = "en") -> m.Filter:
        must: list[m.Condition] = [
            m.FieldCondition(key="licence", match=m.MatchAny(any=sorted(LICENCE_ALLOWLIST))),
            m.FieldCondition(key="retracted", match=m.MatchValue(value=False)),
            m.FieldCondition(key="lang", match=m.MatchValue(value=lang)),
        ]
        if not allow_dosing:
            must.append(m.FieldCondition(key="dosing", match=m.MatchValue(value=False)))
        return m.Filter(must=must)

    async def hybrid_search(
        self, dense: list[float], sparse: SparseVec, *, limit: int, flt: m.Filter
    ) -> list[Hit]:
        res = await self.client.query_points(
            self.collection,
            prefetch=[
                m.Prefetch(query=dense, using="dense", limit=limit * 2, filter=flt),
                m.Prefetch(
                    query=m.SparseVector(indices=sparse.indices, values=sparse.values),
                    using="bm25",
                    limit=limit * 2,
                    filter=flt,
                ),
            ],
            query=m.FusionQuery(fusion=m.Fusion.RRF),
            limit=limit,
            with_payload=True,
        )
        return [Hit(str(p.id), float(p.score), dict(p.payload or {})) for p in res.points]

    async def get_parents(self, ids: list[str]) -> dict[str, dict[str, object]]:
        if not ids:
            return {}
        recs = await self.client.retrieve(self.parents, ids=ids, with_payload=True)
        return {str(r.id): dict(r.payload or {}) for r in recs}

    async def doc_sections(self, doc_id: str) -> tuple[dict[str, str], dict[str, object] | None]:
        """All parent sections of one document as {section heading: text}, plus one child's
        payload (title, url, source) for citing it. Reads stored text; no search involved."""
        flt = m.Filter(must=[m.FieldCondition(key="doc_id", match=m.MatchValue(value=doc_id))])
        parents, _ = await self.client.scroll(
            self.parents, scroll_filter=flt, limit=64, with_payload=True
        )
        sections: dict[str, str] = {}
        for p in parents:
            payload = p.payload or {}
            header = str(payload.get("header", ""))
            name = header.split(" › ", 1)[1].split(" · ")[0] if " › " in header else header
            text = str(payload.get("text", ""))
            sections[name] = f"{sections[name]}\n{text}" if name in sections else text
        children, _ = await self.client.scroll(
            self.collection, scroll_filter=flt, limit=1, with_payload=True
        )
        meta = (
            (dict(children[0].payload or {}) | {"chunk_id": str(children[0].id)})
            if children
            else None
        )
        return sections, meta

    async def count(self) -> int:
        if not await self.client.collection_exists(self.collection):
            return 0
        return (await self.client.count(self.collection, exact=True)).count

    async def ping(self) -> bool:
        try:
            await self.client.get_collections()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        await self.client.close()
