"""Exclusions comparison: which risks each policy excludes, with the clause and page.

Each exclusion clause ("V.D") is split into its numbered items ("V.D.4"); each item is tagged
with the exclusion categories it matches. A category a policy doesn't match is reported as
"not found in the exclusions" — never as "covered", because coverage also depends on the
insuring agreement, definitions, limits and endorsements.

Rules are plain patterns so a reviewer can audit them; an LLM can later add a plain-English
summary on top of these cited cells without changing them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.policies.parse import Clause, PolicyDoc

CATEGORIES: tuple[tuple[str, str, re.Pattern[str]], ...] = tuple(
    (key, label, re.compile(pattern, re.I))
    for key, label, pattern in (
        (
            "economic_loss",
            "Business interruption and other economic loss",
            r"loss of revenue|profits|interruption of business|loss of (use|access)|additional living expense|economic loss",
        ),
        ("ordinance_law", "Cost of complying with ordinances or laws", r"ordinance or law"),
        (
            "flood_in_progress",
            "Flood already in progress",
            r"flood in progress|continuation of a flood",
        ),
        (
            "earth_movement",
            "Earth movement (earthquake, landslide, sinkholes)",
            r"earth movement|earthquake|landslide|sinkhole|subsidence",
        ),
        ("ice_freezing", "Ice, freezing and thawing", r"weight of ice|freezing or thawing"),
        ("weather", "Rain, snow, sleet, hail or water spray", r"rain, snow|sleet|hail"),
        (
            "mold_moisture",
            "Mold, mildew and moisture within the owner's control",
            r"\bmold\b|mildew|moisture",
        ),
        (
            "sewer_seepage",
            "Sewer backup, sump overflow and seepage",
            r"sewers or drains|sump|seeps or leaks",
        ),
        ("water_pressure", "Pressure or weight of water", r"pressure or weight of water"),
        (
            "power_failure",
            "Power, heating or cooling failure",
            r"power, heating, or cooling failure",
        ),
        (
            "other_perils",
            "Theft, fire, explosion, wind and other perils",
            r"\btheft\b|\bfire\b|explosion|\bwind\b|windstorm",
        ),
        ("intentional", "Intentional loss", r"intentional|caused intentionally"),
        ("alteration", "Alteration of the property", r"alteration"),
        (
            "federal_land",
            "Property on land leased from the federal government",
            r"land leased from the federal government",
        ),
        ("pollutants", "Testing or monitoring of pollutants", r"pollutant"),
    )
)

_ITEM = re.compile(r"(?:(?<=[:;.])|^)\s*(\d{1,2})\.\s+")


@dataclass(frozen=True)
class Item:
    id: str
    text: str
    page: int


def items(clause: Clause) -> list[Item]:
    """Numbered sub-items of a clause; the clause itself when it has none."""
    marks = list(_ITEM.finditer(clause.text))
    if not marks:
        return [Item(clause.id, clause.text, clause.page)]
    out = []
    lead = clause.text[: marks[0].start()].strip()
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(clause.text)
        body = clause.text[m.end() : end].strip()
        out.append(
            Item(
                f"{clause.id}.{m.group(1)}",
                f"{lead} … {body}" if lead else body,
                clause.page_at(m.start()),
            )
        )
    return out


def section_items(doc: PolicyDoc, keyword: str) -> list[Item]:
    sec = doc.section(keyword)
    if sec is None:
        return []
    clauses = sec.clauses or [sec.as_clause()]
    return [it for c in clauses for it in items(c)]


def exclusion_items(doc: PolicyDoc) -> list[Item]:
    return section_items(doc, "exclusion")


_WORD = re.compile(r"[a-z]{3,}")


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def diff_section(docs: list[PolicyDoc], keyword: str, threshold: float = 0.5) -> dict[str, object]:
    """Align a section's items across policies by word overlap; report what each one lacks."""
    groups: list[dict[str, object]] = []
    for d in docs:
        for it in section_items(d, keyword):
            toks = _tokens(it.text)
            best, score = None, 0.0
            for g in groups:
                if d.id in g["cells"]:  # type: ignore[operator]
                    continue
                gt = g["tokens"]
                s = len(toks & gt) / max(1, len(toks | gt))  # type: ignore[operator]
                if s > score:
                    best, score = g, s
            cell = {
                "clause": it.id,
                "page": it.page,
                "page_label": d.page_label,
                "text": it.text[:400],
            }
            if best is not None and score >= threshold:
                best["cells"][d.id] = cell  # type: ignore[index]
            else:
                groups.append({"tokens": toks, "summary": it.text[:160], "cells": {d.id: cell}})
    rows = [
        {"summary": g["summary"], "in_all": len(g["cells"]) == len(docs), "cells": g["cells"]}  # type: ignore[arg-type]
        for g in groups
    ]
    return {
        "section": keyword,
        "rows": rows,
        "only_in_some": [r for r in rows if not r["in_all"]],
    }


def compare(docs: list[PolicyDoc]) -> dict[str, object]:
    per_doc = {d.id: exclusion_items(d) for d in docs}
    rows = []
    for key, label, pattern in CATEGORIES:
        cells = {}
        for d in docs:
            hit = next((it for it in per_doc[d.id] if pattern.search(it.text)), None)
            cells[d.id] = (
                {
                    "status": "excluded",
                    "clause": hit.id,
                    "page": hit.page,
                    "page_label": d.page_label,
                    "quote": _quote(hit.text, pattern),
                }
                if hit
                else {"status": "not_found"}
            )
        statuses = {c["status"] for c in cells.values()}
        rows.append({"key": key, "label": label, "differs": len(statuses) > 1, "cells": cells})
    return {
        "policies": [
            {"id": d.id, "title": d.title, "form": d.form, "edition": d.edition} for d in docs
        ],
        "rows": rows,
        "differences": [r["label"] for r in rows if r["differs"]],
        "note": (
            "“Not found” means no matching clause in the policy's exclusions section; it does not "
            "mean the loss is covered. Coverage also depends on the insuring agreement, definitions, "
            "limits and endorsements."
        ),
    }


def _quote(text: str, pattern: re.Pattern[str], width: int = 260) -> str:
    m = pattern.search(text)
    start = max(0, (m.start() if m else 0) - 80)
    snippet = text[start : start + width].strip()
    return ("…" if start else "") + snippet + ("…" if start + width < len(text) else "")
