"""Structure-aware parent–child chunking.

- Parent = one document section (split into parts if longer than `parent_words`). The LLM
  sees parents, so answers get the whole section's context.
- Child = sentence-aligned window of ~`child_words` with overlap. Children are what we
  embed and BM25-index, so retrieval is precise.
- Every child carries a contextual header (title › section · source · year) so both the
  dense and the BM25 side know where the text comes from.
- IDs are deterministic (uuid5), so re-ingesting the same document is an idempotent upsert.
"""

from __future__ import annotations

import re
import uuid

from app.rag.types import Chunk, Parent, SourceDoc

_NS = uuid.UUID("6f1c2a52-4d1b-4a4e-9a0e-2b1e7c3d9f10")
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])|\n{2,}")


def stable_id(*parts: object) -> str:
    return str(uuid.uuid5(_NS, "|".join(str(p) for p in parts)))


def header_for(doc: SourceDoc, path: list[str]) -> str:
    crumbs = " › ".join([doc.title, *path]) if path else doc.title
    meta = " · ".join(str(x) for x in (doc.source, doc.year) if x)
    return f"{crumbs} · {meta}" if meta else crumbs


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(text) if s and s.strip()]


def _windows(sentences: list[str], size: int, overlap: int) -> list[str]:
    out: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for sent in sentences:
        n = len(sent.split())
        if cur and cur_len + n > size:
            out.append(" ".join(cur))
            keep: list[str] = []
            kept = 0
            for s in reversed(cur):  # carry trailing sentences as overlap
                kept += len(s.split())
                if kept > overlap:
                    break
                keep.insert(0, s)
            cur, cur_len = keep, sum(len(s.split()) for s in keep)
        cur.append(sent)
        cur_len += n
    if cur:
        out.append(" ".join(cur))
    return out


def chunk_document(
    doc: SourceDoc,
    *,
    child_words: int = 220,
    overlap_words: int = 40,
    parent_words: int = 1100,
    corpus_version: str = "corpus-v1",
) -> tuple[list[Parent], list[Chunk]]:
    parents: list[Parent] = []
    chunks: list[Chunk] = []
    for s_idx, section in enumerate(doc.sections):
        text = section.text.strip()
        if not text:
            continue
        header = header_for(doc, section.path)
        sentences = [text] if section.is_table else split_sentences(text)
        parent_parts = _windows(sentences, parent_words, 0) if not section.is_table else [text]
        for p_idx, parent_text in enumerate(parent_parts):
            parent_id = stable_id(doc.doc_id, s_idx, "/".join(section.path), p_idx)
            parents.append(Parent(parent_id, doc.doc_id, header, parent_text))
            child_texts = (
                [parent_text]
                if section.is_table
                else _windows(split_sentences(parent_text), child_words, overlap_words)
            )
            for c_idx, child in enumerate(child_texts):
                chunks.append(
                    Chunk(
                        id=stable_id(parent_id, c_idx),
                        parent_id=parent_id,
                        doc_id=doc.doc_id,
                        text=f"{header}\n{child}",
                        payload={
                            "doc_id": doc.doc_id,
                            "parent_id": parent_id,
                            "title": doc.title,
                            "section": " › ".join(section.path) or None,
                            "source": doc.source,
                            "url": doc.url,
                            "licence": doc.licence,
                            "doc_type": doc.doc_type,
                            "year": doc.year,
                            "lang": doc.lang,
                            "retracted": doc.retracted,
                            "dosing": section.dosing,
                            "is_table": section.is_table,
                            "corpus_version": corpus_version,
                        },
                    )
                )
    return parents, chunks
