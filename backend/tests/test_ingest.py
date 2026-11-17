import json

import httpx
import pytest
from qdrant_client import AsyncQdrantClient

from app.db.models import Document
from app.ingest.parsers import licence_from_url_or_code, parse_jats, parse_label, parse_summary_html
from app.ingest.pipeline import Ingestor
from app.ingest.sources import Fetcher, fetch_pmc, parse_medlineplus_ws, pick_label, pmc_query
from app.rag.bm25 import BM25Encoder
from app.rag.embeddings import HashEmbedder
from app.rag.store import VectorStore
from tests.fixtures import DOCS

MEDLINEPLUS_XML = b"""<?xml version="1.0"?><nlmSearchResult><list>
<document url="https://medlineplus.gov/asthma.html"><content name="healthTopic">
<health-topic title="Asthma" url="https://medlineplus.gov/asthma.html" language="English" date-created="10/22/1998">
<full-summary>&lt;h3&gt;What is asthma?&lt;/h3&gt;&lt;p&gt;Asthma is a chronic lung disease.&lt;/p&gt;
&lt;h3&gt;What are the symptoms?&lt;/h3&gt;&lt;ul&gt;&lt;li&gt;Wheezing&lt;/li&gt;&lt;li&gt;Coughing&lt;/li&gt;&lt;/ul&gt;</full-summary>
</health-topic></content></document></list></nlmSearchResult>"""

JATS = """<article><front><journal-meta><journal-title-group><journal-title>Lancet</journal-title>
</journal-title-group></journal-meta><article-meta><title-group><article-title>Asthma review</article-title>
</title-group><contrib-group><contrib contrib-type="author"><name><surname>Smith</surname></name></contrib>
</contrib-group><pub-date><year>2023</year></pub-date><permissions><license xmlns:xlink="http://www.w3.org/1999/xlink"
xlink:href="https://creativecommons.org/licenses/by/4.0/"><license-p>CC BY</license-p></license></permissions>
<abstract><p>Asthma affects 300 million people.</p></abstract></article-meta></front>
<body><sec><title>Treatment</title><p>Inhaled corticosteroids reduce exacerbations.</p>
<table-wrap><caption>Drugs</caption><table><tr><td>ICS</td><td>first line</td></tr></table></table-wrap>
<sec><title>Biologics</title><p>Biologics help severe asthma.</p></sec></sec>
<sec><title>References</title><p>skip me</p></sec></body></article>"""


def test_parse_medlineplus():
    doc = parse_medlineplus_ws(MEDLINEPLUS_XML, "asthma")
    assert doc.doc_id == "medlineplus:asthma" and doc.licence == "public-domain"
    titles = [s.path[0] for s in doc.sections]
    assert titles == ["What is asthma", "What are the symptoms"]
    assert "- Wheezing" in doc.sections[1].text


def test_parse_summary_html_handles_plain_text():
    assert parse_summary_html("<p>Just text.</p>")[0].text == "Just text."


def test_label_parser_excludes_overdosage_and_flags_dosing():
    rec = {
        "indications_and_usage": [
            "1 INDICATIONS AND USAGE Metformin is indicated for type 2 diabetes in adults."
        ],
        "overdosage": [
            "Overdose of metformin has occurred, including ingestion of amounts greater than 50 grams."
        ],
        "dosage_and_administration": [
            "2 DOSAGE AND ADMINISTRATION Start 500 mg orally twice daily with meals."
        ],
    }
    sections = parse_label(rec)
    heads = {s.path[0]: s for s in sections}
    assert "Overdosage" not in " ".join(heads)
    assert heads["Dosage and Administration"].dosing is True
    assert heads["Indications and Usage"].text.startswith("Metformin")


def test_pick_label_prefers_single_ingredient():
    combo = {
        "openfda": {"generic_name": ["SITAGLIPTIN AND METFORMIN HYDROCHLORIDE"]},
        "effective_time": "20260101",
    }
    single = {
        "openfda": {"generic_name": ["METFORMIN HYDROCHLORIDE"]},
        "effective_time": "20250101",
    }
    assert pick_label([combo, single], "metformin") is single


def test_parse_jats_sections_tables_licence():
    parsed = parse_jats(JATS)
    assert parsed["title"] == "Asthma review" and parsed["year"] == 2023
    assert parsed["licence"] == "cc-by" and parsed["journal"] == "Lancet"
    paths = [s.path for s in parsed["sections"]]
    assert ["Abstract"] in paths and ["Treatment", "Biologics"] in paths
    assert not any("References" in p for p in paths)
    assert any(s.is_table for s in parsed["sections"])


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://creativecommons.org/licenses/by-nc-nd/4.0/", "cc-by-nc-nd"),
        ("https://creativecommons.org/licenses/by-sa/4.0/", "cc-by-sa"),
        ("https://creativecommons.org/publicdomain/zero/1.0/", "cc0"),
        ("", "unknown"),
        ("cc-by", "cc-by"),
    ],
)
def test_licence_normalisation(value, expected):
    assert licence_from_url_or_code(value) == expected


def test_pmc_query_strips_syntax():
    q = pmc_query('asthma") OR (x[all]', 2016)
    assert '")' not in q.split("[title]")[0]


async def test_fetch_pmc_rejects_nc_licence_and_retracted(tmp_path):
    meta = {
        "111": {"license_code": "CC BY-NC", "is_retracted": False},
        "222": {"license_code": "CC BY", "is_retracted": True},
    }

    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        for key in meta:
            if f"prefix=PMC{key}" in url or f"prefix=PMC{key}." in url:
                return httpx.Response(200, content=f"<x><Prefix>PMC{key}.1/</Prefix></x>".encode())
        for key, m in meta.items():
            if url.endswith(f"PMC{key}.1.json"):
                return httpx.Response(200, json=m)
        return httpx.Response(404)

    f = Fetcher(tmp_path, httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    doc, status = await fetch_pmc(f, "PMC111", download_pdf=False)
    assert doc is None and status.startswith("licence_rejected")
    doc, status = await fetch_pmc(f, "PMC222", download_pdf=False)
    assert doc is None and status == "retracted"


async def test_ingestor_licence_gate_and_idempotency(app):
    c = app.state.container
    emb = HashEmbedder(64)
    store = VectorStore(AsyncQdrantClient(":memory:"), "ingest-test", emb.dim)
    await store.ensure()
    ing = Ingestor(store, emb, BM25Encoder(), c.sessionmaker, corpus_version="v-test")
    r1 = await ing.ingest(DOCS)
    assert r1.added == 3 and r1.rejected["licence:cc-by-nc"] == 1
    n = await store.count()
    assert n == r1.chunks > 0

    ing2 = Ingestor(store, emb, BM25Encoder(), c.sessionmaker, corpus_version="v-test")
    r2 = await ing2.ingest(DOCS)
    assert r2.unchanged == 3 and r2.added == 0 and await store.count() == n

    async with c.sessionmaker() as s:
        row = await s.get(Document, "fda:metformin")
        assert row.licence == "cc0" and row.chunk_count > 0
    await store.close()


async def test_fetcher_caches_to_disk(tmp_path):
    calls = []

    def handler(req):
        calls.append(req.url)
        return httpx.Response(200, content=json.dumps({"ok": 1}).encode())

    f = Fetcher(tmp_path, httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    a = await f.get("openfda", "https://x/y", cache_name="y.json")
    b = await f.get("openfda", "https://x/y", cache_name="y.json")
    assert a == b and len(calls) == 1


BULK_XML = b"""<?xml version="1.0"?><health-topics total="2">
<health-topic title="A1C" url="https://medlineplus.gov/a1c.html" language="English" date-created="12/22/2015">
<also-called>HbA1C</also-called><full-summary>&lt;p&gt;A1C is a blood test for diabetes.&lt;/p&gt;</full-summary>
<language-mapped-topic language="Spanish">Prueba A1C</language-mapped-topic></health-topic>
<health-topic title="Prueba A1C" url="https://medlineplus.gov/spanish/a1c.html" language="Spanish" date-created="12/22/2015">
<full-summary>&lt;p&gt;La prueba A1C.&lt;/p&gt;</full-summary></health-topic>
</health-topics>"""


def test_parse_medlineplus_bulk_keeps_english_and_synonyms():
    from app.ingest.sources import parse_medlineplus_bulk

    docs = parse_medlineplus_bulk(BULK_XML)
    assert [d.doc_id for d in docs] == ["medlineplus:a1c"]
    assert docs[0].sections[0].text.startswith("Also called: HbA1C.")
    assert docs[0].licence == "public-domain" and docs[0].year == 2015


OTC_RECORD = {
    "set_id": "abc",
    "effective_time": "20260102",
    "openfda": {"generic_name": ["ACETAMINOPHEN"], "brand_name": ["Pain Reliever"]},
    "active_ingredient": ["Drug Facts Active ingredient (in each tablet) Acetaminophen 500 mg"],
    "purpose": ["Purpose Pain reliever/fever reducer"],
    "indications_and_usage": ["Uses temporarily relieves minor aches and pains due to: headache"],
    "ask_doctor": ["Ask a doctor before use if you have liver disease"],
    "stop_use": ["Stop use and ask a doctor if fever lasts more than 3 days"],
    "dosage_and_administration": [
        "Directions \u25a0 adults and children 12 years and over: take 2 tablets every 6 hours \u25a0 children under 12 years: ask a doctor"
    ],
}


def test_otc_label_parsed_verbatim_with_dosing_flag():
    from app.ingest.sources import openfda_otc_doc, pick_otc_label

    combo = {**OTC_RECORD, "openfda": {"generic_name": ["ACETAMINOPHEN, PHENYLEPHRINE HCL"]}}
    assert pick_otc_label([combo, OTC_RECORD], "acetaminophen") is OTC_RECORD
    doc = openfda_otc_doc(OTC_RECORD, "acetaminophen")
    s = {x.path[0]: x for x in doc.sections}
    assert doc.doc_id == "openfda-otc:acetaminophen" and doc.licence == "cc0"
    assert s["Active ingredient"].text == "Acetaminophen 500 mg"
    assert s["Uses"].text.startswith("temporarily relieves")
    assert s["Directions"].dosing is True
    assert (
        "- adults and children 12 years and over: take 2 tablets every 6 hours"
        in s["Directions"].text
    )
    assert s["Ask a doctor before use"].text.startswith(
        "Ask a doctor before use if you have liver disease"
    )
