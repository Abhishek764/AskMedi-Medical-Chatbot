"""Parsers: MedlinePlus HTML summaries, openFDA label JSON, PMC JATS XML, PDF text."""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET  # noqa: S405 - types only; parsing goes through defusedxml
from html.parser import HTMLParser
from pathlib import Path

from defusedxml import ElementTree as SafeET

from app.rag.types import Section

_WS = re.compile(r"[ \t\r\f\v]+")


def clean(text: str) -> str:
    text = html.unescape(text)
    text = _WS.sub(" ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


# -- HTML (MedlinePlus full-summary) -------------------------------------------
class _SummaryHTML(HTMLParser):
    """Splits on <h2>/<h3> headings; keeps paragraph and list text; drops tags."""

    def __init__(self) -> None:
        super().__init__()
        self.sections: list[tuple[str, list[str]]] = [("Summary", [])]
        self._in_heading = False
        self._heading: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("h2", "h3", "h4"):
            self._in_heading, self._heading = True, []
        elif tag in ("p", "li", "br"):
            self.sections[-1][1].append("\n")
        if tag == "li":
            self.sections[-1][1].append("- ")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("h2", "h3", "h4") and self._in_heading:
            self._in_heading = False
            self.sections.append((clean("".join(self._heading)).rstrip("?:") or "Section", []))

    def handle_data(self, data: str) -> None:
        (self._heading if self._in_heading else self.sections[-1][1]).append(data)


def parse_summary_html(markup: str) -> list[Section]:
    p = _SummaryHTML()
    p.feed(markup)
    out = []
    for title, parts in p.sections:
        text = clean("".join(parts))
        if text:
            out.append(Section([title], text))
    return out


# -- openFDA label --------------------------------------------------------------
LABEL_SECTIONS: list[tuple[str, str, bool]] = [
    # (json field, heading, dosing?)  'overdosage' is deliberately excluded (lethality info).
    ("boxed_warning", "Boxed Warning", False),
    ("indications_and_usage", "Indications and Usage", False),
    ("contraindications", "Contraindications", False),
    ("warnings_and_cautions", "Warnings and Precautions", False),
    ("warnings", "Warnings", False),
    ("precautions", "Precautions", False),
    ("adverse_reactions", "Adverse Reactions", False),
    ("drug_interactions", "Drug Interactions", False),
    ("pregnancy", "Pregnancy", False),
    ("pediatric_use", "Pediatric Use", False),
    ("geriatric_use", "Geriatric Use", False),
    ("mechanism_of_action", "Mechanism of Action", False),
    ("information_for_patients", "Information for Patients", False),
    ("purpose", "Purpose", False),
    ("uses", "Uses", False),
    ("do_not_use", "Do Not Use", False),
    ("stop_use", "Stop Use", False),
    ("dosage_and_administration", "Dosage and Administration", True),
    ("dosage_forms_and_strengths", "Dosage Forms and Strengths", True),
    ("directions", "Directions", True),
]
_SECTION_NUMBER = re.compile(r"^\s*\d+(\.\d+)*\s+(?:[A-Z&]{2,}\s+)+")

# OTC "Drug Facts" panel, in the order printed on the box. Headings are the keys the symptom
# check reads, so keep them stable. Directions carry the label dose and are flagged dosing.
OTC_SECTIONS: list[tuple[str, str, bool]] = [
    ("active_ingredient", "Active ingredient", False),
    ("purpose", "Purpose", False),
    ("indications_and_usage", "Uses", False),
    ("do_not_use", "Do not use", False),
    ("ask_doctor", "Ask a doctor before use", False),
    ("ask_doctor_or_pharmacist", "Ask a doctor or pharmacist before use", False),
    ("when_using", "When using this product", False),
    ("stop_use", "Stop use and ask a doctor", False),
    ("pregnancy_or_breast_feeding", "Pregnancy or breast-feeding", False),
    ("warnings", "Warnings", False),
    ("dosage_and_administration", "Directions", True),
]
_OTC_BULLETS = re.compile(r"\s*[■▪●•]\s*")
# Labels repeat the heading at the start of each field ("Uses temporarily relieves ...").
_OTC_LEADS = re.compile(
    r"^(active ingredients?(\s*\([^)]*\))?|purposes?|uses|directions|do not use|"
    r"ask a doctor( or pharmacist)? before use( if you( have| are)?)?|"
    r"when using this product|stop use and ask a doctor if|if pregnant or breast-feeding,?)\s*:?\s*",
    re.I,
)


def parse_otc_label(record: dict[str, object]) -> list[Section]:
    out = []
    for field, heading, dosing in OTC_SECTIONS:
        val = record.get(field)
        if not isinstance(val, list) or not val:
            continue
        text = clean("\n\n".join(str(v) for v in val))
        text = _OTC_BULLETS.sub("\n- ", text).strip()
        text = re.sub(r"^drug facts\s*", "", text, flags=re.I)
        if heading not in (
            "Ask a doctor before use",
            "Ask a doctor or pharmacist before use",
            "Stop use and ask a doctor",
            "Pregnancy or breast-feeding",
        ):
            text = _OTC_LEADS.sub("", text, count=1)
        if len(text) > 3:
            out.append(Section([heading], text, dosing=dosing))
    return out


def parse_label(record: dict[str, object]) -> list[Section]:
    out = []
    for field, heading, dosing in LABEL_SECTIONS:
        val = record.get(field)
        if not isinstance(val, list) or not val:
            continue
        text = clean("\n\n".join(str(v) for v in val))
        text = _SECTION_NUMBER.sub("", text, count=1)  # drop "1 INDICATIONS AND USAGE" prefix
        if len(text) > 40:
            out.append(Section([heading], text, dosing=dosing))
    return out


# -- JATS (PMC) -----------------------------------------------------------------
SKIP_SECS = re.compile(
    r"(reference|acknowledg|funding|conflict|competing|author contrib|supplementary|abbreviation|"
    r"data availability|ethics|declaration|disclosure)",
    re.I,
)


def _text(el: ET.Element | None) -> str:
    return clean("".join(el.itertext())) if el is not None else ""


def parse_jats(xml_text: str) -> dict[str, object]:
    root = SafeET.fromstring(xml_text)
    article = root if root.tag == "article" else root.find(".//article")
    if article is None:
        raise ValueError("no <article> element")
    meta = article.find(".//article-meta")
    title = _text(meta.find(".//article-title")) if meta is not None else ""
    journal = _text(article.find(".//journal-title"))
    year = None
    for pd in article.iter("pub-date"):
        y = pd.findtext("year")
        if y and y.isdigit():
            year = int(y)
            break
    licence_url = ""
    for lic in article.iter("license"):
        href = next((v for k, v in lic.attrib.items() if k.endswith("href")), "")
        licence_url = href or _text(lic)
        if not href:
            for ext in lic.iter("ext-link"):
                licence_url = next((v for k, v in ext.attrib.items() if k.endswith("href")), "")
        break
    authors = [
        f"{_text(c.find('name/surname'))}".strip()
        for c in article.iter("contrib")
        if c.get("contrib-type") == "author"
    ]
    sections: list[Section] = []
    abstract = article.find(".//abstract")
    if abstract is not None:
        sections.append(Section(["Abstract"], _text(abstract)))
    body = article.find("body")
    if body is not None:
        for sec in body.findall("sec"):
            _walk_sec(sec, [], sections)
    return {
        "title": title,
        "journal": journal,
        "year": year,
        "licence": licence_from_url_or_code(licence_url),
        "authors": ", ".join(a for a in authors[:3] if a) + (" et al." if len(authors) > 3 else ""),
        "sections": sections,
    }


def _walk_sec(sec: ET.Element, path: list[str], out: list[Section]) -> None:
    title = _text(sec.find("title")) or "Section"
    if SKIP_SECS.search(title):
        return
    here = [*path, title]
    paras = [_text(p) for p in sec.findall("p")]
    for tw in sec.findall("table-wrap"):
        caption = _text(tw.find("caption"))
        rows = [" | ".join(_text(c) for c in tr) for tr in tw.iter("tr")]
        if rows:
            out.append(Section([*here, caption or "Table"], "\n".join(rows), is_table=True))
    text = "\n\n".join(p for p in paras if p)
    if text:
        out.append(Section(here, text))
    for child in sec.findall("sec"):
        _walk_sec(child, here, out)


def licence_from_url_or_code(value: str) -> str:
    v = value.lower().replace("_", "-").strip()
    if not v:
        return "unknown"
    if "publicdomain/zero" in v or v in ("cc0", "cc 0"):
        return "cc0"
    if "publicdomain/mark" in v or "public domain" in v:
        return "public-domain"
    m = re.search(r"licenses/([a-z-]+)/", v)
    code = m.group(1) if m else v.replace("cc ", "cc-").replace(" ", "-")
    code = code if code.startswith("cc-") else f"cc-{code}"
    return code


# -- PDF ------------------------------------------------------------------------
_HEADING = re.compile(r"^(?:\d+(?:\.\d+)*\.?\s+)?[A-Z][A-Za-z ,&/()-]{2,60}$")


def parse_pdf(path: Path) -> list[Section]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    sections: list[Section] = []
    current_title = "Page 1"
    buf: list[str] = []
    for page_no, page in enumerate(reader.pages, start=1):
        for line in (page.extract_text() or "").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            words = stripped.split()
            if _HEADING.match(stripped) and len(words) <= 8 and not stripped.endswith("."):
                if buf:
                    sections.append(Section([current_title], clean(" ".join(buf))))
                current_title, buf = f"{stripped} (p. {page_no})", []
            else:
                buf.append(stripped)
    if buf:
        sections.append(Section([current_title], clean(" ".join(buf))))
    return [s for s in sections if len(s.text) > 80]
