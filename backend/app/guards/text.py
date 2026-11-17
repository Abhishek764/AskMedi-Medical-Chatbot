"""Text normalisation shared by the rule-based guards."""

from __future__ import annotations

import re
import unicodedata

_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "@": "a", "$": "s"})
_NON_WORD = re.compile(r"[^a-z0-9\s']+")
_SPACES = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Lowercase, unicode-fold, strip punctuation, collapse whitespace."""
    t = unicodedata.normalize("NFKC", text).lower()
    t = t.replace("’", "'")
    t = _NON_WORD.sub(" ", t)
    return _SPACES.sub(" ", t).strip()


def variants(text: str) -> list[str]:
    """Plain and de-leeted forms, so 'k1ll mys3lf' still matches."""
    plain = normalise(text)
    deleet = normalise(unicodedata.normalize("NFKC", text).lower().translate(_LEET))
    return [plain] if deleet == plain else [plain, deleet]


def any_match(patterns: list[re.Pattern[str]], texts: list[str]) -> bool:
    return any(p.search(t) for p in patterns for t in texts)


def compile_all(patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(p) for p in patterns]
