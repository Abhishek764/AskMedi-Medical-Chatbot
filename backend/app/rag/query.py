"""Query pipeline: standalone rewrite → normalisation → expansion → intent routing.

Dictionaries here are small seeds. Production grows them from RxNorm (brand → generic) and
MeSH (synonyms); each addition is kept only if golden-set recall improves.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.rag.bm25 import STOPWORDS, tokenize

ABBREVIATIONS: dict[str, str] = {
    "htn": "hypertension",
    "bp": "blood pressure",
    "t2dm": "type 2 diabetes",
    "t1dm": "type 1 diabetes",
    "dm": "diabetes",
    "mi": "myocardial infarction heart attack",
    "uti": "urinary tract infection",
    "copd": "chronic obstructive pulmonary disease",
    "gerd": "gastroesophageal reflux disease",
    "tb": "tuberculosis",
    "ckd": "chronic kidney disease",
    "cad": "coronary artery disease",
    "afib": "atrial fibrillation",
    "ibs": "irritable bowel syndrome",
    "pcos": "polycystic ovary syndrome",
    "adhd": "attention deficit hyperactivity disorder",
    "nsaid": "nonsteroidal anti-inflammatory drug",
    "nsaids": "nonsteroidal anti-inflammatory drugs",
    "std": "sexually transmitted infection",
    "sti": "sexually transmitted infection",
}

BRAND_TO_GENERIC: dict[str, str] = {
    "crocin": "paracetamol",
    "dolo": "paracetamol",
    "calpol": "paracetamol",
    "tylenol": "acetaminophen paracetamol",
    "panadol": "paracetamol",
    "advil": "ibuprofen",
    "brufen": "ibuprofen",
    "motrin": "ibuprofen",
    "glycomet": "metformin",
    "glucophage": "metformin",
    "lipitor": "atorvastatin",
    "zyrtec": "cetirizine",
    "augmentin": "amoxicillin clavulanate",
    "prilosec": "omeprazole",
    "omez": "omeprazole",
    "ecosprin": "aspirin",
    "disprin": "aspirin",
    "allegra": "fexofenadine",
    "ventolin": "salbutamol albuterol",
    "asthalin": "salbutamol albuterol",
}

SYNONYMS: dict[str, str] = {
    "heart attack": "myocardial infarction",
    "high blood pressure": "hypertension",
    "low blood pressure": "hypotension",
    "sugar": "diabetes glucose",
    "blood sugar": "glucose diabetes",
    "kidney": "renal",
    "liver": "hepatic",
    "stroke": "cerebrovascular",
    "piles": "hemorrhoids",
    "jaundice": "hyperbilirubinemia hepatitis",
    "flu": "influenza",
    "cold": "common cold rhinovirus",
    "paracetamol": "acetaminophen",
    "acetaminophen": "paracetamol",
    "loose motion": "diarrhea",
    "loose motions": "diarrhea",
    "acidity": "acid reflux gastritis",
    "fits": "seizures epilepsy",
    "bp": "blood pressure",
}

_PRONOUNS = re.compile(
    r"\b(it|its|this|that|they|them|those|these|he|she|the condition|the drug)\b"
)
_FOLLOWUP = re.compile(r"^(and|also|what about|how about|so|then)\b")

INTENTS: list[tuple[str, re.Pattern[str]]] = [
    (
        "evidence",
        re.compile(
            r"\b(evidence|study|studies|research|trial|effective|does .{0,60} work|proven)\b"
        ),
    ),
    (
        "drug",
        re.compile(
            r"\b(side effects?|medicine|medication|drug|tablet|interaction|contraindicat\w*|warning)\b"
        ),
    ),
    ("symptoms", re.compile(r"\b(symptoms?|signs?)\b")),
    ("treatment", re.compile(r"\b(treat\w*|cure|manage\w*|therapy)\b")),
    ("causes", re.compile(r"\b(cause[sd]?|why|risk factors?)\b")),
    ("prevention", re.compile(r"\b(prevent\w*|avoid|vaccin\w*)\b")),
    ("definition", re.compile(r"^(what is|what are|what's|define|meaning of)\b")),
]

PREFERRED_DOC_TYPES: dict[str, tuple[str, ...]] = {
    "evidence": ("research",),
    "drug": ("label", "consumer"),
}


@dataclass
class QueryPlan:
    original: str
    standalone: str
    normalised: str
    dense_query: str
    sparse_query: str
    intent: str
    preferred_doc_types: tuple[str, ...] = field(default_factory=tuple)


def rewrite_standalone(question: str, history: list[str]) -> str:
    """Heuristic rewrite for short follow-ups; an LLM rewrite can replace it later."""
    q = question.strip()
    if not history:
        return q
    lower = q.lower()
    is_followup = len(q.split()) <= 10 and (_PRONOUNS.search(lower) or _FOLLOWUP.search(lower))
    if not is_followup:
        return q
    prev = history[-1]
    terms = [t for t in tokenize(prev) if t not in STOPWORDS]
    topic = " ".join(dict.fromkeys(terms))
    return f"{q} (about: {topic})" if topic else q


def _expand_tokens(text: str, table: dict[str, str]) -> str:
    out = text
    for key in sorted(table, key=len, reverse=True):
        out = re.sub(rf"\b{re.escape(key)}\b", f"{key} {table[key]}", out)
    return out


def normalise_query(text: str) -> str:
    t = text.lower()
    for table in (ABBREVIATIONS, BRAND_TO_GENERIC):
        for key, val in table.items():
            t = re.sub(rf"\b{re.escape(key)}\b", val, t)
    return re.sub(r"\s+", " ", t).strip()


def detect_intent(text: str) -> str:
    t = text.lower()
    for name, pattern in INTENTS:
        if pattern.search(t):
            return name
    return "general"


def plan_query(question: str, history: list[str] | None = None) -> QueryPlan:
    standalone = rewrite_standalone(question, history or [])
    normalised = normalise_query(standalone)
    intent = detect_intent(normalised)
    return QueryPlan(
        original=question,
        standalone=standalone,
        normalised=normalised,
        dense_query=normalised,
        sparse_query=_expand_tokens(normalised, SYNONYMS),  # synonyms help BM25 only
        intent=intent,
        preferred_doc_types=PREFERRED_DOC_TYPES.get(intent, ()),
    )
