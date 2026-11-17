# AskMedi v2 — Medical Information Assistant

AskMedi answers health and medicine questions **only from trusted, licensed sources, with a
citation on every sentence, or it refuses**. It is a medical information tool: it does not
diagnose, prescribe, or recommend doses to the public, and it is not a medical device.

v2 replaces the v1 Flask app (kept at tag `v1-final`) with a FastAPI backend and a React web
app; an Android app comes later on the same API.

- Architecture (interactive, linked to the code): [`docs/diagrams/v2-architecture.html`](docs/diagrams/v2-architecture.html), open it in a browser
- Metrics and how to improve them: [`docs/METRICS.md`](docs/METRICS.md)
- Corpus and licences: [`data/README.md`](data/README.md)
- Plan, security analysis, resources: [`docs/`](docs/v2-plan.md)
- Where work stands: [`PROGRESS.md`](PROGRESS.md)

## How it works

```
Web app (React) ──HTTPS──► Cloudflare ──► FastAPI /v1 ──► answer pipeline
                                              │             1 input guard (crisis, emergency, scope, injection, PII)
                                              │             2 query planner (follow-ups, synonyms, brand → generic)
                                              │             3 Qdrant hybrid search: dense + BM25, RRF fusion
                                              │             4 cross-encoder rerank → abstain if sources are weak
                                              │             5 generator (extractive free mode, or OpenAI/Claude/Ollama)
                                              │             6 verifier: citations, support, numbers, role filter
                                              ├──► PostgreSQL (users, chats, citations, feedback, corpus registry)
                                              └──► Redis (rate limits, quotas, answer cache, job queue)
Offline: MedlinePlus + openFDA + PMC ──► data/raw ──► parse ──► chunk ──► embed + BM25 ──► Qdrant
```

| Area | What it does |
|---|---|
| **Safety** | Crisis and self-harm detection (first-person, means/lethality, fiction framing, Hinglish, leetspeak) and acute emergency detection run first, with fixed helpline copy (India: Tele-MANAS 14416, emergency 112). Conversation risk is sticky. Blocks prompt injection, personas, harmful-substance advice, prescriptions, personal diagnosis, dosing for the public, and anything that isn't a health question. PII is redacted before logs and models. |
| **Cite-or-refuse** | Abstains before generation when sources are weak; the verifier drops sentences with missing citations, weak support or numbers not in the source. |
| **Corpus** | MedlinePlus health topics (public domain), FDA drug labels (CC0; overdosage excluded; dosing provider-only), PMC open-access reviews (licence and retraction checked per article). |
| **API** | JWT with rotating refresh tokens, email verification, password reset, account export and deletion, provider verification, conversations, SSE chat, feedback, rate limits, daily quotas, admin metrics. |
| **Web app** | Sign-up with 18+ and disclaimer confirmation, streamed answers with citation links, crisis and emergency cards with tap-to-call, feedback, conversation history, settings. |
| **Ops** | PostgreSQL + Alembic, Redis, arq worker, Docker, docker-compose, Render blueprint, GitHub Actions CI, optional Sentry. |

## Run it locally (no API keys, no paid services)

Needs Python via [uv](https://docs.astral.sh/uv/) and Node.js 22.

```bash
# 1. Backend
cd backend
uv sync --extra local                       # free local ONNX models (no torch)
cp .env.example .env                         # then set JWT_SECRET to a long random string
uv run python -m app.ingest load             # build the search index from data/corpus (offline)
uv run uvicorn app.main:create_app --factory --reload    # API on :8000, docs at /docs

# 2. Web app (second terminal)
cd web
npm install
npm run dev                                  # http://localhost:5173 (proxies /v1 to :8000)
```

When you have an OpenAI key, set `OPENAI_API_KEY=...` and `LLM_PROVIDER=openai` in
`backend/.env` (never commit it). Everything else stays the same.

Tests: `cd backend && uv run pytest` · `cd web && npm test`. Evals: `cd backend && uv run python -m app.eval_run run`.

## Moving from v1

```bash
cd backend
uv run alembic upgrade head
uv run python -m app.migrate_v1 --source "postgresql+asyncpg://USER:PASS@HOST/V1DB" --dry-run
uv run python -m app.migrate_v1 --source "postgresql+asyncpg://USER:PASS@HOST/V1DB"
```

Users, conversations and messages are copied. v1 passwords keep working and are upgraded to
argon2id at next login; migrated users confirm age and the disclaimer once before chatting.

## Repository layout

```
backend/   FastAPI API, answer pipeline, guards, ingestion, worker, tests
web/       React web app (Vite, TypeScript, Tailwind)
data/      corpus snapshot (JSONL + manifest), raw downloads (gitignored), v1 book
evals/     golden sets, eval results (v1 baseline, v2 scorecard)
docs/      plan, security analysis, metrics, corpus plan, architecture diagram
```

## Disclaimer

AskMedi provides general health information from cited sources. It is not medical advice, a
diagnosis, or a prescription. In an emergency, call your local emergency number.
