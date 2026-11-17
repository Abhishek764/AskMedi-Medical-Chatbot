"""Parse insurance policy PDFs into sections and individual clauses, each with its page.

Two layouts:
- CFR forms (FEMA Standard Flood Insurance Policy, 44 CFR Part 61 App. A): page numbers are
  the printed CFR pages; one appendix is cut out of PDFs that also hold its neighbours.
- Any other policy PDF (e.g. an insurer's specimen form): best-effort headings; pages are
  PDF page numbers.

Clauses are split on lettered items ("A.", "B.") inside each top-level section, which is how
both SFIP forms and most commercial forms (e.g. "2. Exclusions … a. Expected or intended
injury") number their exclusions.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROMAN = r"(?:I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII)"
SECTION = re.compile(rf"^({ROMAN})\.\s+([A-Z][A-Z ,'’—-]{{2,}})\s*$")
GENERIC_SECTION = re.compile(
    r"^(SECTION\s+[IVX\d]+|[A-Z][A-Z ,'’—&-]{6,})\s*[-–—:]?\s*([A-Z ,'’&-]*)$"
)
ITEM = re.compile(r"^([A-Z])\.\s+(.*)$")
NOISE = (
    re.compile(r"^VerDate\b"),
    re.compile(r"^Fed\. Emergency Mgmt\. Agency, DHS"),
    re.compile(r"^\d{1,4}\s*$"),
)


@dataclass
class Clause:
    id: str  # e.g. "V.C"
    heading: str  # e.g. "Exclusions"
    text: str
    page: int
    page_end: int
    page_breaks: list[list[int]] = field(
        default_factory=list
    )  # [char offset, page] where pages start

    def page_at(self, offset: int) -> int:
        page = self.page
        for start, p in self.page_breaks:
            if start <= offset:
                page = p
        return page


@dataclass
class Section:
    number: str  # "V"
    title: str  # "EXCLUSIONS"
    text: str
    page: int
    page_end: int
    clauses: list[Clause] = field(default_factory=list)
    page_breaks: list[list[int]] = field(default_factory=list)

    def as_clause(self) -> Clause:
        """The whole section as one clause (for sections without lettered items)."""
        return Clause(
            self.number, self.title.title(), self.text, self.page, self.page_end, self.page_breaks
        )


@dataclass
class PolicyDoc:
    id: str
    title: str
    form: str
    edition: str
    source_url: str
    licence: str
    page_label: str  # how pages are cited: "44 CFR p." or "PDF p."
    sections: list[Section]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> PolicyDoc:
        secs = [
            Section(**{**s, "clauses": [Clause(**c) for c in s["clauses"]]})  # type: ignore[arg-type]
            for s in d["sections"]  # type: ignore[union-attr]
        ]
        return cls(**{**d, "sections": secs})  # type: ignore[arg-type]

    def section(self, keyword: str) -> Section | None:
        return next((s for s in self.sections if keyword.lower() in s.title.lower()), None)


def _pages(path: Path) -> list[str]:
    from pypdf import PdfReader

    logging.getLogger("pypdf").setLevel(logging.ERROR)
    return [p.extract_text() or "" for p in PdfReader(str(path)).pages]


def _lines_with_pages(pages: list[str], printed: bool) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for idx, text in enumerate(pages):
        raw = [ln.rstrip() for ln in text.split("\n")]
        number = idx + 1
        if printed:
            first = next((ln.strip() for ln in raw if ln.strip()), "")
            if first.isdigit():
                number = int(first)
        for ln in raw:
            s = ln.strip()
            if s and not any(p.search(s) for p in NOISE):
                out.append((number, s))
    return out


def _join(lines: list[tuple[int, str]]) -> tuple[str, list[list[int]]]:
    """Join lines into one string; returns it with the offsets where each new page starts."""
    text = ""
    breaks: list[list[int]] = []
    last_page = None
    for page, ln in lines:
        ln = re.sub(r"\s+", " ", ln).replace("‘‘", "“").replace("’’", "”")
        if page != last_page:
            breaks.append([len(text), page])
            last_page = page
        if text.endswith("-") and ln[:1].islower():
            text = text[:-1] + ln  # re-join a word hyphenated across lines
        else:
            text = f"{text} {ln}" if text else ln
    return text.strip(), breaks


def _split(lines: list[tuple[int, str]], heading_re: re.Pattern[str]) -> list[Section]:
    sections: list[Section] = []
    cur: tuple[str, str, list[tuple[int, str]]] | None = None

    def close() -> None:
        if cur is None or not cur[2]:
            return
        number, title, body = cur
        joined, breaks = _join(body)
        sec = Section(
            number, title.strip(" ,"), joined, body[0][0], body[-1][0], page_breaks=breaks
        )
        item: list[tuple[int, str]] = []
        letter = ""
        for page, text in body:
            m = ITEM.match(text)
            if m and (not letter or ord(m.group(1)) == ord(letter) + 1):
                if item:
                    sec.clauses.append(_clause(sec, letter, item))
                letter, item = m.group(1), [(page, text)]
            elif item:
                item.append((page, text))
        if item:
            sec.clauses.append(_clause(sec, letter, item))
        sections.append(sec)

    for page, text in lines:
        m = heading_re.match(text)
        if m:
            close()
            cur = (m.group(1), m.group(2) or m.group(1), [])
        elif cur is not None:
            cur[2].append((page, text))
    close()
    return sections


def _clause(sec: Section, letter: str, item: list[tuple[int, str]]) -> Clause:
    text, breaks = _join(item)
    return Clause(
        f"{sec.number}.{letter}", sec.title.title(), text, item[0][0], item[-1][0], breaks
    )


def parse_cfr_form(path: Path, appendix: str, **meta: str) -> PolicyDoc:
    """Cut 'APPENDIX A(n) TO PART 61' out of a CFR PDF and split it into sections."""
    lines = _lines_with_pages(_pages(path), printed=True)
    start_re = re.compile(rf"^APPENDIX {re.escape(appendix)} TO PART 61", re.I)
    start = next((i for i, (_, t) in enumerate(lines) if start_re.match(t)), None)
    if start is None:
        raise ValueError(f"Appendix {appendix} not found in {path.name}")
    end = next(
        (
            i
            for i, (_, t) in enumerate(lines[start + 1 :], start + 1)
            if re.match(r"^APPENDIX A\(\d\) TO PART 61", t, re.I)
        ),
        len(lines),
    )
    sections = _split(lines[start + 1 : end], SECTION)
    # The first sections (I, II…) can appear twice when a form repeats its table of contents;
    # keep the longest copy of each numbered section.
    best: dict[str, Section] = {}
    for s in sections:
        if s.number not in best or len(s.text) > len(best[s.number].text):
            best[s.number] = s
    ordered = sorted(best.values(), key=lambda s: s.page)
    return PolicyDoc(sections=ordered, page_label="44 CFR p.", **meta)  # type: ignore[arg-type]


def parse_generic_pdf(path: Path, **meta: str) -> PolicyDoc:
    """Best-effort parse of any policy PDF (headings in capitals, lettered clauses)."""
    lines = _lines_with_pages(_pages(path), printed=False)
    sections = _split(lines, GENERIC_SECTION)
    return PolicyDoc(sections=sections, page_label="PDF p.", **meta)  # type: ignore[arg-type]
