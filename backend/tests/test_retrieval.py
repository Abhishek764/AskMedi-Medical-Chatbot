import pytest
from qdrant_client import AsyncQdrantClient

from app.rag.bm25 import BM25Encoder
from app.rag.chunking import chunk_document
from app.rag.embeddings import HashEmbedder
from app.rag.query import normalise_query, plan_query, rewrite_standalone
from app.rag.rerank import LexicalReranker
from app.rag.retriever import HybridRetriever
from app.rag.store import VectorStore
from tests.fixtures import DOCS


@pytest.fixture
async def retriever():
    emb = HashEmbedder(128)
    store = VectorStore(AsyncQdrantClient(":memory:"), "test", emb.dim)
    await store.ensure()
    bm25 = BM25Encoder()
    for doc in DOCS:
        parents, chunks = chunk_document(doc)
        dense = await emb.embed_documents([c.text for c in chunks])
        await store.upsert(parents, chunks, dense, [bm25.encode_document(c.text) for c in chunks])
    yield HybridRetriever(store, emb, LexicalReranker(), bm25, retrieve_k=10, context_k=3)
    await store.close()


async def test_finds_symptoms_section(retriever):
    res = await retriever.retrieve(
        plan_query("What are the symptoms of dengue?"), allow_dosing=False
    )
    top = res.passages[0]
    assert top.doc_id == "medlineplus:dengue"
    assert "fever" in top.parent_text
    assert res.top_score >= LexicalReranker.default_threshold


async def test_out_of_corpus_scores_low(retriever):
    res = await retriever.retrieve(
        plan_query("What are the symptoms of ebola?"), allow_dosing=False
    )
    assert res.top_score < LexicalReranker.default_threshold


async def test_non_allowlisted_licence_never_returned(retriever):
    res = await retriever.retrieve(plan_query("asthma wheezing coughing notes"), allow_dosing=False)
    assert all(p.doc_id != "bad:nc" for p in res.passages)


async def test_dosing_chunks_only_for_providers(retriever):
    q = plan_query("metformin starting dose")
    public = await retriever.retrieve(q, allow_dosing=False)
    provider = await retriever.retrieve(q, allow_dosing=True)
    assert not any(p.payload["dosing"] for p in public.passages)
    assert any(p.payload["dosing"] for p in provider.passages)


async def test_brand_name_normalised(retriever):
    res = await retriever.retrieve(plan_query("side effects of glycomet"), allow_dosing=False)
    assert res.passages[0].doc_id == "fda:metformin"


def test_followup_rewrite_carries_topic():
    q = rewrite_standalone("How is it treated?", ["What is asthma?"])
    assert "asthma" in q


def test_normalise_abbreviations_and_brands():
    assert normalise_query("HTN and crocin") == "hypertension and paracetamol"


def test_intent_routing():
    assert plan_query("Is there evidence that vitamin D works?").preferred_doc_types == (
        "research",
    )
    assert plan_query("side effects of metformin").intent == "drug"


async def test_ensure_indexes_doc_id_on_parents_even_when_collections_exist():
    """Qdrant Cloud (strict mode) rejects filters on unindexed fields; doc_sections and
    delete_doc filter the parents collection by doc_id. Local mode ignores indexes, so spy."""
    client = AsyncQdrantClient(":memory:")
    store = VectorStore(client, "test", 8)
    await store.ensure()  # creates both collections
    calls: list[tuple[str, str]] = []

    async def spy(collection_name, field_name, field_schema=None, **kw):
        calls.append((collection_name, field_name))

    client.create_payload_index = spy  # type: ignore[method-assign]
    await store.ensure()  # collections already exist (e.g. copied to Qdrant Cloud)
    assert (store.parents, "doc_id") in calls
    assert ("test", "doc_id") in calls
    await store.close()
