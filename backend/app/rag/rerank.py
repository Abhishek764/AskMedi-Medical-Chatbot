"""Rerankers. Each returns a relevance score in [0, 1] per document, used for ordering and
for the abstain gate, so each declares its own default abstain threshold.

- lexical:   query-term coverage (no model). Default when RERANK_PROVIDER=none.
- fastembed: free local cross-encoder (ms-marco MiniLM, ONNX).
- cohere:    hosted Rerank (needs COHERE_API_KEY).
"""

from __future__ import annotations

import math
from typing import Protocol

import httpx

from app.rag.bm25 import tokenize

# Words that say what kind of question it is but not what it is about.
GENERIC = frozenset(
    tokenize(
        """what how why when who which is are does do can symptom symptoms sign signs cause causes
        caused treat treated treatment treatments therapy cure risk risks factor factors prevent
        prevention diagnose diagnosed diagnosis effect effects side common usual type types
        work works help helps mean means long term disease condition problem people patient
        patients get getting know tell explain about good bad best"""
    )
)


class Reranker(Protocol):
    name: str
    default_threshold: float

    async def score(self, query: str, docs: list[str]) -> list[float]: ...


class LexicalReranker:
    name = "lexical"
    default_threshold = 0.5

    async def score(self, query: str, docs: list[str]) -> list[float]:
        q = list(dict.fromkeys(tokenize(query)))
        specific = [t for t in q if t not in GENERIC] or q
        if not specific:
            return [0.0] * len(docs)
        out = []
        for d in docs:
            toks = set(tokenize(d))
            core = sum(1 for t in specific if t in toks) / len(specific)
            extra = sum(1 for t in q if t in toks) / len(q)
            out.append(round(0.85 * core + 0.15 * extra, 4))
        return out


class FastEmbedReranker:
    name = "fastembed"
    default_threshold = 0.2

    def __init__(self, model: str) -> None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self._model = TextCrossEncoder(model_name=model)

    async def score(self, query: str, docs: list[str]) -> list[float]:
        import anyio

        logits = await anyio.to_thread.run_sync(lambda: list(self._model.rerank(query, docs)))
        return [1 / (1 + math.exp(-x)) for x in logits]


class CohereReranker:
    name = "cohere"
    default_threshold = 0.15

    def __init__(self, api_key: str, model: str = "rerank-v3.5") -> None:
        self._client = httpx.AsyncClient(
            base_url="https://api.cohere.com/v2",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        self._model = model

    async def score(self, query: str, docs: list[str]) -> list[float]:
        if not docs:
            return []
        r = await self._client.post(
            "/rerank", json={"model": self._model, "query": query, "documents": docs}
        )
        r.raise_for_status()
        scores = [0.0] * len(docs)
        for item in r.json().get("results", []):
            scores[int(item["index"])] = float(item["relevance_score"])
        return scores

    async def aclose(self) -> None:
        await self._client.aclose()


def build_reranker(provider: str, *, model: str, cohere_key: str | None) -> Reranker:
    if provider == "fastembed":
        return FastEmbedReranker(model)
    if provider == "cohere":
        if not cohere_key:
            raise ValueError("COHERE_API_KEY required for cohere rerank")
        return CohereReranker(cohere_key)
    return LexicalReranker()
