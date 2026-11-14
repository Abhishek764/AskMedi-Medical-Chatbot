"""Output verification: citations, groundedness, role filter.

A sentence survives only if it cites passages we actually retrieved, its content words are
supported by those passages, and every number in it appears in them (numbers are where
medical hallucinations hurt most). Public users never get dosing or diagnosis sentences.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.rag.bm25 import tokenize
from app.rag.generate import Draft, ref
from app.rag.types import Retrieved

_NUM = re.compile(r"\d+(?:\.\d+)?")
_DOSING = re.compile(
    r"\b\d+(\.\d+)? ?(mg|mcg|µg|ml|g|iu|units?|tablets?|puffs?|drops?)\b"
    r"|\b(take|give|use)\b.{0,30}\b(times|every|daily|twice|once)\b"
    r"|\b(dose|dosage)\b",
    re.I,
)
_DIAGNOSIS = re.compile(
    r"\byou (have|are suffering from|probably have|likely have|may have)\b", re.I
)


@dataclass
class VerifiedSentence:
    text: str
    citations: list[int]  # indexes into passages


@dataclass
class Verification:
    sentences: list[VerifiedSentence]
    ok: bool
    reason: str | None = None
    dropped: dict[str, int] = field(default_factory=dict)
    support: float = 0.0

    @property
    def text(self) -> str:
        return " ".join(s.text for s in self.sentences)


def support_score(sentence: str, sources: list[str]) -> float:
    toks = set(tokenize(sentence))
    if not toks:
        return 0.0
    src = set()
    for s in sources:
        src |= set(tokenize(s))
    return len(toks & src) / len(toks)


def numbers_supported(sentence: str, sources: list[str]) -> bool:
    joined = " ".join(sources)
    src_nums = set(_NUM.findall(joined))
    return all(n in src_nums for n in _NUM.findall(sentence))


def verify(
    draft: Draft,
    passages: list[Retrieved],
    *,
    role: str,
    threshold: float = 0.5,
    min_kept_ratio: float = 0.5,
) -> Verification:
    if draft.insufficient or not draft.sentences:
        return Verification([], ok=False, reason="no_sources")
    ids = {ref(i): i for i in range(len(passages))}
    kept: list[VerifiedSentence] = []
    dropped = {"citation": 0, "unsupported": 0, "number": 0, "role_filter": 0}
    scores: list[float] = []
    for s in draft.sentences:
        cites = [ids[c] for c in dict.fromkeys(s.refs) if c in ids]
        if not cites:
            dropped["citation"] += 1
            continue
        sources = [passages[i].parent_text for i in cites]
        score = support_score(s.text, sources)
        if score < threshold:
            dropped["unsupported"] += 1
            continue
        if not numbers_supported(s.text, sources):
            dropped["number"] += 1
            continue
        if role not in ("provider", "admin") and (
            _DOSING.search(s.text) or _DIAGNOSIS.search(s.text)
        ):
            dropped["role_filter"] += 1
            continue
        if _DIAGNOSIS.search(s.text):
            dropped["role_filter"] += 1
            continue
        scores.append(score)
        kept.append(VerifiedSentence(s.text, cites))
    total = len(draft.sentences)
    ratio = len(kept) / total
    support = sum(scores) / len(scores) if scores else 0.0
    dropped = {k: v for k, v in dropped.items() if v}
    if not kept or ratio < min_kept_ratio:
        return Verification([], ok=False, reason="unverified", dropped=dropped, support=support)
    return Verification(kept, ok=True, dropped=dropped, support=support)
