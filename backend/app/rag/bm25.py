"""BM25 as Qdrant sparse vectors.

Documents get the BM25 term-frequency part: tf·(k1+1) / (tf + k1·(1 − b + b·dl/avgdl)).
Queries get weight 1 per unique term. The collection's sparse vector uses Qdrant's
`modifier=IDF`, so Qdrant multiplies in the IDF from live collection statistics at query
time. Dot product of the two = the BM25 score. No model download, no external service.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass

_TOKEN = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*")

STOPWORDS = frozenset(
    """a about above after again against all am an and any are as at be because been before
    being below between both but by can could did do does doing down during each few for from
    further had has have having he her here hers herself him himself his how i if in into is it
    its itself just me more most my myself no nor not now of off on once only or other our ours
    ourselves out over own same she should so some such than that the their theirs them
    themselves then there these they this those through to too under until up very was we
    were what when where which while who whom why will with would you your yours yourself
    yourselves also may might must shall within without per via vs etc""".split()
)


def tokenize(text: str) -> list[str]:
    toks = _TOKEN.findall(text.lower())
    return [_light_stem(t) for t in toks if t not in STOPWORDS and len(t) > 1]


def _light_stem(tok: str) -> str:
    """Tiny suffix folding so 'infections'/'infection' and 'symptoms'/'symptom' match."""
    if len(tok) > 4 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith(("ss", "us", "is")):
        return tok[:-1]
    return tok


def term_id(term: str) -> int:
    return (
        int.from_bytes(hashlib.blake2b(term.encode(), digest_size=4).digest(), "big") & 0x7FFFFFFF
    )


@dataclass(frozen=True)
class SparseVec:
    indices: list[int]
    values: list[float]


class BM25Encoder:
    def __init__(self, k1: float = 1.2, b: float = 0.75, avgdl: float = 180.0) -> None:
        self.k1, self.b, self.avgdl = k1, b, avgdl

    def encode_document(self, text: str) -> SparseVec:
        toks = tokenize(text)
        dl = len(toks) or 1
        tf = Counter(toks)
        weights: dict[int, float] = {}
        norm = self.k1 * (1 - self.b + self.b * dl / self.avgdl)
        for term, f in tf.items():
            tid = term_id(term)
            weights[tid] = weights.get(tid, 0.0) + f * (self.k1 + 1) / (f + norm)
        return SparseVec(list(weights), list(weights.values()))

    def encode_query(self, text: str) -> SparseVec:
        ids = sorted({term_id(t) for t in tokenize(text)})
        return SparseVec(ids, [1.0] * len(ids))
