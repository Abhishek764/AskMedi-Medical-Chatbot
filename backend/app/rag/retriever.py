"""Hybrid retriever: plan → Qdrant hybrid (dense + BM25, RRF) → rerank → parent expansion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.rag.bm25 import BM25Encoder
from app.rag.embeddings import Embedder
from app.rag.query import QueryPlan
from app.rag.rerank import Reranker
from app.rag.store import VectorStore
from app.rag.types import Retrieved

INTENT_BOOST = 0.05
Mode = Literal["dense", "bm25", "hybrid", "hybrid_rerank"]


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

    async def rank(
        self, plan: QueryPlan, *, allow_dosing: bool, mode: Mode = "hybrid_rerank"
    ) -> tuple[list[Retrieved], int]:
        """Ranked child chunks for a query. Production uses `hybrid_rerank`; the other modes
        exist so the ablation study (app/eval_ablation.py) can measure each stage's effect."""
        flt = VectorStore.safety_filter(allow_dosing=allow_dosing)
        if mode == "bm25":
            hits = await self.store.single_search(
                self.bm25.encode_query(plan.sparse_query), "bm25", limit=self.retrieve_k, flt=flt
            )
        else:
            dense = await self.embedder.embed_query(plan.dense_query)
            if mode == "dense":
                hits = await self.store.single_search(
                    dense, "dense", limit=self.retrieve_k, flt=flt
                )
            else:
                sparse = self.bm25.encode_query(plan.sparse_query)
                hits = await self.store.hybrid_search(dense, sparse, limit=self.retrieve_k, flt=flt)
        if not hits:
            return [], 0

        if mode == "hybrid_rerank":
            texts = [str(h.payload.get("text", "")) for h in hits]
            scores = await self.reranker.score(plan.normalised, texts)
        else:  # keep the retriever's own order
            scores = [1.0 - i / (len(hits) + 1) for i in range(len(hits))]
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
        if mode == "hybrid_rerank":
            ranked.sort(key=lambda r: r.score, reverse=True)
        return ranked, len(hits)

    async def retrieve(self, plan: QueryPlan, *, allow_dosing: bool) -> RetrievalResult:
        ranked, candidates = await self.rank(plan, allow_dosing=allow_dosing)
        if not ranked:
            return RetrievalResult(plan, [], 0.0, 0)

        best_per_parent: dict[str, Retrieved] = {}
        for r in ranked:
            best_per_parent.setdefault(r.parent_id, r)
        top = list(best_per_parent.values())[: self.context_k]

        parents = await self.store.get_parents([r.parent_id for r in top])
        for r in top:
            p = parents.get(r.parent_id)
            r.parent_text = str(p["text"]) if p else r.text.split("\n", 1)[-1]
        return RetrievalResult(plan, top, top[0].score if top else 0.0, candidates)
