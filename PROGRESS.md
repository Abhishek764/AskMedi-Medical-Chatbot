# AskMedi v2 — progress log

Read this first when resuming. Newest entries at the top. Branch: `v2/backend`.

## Session 2026-11-17 — goal: finish v2 (clean repo, ~1.5k docs, React web app, metrics)

| # | Task | Status |
|---|---|---|
| 1 | Progress log + memory | done |
| 2 | Clean repo: docs → `docs/`, one diagram system (Archify) | done (diagram refresh pending) |
| 3 | Grow corpus toward 1,000–2,000 docs (MedlinePlus bulk XML, more labels, more papers) | code done; download running → then `export` |
| 4 | React web app in `web/` (auth, chat SSE, citations, safety cards, feedback, settings) | done (`npm run dev`), CI added |
| 5 | Metrics: `docs/METRICS.md` + live `GET /v1/admin/metrics` | done |
| 6 | Re-run evals on the bigger corpus; update scorecard + METRICS.md numbers | todo (corpus now 1,677 docs) |
| 6b | Medicine check: 3 questions → OTC medicines with label dose (backend + web) | done, needs clinician review (`docs/security-analysis.md` §8) |
| 6c | Design system artifact (from web app) | done |
| 6d | Gemini free tier (LLM_PROVIDER=auto: OpenAI → Gemini → Claude → extractive) | done (gemini-3.1-flash-lite) |
| 6e | Insurance policy demo (FEMA SFIP: compare, diff, cited Q&A) + CI eval gate + ablation | done |
| 7 | End-to-end check: `backend/scripts/smoke.py` (chat, guards, medicine check, policies) | done 2026-11-18, all pass |
| 7b | Hard-set ablation (`eval_ablation --golden ../evals/golden/v2_hard.jsonl`, stop API first) | todo |
| 7c | Observability: Prometheus `/metrics`, Grafana stack (`deploy/observability`), `/admin` dashboard, `app.admin promote` | done 2026-11-18 |
| 7d | Tracing: Logfire + LangSmith step traces (`app/core/tracing.py`), off until keys set | done (keys: manualwork step 11) |
| 7e | NeMo Guardrails input/output rails (`GUARDRAILS_PROVIDER=nemo`, `backend/guardrails/`) | done, on in local .env |
| 7f | Ragas suite `app.eval_ragas`: hard set ID recall 0.872 / precision 0.296 (47 q) | done; judged run limited by Gemini free tier |
| 8 | Refresh Archify diagram (web app built, docs/ paths) | todo |

Note: when redirecting ingest output to a log, set `PYTHONUNBUFFERED=1` or the log looks frozen.
Local Qdrant (`backend/qdrant_data`) allows one process at a time: stop the API before ingesting.

Waiting on the user (see manualwork.md): rotate Gemini key, full Qdrant Cloud API key, OpenAI key later,
review of `evals/golden/v2_corpus.jsonl`, clinician review of crisis copy.

## Already done (before 2026-11-17)
- FastAPI backend in `backend/` (auth, conversations, SSE chat, guards, hybrid BM25 + dense retrieval,
  verifier, ingestion, worker, Docker, Render, CI) — 158 tests.
- v1 Flask removed (tag `v1-final`), `app.migrate_v1` moves v1 users and chats.
- Corpus v1: 253 docs in `data/corpus/`; raw in `data/raw/` (gitignored).
- Eval scorecard `evals/results/v2/REPORT.md`: crisis/emergency recall 1.00, 93% expected-doc citation.

## How to resume
```bash
cd backend && uv sync --extra local --extra evals --extra rails && uv run pytest          # backend green?
uv run uvicorn app.main:create_app --factory --port 8000      # API
cd ../web && npm install && npm run dev                       # web on :5173
cd ../backend && uv run python scripts/smoke.py               # end-to-end smoke
```
