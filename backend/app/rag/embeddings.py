"""Dense embedding providers.

- hash:      feature-hashed word uni/bigrams. No download, deterministic; dev and tests.
- fastembed: free local ONNX models (default BAAI/bge-small-en-v1.5, 384-d). `uv sync --extra local`.
- openai:    text-embedding-3-small (needs OPENAI_API_KEY).
"""

from __future__ import annotations

import hashlib
import math
from typing import Protocol

import httpx

from app.rag.bm25 import tokenize


class Embedder(Protocol):
    dim: int
    name: str

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...


class HashEmbedder:
    def __init__(self, dim: int = 384) -> None:
        self.dim = dim
        self.name = f"hash-{dim}"

    def _vec(self, text: str) -> list[float]:
        toks = tokenize(text)
        feats = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:], strict=False)]
        v = [0.0] * self.dim
        for f in feats:
            h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "big")
            v[h % self.dim] += 1.0 if (h >> 32) & 1 else -1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


class FastEmbedEmbedder:
    def __init__(self, model: str, dim: int) -> None:
        from fastembed import TextEmbedding  # optional extra: uv sync --extra local

        self._model = TextEmbedding(model_name=model)
        self.dim = dim
        self.name = model

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        import anyio

        return await anyio.to_thread.run_sync(
            lambda: [v.tolist() for v in self._model.passage_embed(texts)]
        )

    async def embed_query(self, text: str) -> list[float]:
        import anyio

        return await anyio.to_thread.run_sync(
            lambda: next(iter(self._model.query_embed([text]))).tolist()
        )


class OpenAIEmbedder:
    def __init__(self, api_key: str, model: str = "text-embedding-3-small", dim: int = 1536):
        self._client = httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        self.dim = dim
        self.name = model
        self._model = model

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 256):
            r = await self._client.post(
                "/embeddings", json={"model": self._model, "input": texts[i : i + 256]}
            )
            r.raise_for_status()
            out.extend(d["embedding"] for d in sorted(r.json()["data"], key=lambda d: d["index"]))
        return out

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embed(texts)

    async def embed_query(self, text: str) -> list[float]:
        return (await self._embed([text]))[0]

    async def aclose(self) -> None:
        await self._client.aclose()


def build_embedder(provider: str, *, model: str, dim: int, openai_key: str | None) -> Embedder:
    if provider == "fastembed":
        return FastEmbedEmbedder(model, dim)
    if provider == "openai":
        if not openai_key:
            raise ValueError("OPENAI_API_KEY required for openai embeddings")
        return OpenAIEmbedder(openai_key)
    return HashEmbedder(dim)
