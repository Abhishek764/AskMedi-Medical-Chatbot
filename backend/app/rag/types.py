"""Shared data types for ingestion and retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

DocType = Literal["consumer", "label", "research", "reference"]

# Licences safe for commercial use (see docs/corpus-plan.md §1). Anything else is rejected.
LICENCE_ALLOWLIST = frozenset({"public-domain", "cc0", "cc-by", "cc-by-sa", "us-gov"})


@dataclass
class Section:
    path: list[str]  # e.g. ["Treatment", "Medicines"]
    text: str
    is_table: bool = False
    dosing: bool = False


@dataclass
class SourceDoc:
    doc_id: str  # stable, e.g. "medlineplus:asthma", "pmc:PMC123", "fda:<set_id>"
    source: str  # medlineplus | openfda | pmc | cdc | local
    title: str
    licence: str
    doc_type: DocType
    sections: list[Section]
    url: str | None = None
    year: int | None = None
    lang: str = "en"
    authors: str | None = None
    journal: str | None = None
    retracted: bool = False


@dataclass
class Parent:
    id: str
    doc_id: str
    header: str
    text: str


@dataclass
class Chunk:
    id: str
    parent_id: str
    doc_id: str
    text: str  # child text with contextual header, what gets embedded and BM25-indexed
    payload: dict[str, object] = field(default_factory=dict)


@dataclass
class Retrieved:
    chunk_id: str
    parent_id: str
    doc_id: str
    text: str
    score: float  # fused or rerank score
    payload: dict[str, object]
    parent_text: str = ""
