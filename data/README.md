# AskMedi data

The knowledge base behind AskMedi's answers. Every document comes from a source whose licence
allows commercial reuse; anything else is rejected in code before it reaches the index.

| Path | What | In git? |
|---|---|---|
| `corpus/corpus-v1.jsonl` | 253 parsed documents (one JSON object per line: id, source, title, URL, licence, type, year, sections) | yes (5 MB) |
| `corpus/manifest.csv` | One row per document: source, licence, year, title, URL, section and word counts | yes |
| `raw/` | Original downloads: MedlinePlus XML, openFDA label JSON, PMC article PDFs + JATS XML, search results | no (~193 MB, rebuilt on demand) |
| `Medical_book.pdf` | v1's source book | yes, **not in the v2 index** (licence unverified) |

## Corpus v1 (2026-11-17)

| Source | Docs | Words | Licence | Used for |
|---|---|---|---|---|
| [MedlinePlus](https://medlineplus.gov) health topics (NLM) | 107 | 55k | public domain | Plain-language consumer answers |
| [openFDA](https://open.fda.gov) drug labels | 62 | 280k | CC0 | Drug uses, warnings, side effects, interactions |
| [PMC Open Access](https://pmc.ncbi.nlm.nih.gov/tools/openftlist/) reviews (2016+) | 84 | 408k | CC BY (83), CC0 (1) | Evidence questions |
| **Total** | **253** | **743k** | | 4,906 indexed chunks |

Rules applied during ingestion (`backend/app/ingest/`):
- **Licence allowlist:** public domain, CC0, CC BY, CC BY-SA. NC and ND licences are rejected.
- **PMC:** licence and retraction status are read from PMC's own metadata, then cross-checked against
  the licence inside the article XML. Five papers whose two licence records disagreed were dropped.
- **openFDA:** the *Overdosage* section is never ingested. *Dosage and Administration* sections are
  flagged so only verified clinicians and pharmacists can retrieve them.
- **MedlinePlus:** only NLM-written health-topic summaries (public domain). A.D.A.M. encyclopedia
  content and drug monographs are copyrighted and excluded.

Attribution shown with answers: "Source: MedlinePlus, National Library of Medicine"; FDA label set
IDs link to DailyMed; papers cite authors, journal, year and PMCID. MedlinePlus and openFDA don't
endorse AskMedi.

## Rebuild

From `backend/`:

```bash
uv run python -m app.ingest load            # index corpus-v1.jsonl, no network needed
uv run python -m app.ingest run             # re-download (cached in data/raw) and index
uv run python -m app.ingest export          # regenerate corpus/ from data/raw
uv run python -m app.ingest stats           # counts in the live index
```

Grow the corpus by editing the seed lists in `backend/app/ingest/seeds.py` (conditions, medicines,
paper topics), then `run` and `export`. The target is about 1,000 documents (`docs/corpus-plan.md`).

## `Medical_book.pdf`

The v1 chatbot answered only from this book. Its licence is unknown, so v2 does not index it.
Keep it out of any public or commercial deployment until its rights are confirmed; if it turns out
to be openly licensed, add it with
`uv run python -m app.ingest pdf ../data/Medical_book.pdf --title "..." --licence <licence>`.
