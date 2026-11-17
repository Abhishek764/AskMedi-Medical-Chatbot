# AskMedi v2 — progress log

Read this first when resuming. Newest entries at the top. Branch: `v2/backend`.

## Session 2026-11-17 — goal: finish v2 (clean repo, ~1.5k docs, React web app, metrics)

| # | Task | Status |
|---|---|---|
| 1 | Progress log + memory | done |
| 2 | Clean repo: docs → `docs/`, one diagram system (Archify) | done (diagram refresh pending) |
| 3 | Grow corpus toward 1,000–2,000 docs (MedlinePlus bulk XML, more labels, more papers) | code done; download running → then `export` |
| 4 | React web app in `web/` (auth, chat SSE, citations, safety cards, feedback, settings) | done (`npm run dev`), CI added |
| 5 | Metrics: `docs/METRICS.md` (what we measure, current values, how to improve) | todo |
| 6 | Re-run evals on the bigger corpus; update scorecard | todo |

Waiting on the user: OpenAI API key (set `OPENAI_API_KEY` + `LLM_PROVIDER=openai` in `backend/.env`),
review of `evals/golden/v2_corpus.jsonl`, clinician review of crisis copy.

## Already done (before 2026-11-17)
- FastAPI backend in `backend/` (auth, conversations, SSE chat, guards, hybrid BM25 + dense retrieval,
  verifier, ingestion, worker, Docker, Render, CI) — 158 tests.
- v1 Flask removed (tag `v1-final`), `app.migrate_v1` moves v1 users and chats.
- Corpus v1: 253 docs in `data/corpus/`; raw in `data/raw/` (gitignored).
- Eval scorecard `evals/results/v2/REPORT.md`: crisis/emergency recall 1.00, 93% expected-doc citation.

## How to resume
```bash
cd backend && uv sync --extra local && uv run pytest          # backend green?
cd ../web && npm install && npm run dev                       # web app (once task 4 lands)
```
