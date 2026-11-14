"""Ingest SourceDocs into Qdrant and the Postgres registry.

licence gate → empty check → content hash (skip unchanged) → delete old chunks → chunk →
embed + BM25 → upsert → registry row. Re-running with the same input changes nothing.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Document
from app.rag.bm25 import BM25Encoder
from app.rag.chunking import chunk_document
from app.rag.embeddings import Embedder
from app.rag.store import VectorStore
from app.rag.types import LICENCE_ALLOWLIST, SourceDoc


@dataclass
class IngestReport:
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    chunks: int = 0
    rejected: Counter[str] = field(default_factory=Counter)
    by_source: Counter[str] = field(default_factory=Counter)

    def as_dict(self) -> dict[str, object]:
        return {
            "added": self.added,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "chunks": self.chunks,
            "rejected": dict(self.rejected),
            "by_source": dict(self.by_source),
        }


def content_hash(doc: SourceDoc) -> str:
    h = hashlib.sha256()
    for s in doc.sections:
        h.update("/".join(s.path).encode())
        h.update(s.text.encode())
    return h.hexdigest()


class Ingestor:
    def __init__(
        self,
        store: VectorStore,
        embedder: Embedder,
        bm25: BM25Encoder,
        sessionmaker: async_sessionmaker[AsyncSession],
        *,
        corpus_version: str,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.bm25 = bm25
        self.sessionmaker = sessionmaker
        self.corpus_version = corpus_version
        self._seen_hashes: set[str] = set()

    async def ingest(
        self, docs: list[SourceDoc], report: IngestReport | None = None
    ) -> IngestReport:
        report = report or IngestReport()
        for doc in docs:
            await self._one(doc, report)
        return report

    async def _one(self, doc: SourceDoc, report: IngestReport) -> None:
        if doc.licence not in LICENCE_ALLOWLIST:
            report.rejected[f"licence:{doc.licence}"] += 1
            return
        if doc.retracted:
            report.rejected["retracted"] += 1
            return
        if not any(s.text.strip() for s in doc.sections):
            report.rejected["no_text"] += 1
            return
        digest = content_hash(doc)
        if digest in self._seen_hashes:
            report.rejected["duplicate"] += 1
            return
        self._seen_hashes.add(digest)

        async with self.sessionmaker() as s:
            row = await s.get(Document, doc.doc_id)
            if (
                row is not None
                and row.sha256 == digest
                and row.corpus_version == self.corpus_version
            ):
                report.unchanged += 1
                return
            parents, chunks = chunk_document(doc, corpus_version=self.corpus_version)
            dense = await self.embedder.embed_documents([c.text for c in chunks])
            sparse = [self.bm25.encode_document(c.text) for c in chunks]
            await self.store.delete_doc(doc.doc_id)
            await self.store.upsert(parents, chunks, dense, sparse)
            values = {
                "source": doc.source,
                "title": doc.title[:500],
                "url": doc.url,
                "licence": doc.licence,
                "doc_type": doc.doc_type,
                "year": doc.year,
                "lang": doc.lang,
                "sha256": digest,
                "corpus_version": self.corpus_version,
                "chunk_count": len(chunks),
                "retracted": doc.retracted,
            }
            if row is None:
                s.add(Document(id=doc.doc_id, **values))
                report.added += 1
            else:
                for k, v in values.items():
                    setattr(row, k, v)
                report.updated += 1
            await s.commit()
        report.chunks += len(chunks)
        report.by_source[doc.source] += 1
