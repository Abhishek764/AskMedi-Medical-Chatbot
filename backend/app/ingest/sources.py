"""Fetchers for free, commercially reusable medical sources. Raw responses are cached under
`data/raw/<source>/` so re-runs are cheap and the corpus can be rebuilt offline.

Politeness: MedlinePlus asks for ≤85 requests/min; NCBI E-utilities allows 3/s without a
key; openFDA allows 240/min without a key. We stay well under all three.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from pathlib import Path
from xml.etree import ElementTree as ET  # noqa: S405 - type hints only

import httpx
from defusedxml import ElementTree as SafeET

from app.ingest.parsers import licence_from_url_or_code, parse_jats, parse_label, parse_summary_html
from app.rag.types import SourceDoc

logger = logging.getLogger("askmedi.ingest")
USER_AGENT = "AskMedi-ingest/2.0"


class RateLimiter:
    def __init__(self, per_second: float) -> None:
        self.interval = 1.0 / per_second
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            delta = time.monotonic() - self._last
            if delta < self.interval:
                await asyncio.sleep(self.interval - delta)
            self._last = time.monotonic()


class Fetcher:
    """HTTP GET with on-disk cache, rate limit and retries."""

    def __init__(self, raw_dir: Path, client: httpx.AsyncClient | None = None) -> None:
        self.raw_dir = raw_dir
        self.client = client or httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT}, timeout=60, follow_redirects=True
        )
        self.limits = {
            "medlineplus": RateLimiter(1.0),
            "openfda": RateLimiter(2.0),
            "ncbi": RateLimiter(2.5),
            "s3": RateLimiter(5.0),
        }

    async def get(
        self,
        source: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        cache_name: str | None = None,
        binary: bool = False,
    ) -> bytes:
        key = (
            cache_name
            or hashlib.sha256(
                (url + json.dumps(params or {}, sort_keys=True)).encode()
            ).hexdigest()[:24]
        )
        path = self.raw_dir / source / key
        if path.exists():
            return path.read_bytes()
        for attempt in range(4):
            await self.limits.get(source, self.limits["s3"]).wait()
            try:
                r = await self.client.get(url, params=params)
                if r.status_code == 404:
                    raise FileNotFoundError(url)
                if r.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError("retryable", request=r.request, response=r)
                r.raise_for_status()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(r.content)
                return r.content
            except httpx.HTTPError:
                if attempt == 3:
                    raise
                await asyncio.sleep(2**attempt)
        raise RuntimeError("unreachable")

    async def aclose(self) -> None:
        await self.client.aclose()


# -- MedlinePlus ------------------------------------------------------------------
MEDLINEPLUS_WS = "https://wsearch.nlm.nih.gov/ws/query"


def parse_medlineplus_ws(xml_bytes: bytes, wanted: str) -> SourceDoc | None:
    root = SafeET.fromstring(xml_bytes)
    best = None
    for doc in root.iter("document"):
        topic = doc.find(".//health-topic")
        if topic is None or topic.get("language", "English") != "English":
            continue
        if best is None or topic.get("title", "").lower() == wanted.lower():
            best = topic
            if topic.get("title", "").lower() == wanted.lower():
                break
    return _topic_doc(best) if best is not None else None


def _topic_doc(topic: ET.Element) -> SourceDoc | None:
    """One MedlinePlus <health-topic> element -> SourceDoc (NLM summary only, public domain)."""
    sections = parse_summary_html(topic.findtext("full-summary") or "")
    title = topic.get("title", "")
    if not sections or not title:
        return None
    also = [a.text.strip() for a in topic.findall("also-called") if a.text and a.text.strip()]
    if also:  # synonyms help BM25 match lay and clinical names ("HbA1C" for "A1C")
        sections[0].text = f"Also called: {', '.join(also[:8])}.\n\n{sections[0].text}"
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    created = topic.get("date-created", "")
    year = int(created[-4:]) if created[-4:].isdigit() else None
    return SourceDoc(
        doc_id=f"medlineplus:{slug}",
        source="medlineplus",
        title=title,
        url=topic.get("url"),
        licence="public-domain",  # NLM-authored health topic summaries only
        doc_type="consumer",
        sections=sections,
        year=year,
    )


MEDLINEPLUS_XML_INDEX = "https://medlineplus.gov/xml.html"


def parse_medlineplus_bulk(xml_bytes: bytes) -> list[SourceDoc]:
    """All English health topics from the MedlinePlus bulk XML file (~1,000 topics)."""
    root = SafeET.fromstring(xml_bytes)
    docs = []
    for topic in root.findall("health-topic"):  # top level only; nested ones are links
        if topic.get("language") != "English":
            continue
        doc = _topic_doc(topic)
        if doc is not None:
            docs.append(doc)
    return docs


async def fetch_medlineplus_bulk(fetcher: Fetcher) -> list[SourceDoc]:
    index = await fetcher.get("medlineplus", MEDLINEPLUS_XML_INDEX, cache_name="xml-index.html")
    names = re.findall(rb"mplus_topics_(\d{4}-\d{2}-\d{2})\.xml", index)
    if not names:
        raise RuntimeError("MedlinePlus bulk XML link not found")
    latest = max(n.decode() for n in names)
    raw = await fetcher.get(
        "medlineplus",
        f"https://medlineplus.gov/xml/mplus_topics_{latest}.xml",
        cache_name=f"mplus_topics_{latest}.xml",
    )
    return parse_medlineplus_bulk(raw)


async def fetch_medlineplus(fetcher: Fetcher, topic: str) -> SourceDoc | None:
    raw = await fetcher.get(
        "medlineplus",
        MEDLINEPLUS_WS,
        params={"db": "healthTopics", "term": topic, "rettype": "topic", "retmax": "5"},
        cache_name=f"{re.sub(r'[^a-z0-9]+', '-', topic.lower())}.xml",
    )
    return parse_medlineplus_ws(raw, topic)


# -- openFDA ----------------------------------------------------------------------
OPENFDA_LABEL = "https://api.fda.gov/drug/label.json"


def pick_label(results: list[dict[str, object]], generic: str) -> dict[str, object] | None:
    """Prefer single-ingredient labels whose generic name matches, newest first."""

    def names(r: dict[str, object]) -> list[str]:
        of = r.get("openfda") or {}
        return [n.lower() for n in (of.get("generic_name") or [])]  # type: ignore[union-attr]

    g = generic.lower()
    candidates = [r for r in results if any(g in n for n in names(r))]
    if not candidates:
        return None
    candidates.sort(
        key=lambda r: (
            min(len(n) for n in names(r)),
            -int(str(r.get("effective_time", "0"))[:8] or 0),
        )
    )
    return candidates[0]


def openfda_doc(record: dict[str, object], generic: str) -> SourceDoc | None:
    sections = parse_label(record)
    if not sections:
        return None
    of = record.get("openfda") or {}
    brand = ", ".join((of.get("brand_name") or [])[:2])  # type: ignore[union-attr]
    set_id = str(record.get("set_id", ""))
    eff = str(record.get("effective_time", ""))
    title = f"{generic.title()} — FDA drug label" + (f" ({brand})" if brand else "")
    return SourceDoc(
        doc_id=f"openfda:{set_id}",
        source="openfda",
        title=title,
        url=f"https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid={set_id}",
        licence="cc0",
        doc_type="label",
        sections=sections,
        year=int(eff[:4]) if eff[:4].isdigit() else None,
    )


async def fetch_openfda(fetcher: Fetcher, generic: str) -> SourceDoc | None:
    try:
        raw = await fetcher.get(
            "openfda",
            OPENFDA_LABEL,
            params={"search": f'openfda.generic_name:"{generic}"', "limit": "10"},
            cache_name=f"{re.sub(r'[^a-z0-9]+', '-', generic.lower())}.json",
        )
    except FileNotFoundError:
        return None
    record = pick_label(json.loads(raw).get("results", []), generic)
    return openfda_doc(record, generic) if record else None


# -- PMC Open Access ------------------------------------------------------------------
ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
S3 = "https://pmc-oa-opendata.s3.amazonaws.com"
PMC_LICENCES = {"CC0": "cc0", "CC BY": "cc-by", "CC BY-SA": "cc-by-sa"}


def _clean_term(topic: str) -> str:
    """Topics come from our seed lists, but keep query syntax out of them anyway."""
    return re.sub(r"[^A-Za-z0-9 '-]+", " ", topic).strip()


def pmc_query(topic: str, since_year: int) -> str:
    topic = _clean_term(topic)
    return (
        f'({topic}[title]) AND (review[pt] OR systematic[sb]) AND "open access"[filter] '
        f'AND ("cc by license"[filter] OR "cc0 license"[filter]) '
        f'AND ("{since_year}"[pdat] : "3000"[pdat]) AND english[lang]'
    )


async def search_pmc(fetcher: Fetcher, topic: str, *, limit: int, since_year: int) -> list[str]:
    raw = await fetcher.get(
        "ncbi",
        ESEARCH,
        params={
            "db": "pmc",
            "term": pmc_query(topic, since_year),
            "retmax": str(limit),
            "retmode": "json",
            "sort": "relevance",
            "tool": "askmedi",
        },
        cache_name=f"search-{re.sub(r'[^a-z0-9]+', '-', topic.lower())}-{limit}-{since_year}.json",
    )
    ids = (json.loads(raw).get("esearchresult") or {}).get("idlist") or []
    return [f"PMC{i}" for i in ids if str(i).isdigit()]


async def _latest_prefix(fetcher: Fetcher, pmcid: str) -> str | None:
    raw = await fetcher.get(
        "s3",
        f"{S3}/",
        params={"list-type": "2", "prefix": f"{pmcid}.", "delimiter": "/"},
        cache_name=f"list-{pmcid}.xml",
    )
    prefixes = re.findall(rb"<Prefix>(PMC\d+\.\d+)/</Prefix>", raw)
    if not prefixes:
        return None
    return max((p.decode() for p in prefixes), key=lambda p: int(p.split(".")[1]))


async def fetch_pmc(
    fetcher: Fetcher, pmcid: str, *, download_pdf: bool = True
) -> tuple[SourceDoc | None, str]:
    """Returns (doc, status). Licence and retraction come from PMC's own metadata."""
    prefix = await _latest_prefix(fetcher, pmcid)
    if prefix is None:
        return None, "not_in_oa_bucket"
    meta = json.loads(
        await fetcher.get("s3", f"{S3}/{prefix}/{prefix}.json", cache_name=f"{prefix}.json")
    )
    licence = PMC_LICENCES.get(str(meta.get("license_code", "")).upper().replace("CC-", "CC "))
    if licence is None:
        return None, f"licence_rejected:{meta.get('license_code')}"
    if meta.get("is_retracted"):
        return None, "retracted"
    xml_bytes = await fetcher.get("s3", f"{S3}/{prefix}/{prefix}.xml", cache_name=f"{prefix}.xml")
    if download_pdf and meta.get("pdf_url"):
        try:
            await fetcher.get(
                "s3", f"{S3}/{prefix}/{prefix}.pdf", cache_name=f"{prefix}.pdf", binary=True
            )
        except (FileNotFoundError, httpx.HTTPError):
            logger.warning("pdf download failed for %s", prefix)
    parsed = parse_jats(xml_bytes.decode("utf-8", errors="replace"))
    jats_licence = parsed["licence"]
    if jats_licence not in ("unknown", licence) and jats_licence not in PMC_LICENCES.values():
        return None, f"licence_conflict:{jats_licence}"
    sections = parsed["sections"]
    if not sections:
        return None, "no_text"
    return (
        SourceDoc(
            doc_id=f"pmc:{pmcid}",
            source="pmc",
            title=str(parsed["title"] or meta.get("title", pmcid)),
            url=f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/",
            licence=licence,
            doc_type="research",
            sections=sections,  # type: ignore[arg-type]
            year=parsed["year"],  # type: ignore[arg-type]
            authors=str(parsed["authors"]) or None,
            journal=str(parsed["journal"]) or None,
        ),
        "ok",
    )


def local_pdf_doc(
    path: Path, *, title: str, licence: str, doc_type: str = "reference"
) -> SourceDoc:
    from app.ingest.parsers import parse_pdf

    slug = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")
    return SourceDoc(
        doc_id=f"local:{slug}",
        source="local",
        title=title,
        licence=licence_from_url_or_code(licence) if licence != "public-domain" else licence,
        doc_type=doc_type,  # type: ignore[arg-type]
        sections=parse_pdf(path),
    )
