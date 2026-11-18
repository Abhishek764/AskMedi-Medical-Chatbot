"""Policy library: load parsed policies, index their clauses, answer questions with page
citations, and compare exclusions.

Kept apart from the medical assistant: its own Qdrant collection, its own endpoint, and no
medical scope or dosing rules. Prompt-injection screening and cite-or-refuse still apply.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.guards.rules import INJECTION
from app.guards.text import any_match, variants
from app.policies.compare import compare, diff_section, items
from app.policies.parse import PolicyDoc
from app.rag.bm25 import BM25Encoder
from app.rag.chunking import chunk_document
from app.rag.embeddings import Embedder
from app.rag.generate import ExtractiveGenerator
from app.rag.query import plan_query
from app.rag.rerank import Reranker
from app.rag.retriever import HybridRetriever
from app.rag.store import VectorStore
from app.rag.types import Section, SourceDoc
from app.rag.verify import verify

COLLECTION = "policies-v1"
NO_ANSWER = "I couldn't find that in these policies, so I won't guess. Check the full policy or ask the insurer."


def to_source_doc(doc: PolicyDoc) -> SourceDoc:
    """One indexed section per clause item, its clause id and page in the heading."""
    sections = []
    for sec in doc.sections:
        clauses = sec.clauses or [sec.as_clause()]
        for c in clauses:
            for it in items(c):
                sections.append(
                    Section([sec.title.title(), f"{it.id} ({doc.page_label} {it.page})"], it.text)
                )
    return SourceDoc(
        doc_id=f"policy:{doc.id}",
        source="policy",
        title=doc.title,
        licence=doc.licence,
        doc_type="reference",
        sections=sections,
        url=doc.source_url,
    )


def load_policies(directory: Path) -> dict[str, PolicyDoc]:
    if not directory.exists():
        return {}
    docs = {}
    for p in sorted(directory.glob("*.json")):
        doc = PolicyDoc.from_dict(json.loads(p.read_text(encoding="utf-8")))
        docs[doc.id] = doc
    return docs


@dataclass
class PolicyAnswer:
    answer: list[dict[str, object]]  # [{text, citations: [n]}]
    citations: list[dict[str, object]]
    refused: bool
    message: str | None = None


class PolicyLibrary:
    def __init__(
        self,
        directory: Path,
        store: VectorStore,
        embedder: Embedder,
        reranker: Reranker,
        bm25: BM25Encoder,
        abstain_threshold: float,
    ) -> None:
        self.directory = directory
        self.store = store
        self.retriever = HybridRetriever(
            store, embedder, reranker, bm25, retrieve_k=30, context_k=4
        )
        self.embedder, self.bm25 = embedder, bm25
        self.abstain_threshold = abstain_threshold
        self.generator = ExtractiveGenerator(max_sentences=3)

    def load(self) -> dict[str, PolicyDoc]:
        return load_policies(self.directory)

    def save(self, doc: PolicyDoc) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{doc.id}.json"
        path.write_text(json.dumps(doc.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
        return path

    async def index(self, doc: PolicyDoc) -> int:
        await self.store.ensure()
        src = to_source_doc(doc)
        parents, chunks = chunk_document(src, corpus_version=COLLECTION)
        dense = await self.embedder.embed_documents([c.text for c in chunks])
        await self.store.delete_doc(src.doc_id)
        await self.store.upsert(
            parents, chunks, dense, [self.bm25.encode_document(c.text) for c in chunks]
        )
        return len(chunks)

    def summaries(self) -> list[dict[str, object]]:
        return [
            {
                "id": d.id,
                "title": d.title,
                "form": d.form,
                "edition": d.edition,
                "source_url": d.source_url,
                "sections": [
                    {"number": s.number, "title": s.title.title(), "page": s.page}
                    for s in d.sections
                ],
            }
            for d in self.load().values()
        ]

    def _pick(self, ids: list[str]) -> list[PolicyDoc]:
        docs = self.load()
        missing = [i for i in ids if i not in docs]
        if missing:
            raise KeyError(", ".join(missing))
        return [docs[i] for i in ids] if ids else list(docs.values())

    def compare(self, ids: list[str]) -> dict[str, object]:
        return compare(self._pick(ids))

    def diff(self, ids: list[str], section: str) -> dict[str, object]:
        return diff_section(self._pick(ids), section)

    async def ask(self, question: str, ids: list[str]) -> PolicyAnswer:
        if any_match(INJECTION, variants(question)):
            return PolicyAnswer([], [], True, "I can only answer questions about these policies.")
        wanted = {f"policy:{i}" for i in ids} if ids else None
        ranked, _ = await self.retriever.rank(plan_query(question), allow_dosing=False)
        if wanted:
            ranked = [r for r in ranked if r.doc_id in wanted]
        best: dict[str, object] = {}
        for r in ranked:
            best.setdefault(r.parent_id, r)
        passages = list(best.values())[:4]
        if not passages or passages[0].score < self.abstain_threshold:  # type: ignore[attr-defined]
            return PolicyAnswer([], [], True, NO_ANSWER)
        parents = await self.store.get_parents([p.parent_id for p in passages])  # type: ignore[attr-defined]
        for p in passages:
            par = parents.get(p.parent_id)  # type: ignore[attr-defined]
            p.parent_text = str(par["text"]) if par else p.text.split("\n", 1)[-1]  # type: ignore[attr-defined]
        draft = await self.generator.generate(question, passages, role="public")  # type: ignore[arg-type]
        checked = verify(draft, passages, role="public", medical=False)  # type: ignore[arg-type]
        if not checked.ok:
            return PolicyAnswer([], [], True, NO_ANSWER)
        used: dict[int, int] = {}
        for s in checked.sentences:
            for c in s.citations:
                used.setdefault(c, len(used) + 1)
        citations = [
            {
                "position": pos,
                "policy": passages[i].payload.get("title"),  # type: ignore[attr-defined]
                "clause": passages[i].payload.get("section"),
                "url": passages[i].payload.get("url"),
            }  # type: ignore[attr-defined]
            for i, pos in used.items()
        ]
        answer = [
            {"text": s.text, "citations": [used[c] for c in s.citations]} for s in checked.sentences
        ]
        return PolicyAnswer(answer, citations, False)
