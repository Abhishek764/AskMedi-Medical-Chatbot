"""Regex PII redaction applied before the LLM, logs and traces.

Covers the identifiers most likely in Indian and US users' messages. Presidio (NER for
names and addresses) can be layered on later behind the same function.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("AADHAAR", re.compile(r"\b[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}\b")),
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("PHONE", re.compile(r"(?<!\w)(?:\+?91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}\b")),
    ("PHONE", re.compile(r"(?<!\w)\+?1?[\s.-]?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b")),
    ("URL", re.compile(r"\bhttps?://\S+")),
]


@dataclass(frozen=True)
class Redaction:
    text: str
    kinds: tuple[str, ...]


def redact(text: str) -> Redaction:
    kinds: list[str] = []
    out = text
    for kind, pattern in _PATTERNS:
        out, n = pattern.subn(f"[{kind}]", out)
        if n:
            kinds.append(kind)
    return Redaction(out, tuple(dict.fromkeys(kinds)))
