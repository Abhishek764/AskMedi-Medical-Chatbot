import csv

from app.ingest.corpus_file import read_corpus, write_corpus
from tests.fixtures import DOCS


def test_round_trip_keeps_allowlisted_docs_sorted(tmp_path):
    n = write_corpus(DOCS, tmp_path / "c.jsonl", tmp_path / "m.csv")
    assert n == 3  # the cc-by-nc fixture is dropped
    back = list(read_corpus(tmp_path / "c.jsonl"))
    assert [d.doc_id for d in back] == sorted(d.doc_id for d in DOCS if d.licence != "cc-by-nc")
    original = {d.doc_id: d for d in DOCS}
    for d in back:
        assert d == original[d.doc_id]  # sections, flags and metadata survive
    rows = list(csv.DictReader((tmp_path / "m.csv").open(encoding="utf-8")))
    assert {r["doc_id"] for r in rows} == {d.doc_id for d in back}
    assert all(int(r["words"]) > 0 for r in rows)
