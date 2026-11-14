"""Hybrid retriever: plan → Qdrant hybrid (dense + BM25, RRF) → rerank → parent expansion."""

from __future__ import annotations

from dataclasses import dataclass

from app.rag.bm25 import BM25Encoder
from app.rag.embeddings import Embedder
from app.rag.query import QueryPlan
from app.rag.rerank import Reranker
from app.rag.store import VectorStore
from app.rag.types import Retrieved

INTENT_BOOST = 0.05


@dataclass
class RetrievalResult:
    plan: QueryPlan
    passages: list[Retrieved]  # top context_k, best first, one per parent
    top_score: float
    candidates: int


class HybridRetriever:
    def __init__(
        self,
        store: VectorStore,
        embedder: Embedder,
        reranker: Reranker,
        bm25: BM25Encoder | None = None,
        *,
        retrieve_k: int = 30,
        context_k: int = 5,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.reranker = reranker
        self.bm25 = bm25 or BM25Encoder()
        self.retrieve_k = retrieve_k
        self.context_k = context_k

    async def retrieve(self, plan: QueryPlan, *, allow_dosing: bool) -> RetrievalResult:
        dense = await self.embedder.embed_query(plan.dense_query)
        sparse = self.bm25.encode_query(plan.sparse_query)
        hits = await self.store.hybrid_search(
            dense,
            sparse,
            limit=self.retrieve_k,
            flt=VectorStore.safety_filter(allow_dosing=allow_dosing),
        )
        if not hits:
            return RetrievalResult(plan, [], 0.0, 0)

        texts = [str(h.payload.get("text", "")) for h in hits]
        scores = await self.reranker.score(plan.normalised, texts)
        ranked: list[Retrieved] = []
        for h, s in zip(hits, scores, strict=True):
            boost = INTENT_BOOST if h.payload.get("doc_type") in plan.preferred_doc_types else 0.0
            ranked.append(
                Retrieved(
                    chunk_id=h.id,
                    parent_id=str(h.payload.get("parent_id")),
                    doc_id=str(h.payload.get("doc_id")),
                    text=str(h.payload.get("text", "")),
                    score=min(1.0, s + boost) if s > 0 else 0.0,
                    payload=h.payload,
                )
            )
        ranked.sort(key=lambda r: r.score, reverse=True)

        best_per_parent: dict[str, Retrieved] = {}
        for r in ranked:
            best_per_parent.setdefault(r.parent_id, r)
        top = list(best_per_parent.values())[: self.context_k]

        parents = await self.store.get_parents([r.parent_id for r in top])
        for r in top:
            p = parents.get(r.parent_id)
            r.parent_text = str(p["text"]) if p else r.text.split("\n", 1)[-1]
        return RetrievalResult(plan, top, top[0].score if top else 0.0, len(hits))
