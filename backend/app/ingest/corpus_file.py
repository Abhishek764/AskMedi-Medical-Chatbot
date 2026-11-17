"""Portable corpus snapshot: parsed documents as JSONL plus a human-readable manifest.

The JSONL holds every SourceDoc after parsing and the licence gate, so the index can be
rebuilt offline (`python -m app.ingest load`) without re-downloading raw files.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Iterator
from dataclasses import asdict
from pathlib import Path

from app.rag.types import LICENCE_ALLOWLIST, Section, SourceDoc

MANIFEST_FIELDS = [
    "doc_id",
    "source",
    "doc_type",
    "licence",
    "year",
    "title",
    "url",
    "sections",
    "words",
]


def doc_to_json(doc: SourceDoc) -> str:
    return json.dumps(asdict(doc), ensure_ascii=False)


def doc_from_json(line: str) -> SourceDoc:
    data = json.loads(line)
    data["sections"] = [Section(**s) for s in data["sections"]]
    return SourceDoc(**data)


def write_corpus(docs: Iterable[SourceDoc], jsonl_path: Path, manifest_path: Path) -> int:
    """Write allowlisted docs sorted by id (stable diffs). Returns the number written."""
    kept = sorted((d for d in docs if d.licence in LICENCE_ALLOWLIST), key=lambda d: d.doc_id)
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as f:
        for d in kept:
            f.write(doc_to_json(d) + "\n")
    with manifest_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        for d in kept:
            w.writerow(
                {
                    "doc_id": d.doc_id,
                    "source": d.source,
                    "doc_type": d.doc_type,
                    "licence": d.licence,
                    "year": d.year or "",
                    "title": d.title,
                    "url": d.url or "",
                    "sections": len(d.sections),
                    "words": sum(len(s.text.split()) for s in d.sections),
                }
            )
    return len(kept)


def read_corpus(jsonl_path: Path) -> Iterator[SourceDoc]:
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield doc_from_json(line)
