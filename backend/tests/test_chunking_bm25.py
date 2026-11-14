from app.rag.bm25 import BM25Encoder, term_id, tokenize
from app.rag.chunking import chunk_document, split_sentences
from app.rag.embeddings import HashEmbedder
from app.rag.types import Section, SourceDoc


def _doc(text: str, **kw) -> SourceDoc:
    return SourceDoc(
        doc_id="test:asthma",
        source="medlineplus",
        title="Asthma",
        licence="public-domain",
        doc_type="consumer",
        sections=[Section(["Symptoms"], text, **kw)],
        year=2024,
    )


LONG = " ".join(f"Sentence number {i} talks about asthma symptoms and wheezing." for i in range(80))


def test_children_carry_header_and_overlap():
    parents, chunks = chunk_document(_doc(LONG), child_words=60, overlap_words=15)
    assert len(parents) == 1
    assert len(chunks) > 3
    assert all(c.text.startswith("Asthma › Symptoms · medlineplus · 2024\n") for c in chunks)
    first, second = chunks[0].text.split("\n", 1)[1], chunks[1].text.split("\n", 1)[1]
    assert first.split(". ")[-1].rstrip(".") in second  # overlap carried forward
    assert all(c.parent_id == parents[0].id for c in chunks)


def test_chunk_ids_are_deterministic():
    _, a = chunk_document(_doc(LONG))
    _, b = chunk_document(_doc(LONG))
    assert [c.id for c in a] == [c.id for c in b]


def test_long_section_splits_into_parent_parts():
    parents, _ = chunk_document(_doc(LONG), parent_words=200)
    assert len(parents) >= 3


def test_tables_stay_whole_and_keep_dosing_flag():
    parents, chunks = chunk_document(
        _doc("| Age | Dose |\n| adult | 500 mg |", is_table=True, dosing=True)
    )
    assert len(chunks) == 1 and chunks[0].payload["dosing"] is True


def test_split_sentences():
    assert split_sentences("Hello there. This is two! Three?") == [
        "Hello there.",
        "This is two!",
        "Three?",
    ]


def test_tokenize_stems_and_drops_stopwords():
    assert tokenize("The symptoms of infections") == ["symptom", "infection"]


def test_bm25_scores_rank_relevant_doc_higher():
    enc = BM25Encoder()
    q = enc.encode_query("asthma wheezing")
    d1 = enc.encode_document("Asthma causes wheezing and chest tightness.")
    d2 = enc.encode_document("Diabetes affects blood sugar levels.")

    def dot(a, b):
        bm = dict(zip(b.indices, b.values, strict=True))
        return sum(v * bm.get(i, 0.0) for i, v in zip(a.indices, a.values, strict=True))

    assert dot(q, d1) > dot(q, d2) == 0
    assert term_id("asthma") == term_id("asthma")


async def test_hash_embedder_similarity():
    e = HashEmbedder(256)
    a = await e.embed_query("asthma wheezing chest")
    b, c = await e.embed_documents(["asthma causes wheezing in the chest", "kidney stones"])
    cos = lambda x, y: sum(i * j for i, j in zip(x, y, strict=True))  # noqa: E731
    assert cos(a, b) > cos(a, c)
