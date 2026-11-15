# AskMedi v2 — Medical Information Assistant

AskMedi answers health and medicine questions **only from trusted, licensed sources, with a
citation on every sentence, or it refuses**. It is a medical information tool: it does not
diagnose, prescribe, or recommend doses to the public, and it is not a medical device.

v2 replaces the v1 Flask app (kept at tag `v1-final`) with a FastAPI backend built for web
and Android clients. Plan and design docs live in [`docs/`](docs/v2-plan.md).

![AskMedi v2 stack](docs/diagrams/v2-stack.png)

## What's in the backend

| Area | What it does |
|---|---|
| **Safety guards** | Crisis and self-harm detection (first-person, means/lethality, fiction framing, Hinglish, leetspeak) and acute emergency detection run before anything else, with fixed helpline copy (India: Tele-MANAS 14416, emergency 112). Conversation risk is sticky. Also blocks prompt injection, therapist/companion personas, harmful-substance advice, prescriptions, personal diagnosis, and dosing for non-verified users. PII is redacted before logs and models. |
| **Hybrid retrieval** | Qdrant with dense vectors **and BM25** sparse vectors (IDF applied server-side), fused with RRF, reranked by a cross-encoder, expanded from child chunks to parent sections. Query planner rewrites follow-ups, normalises abbreviations and brand names, and routes by intent. |
| **Cite-or-refuse** | Abstain gate before generation; verifier drops sentences with missing citations, weak support, or numbers not found in the source. Free extractive mode answers with verbatim source sentences; Ollama, OpenAI or Claude plug in behind the same interface. |
| **Corpus** | Ingestion from MedlinePlus (public domain), openFDA labels (CC0, overdosage excluded, dosing sections provider-only) and PMC open-access reviews (licence and retraction checked per article; PDF + JATS XML). Licence allowlist enforced in code. |
| **API** | JWT auth with rotating refresh tokens, email verification, password reset, account deletion and export, provider (clinician/pharmacist) verification, conversations, SSE chat, feedback, rate limits and daily quotas. |
| **Ops** | Postgres + Alembic, Redis, arq worker (token cleanup, monthly corpus refresh), Docker, docker-compose, Render blueprint, GitHub Actions CI. |

## Quick start (no API keys, no paid services)

```bash
cd backend
uv sync --extra local                       # free local ONNX models (no torch)
cp .env.example .env                         # then set JWT_SECRET
uv run python -m app.ingest run --papers-per-topic 3   # downloads ~250 documents
uv run python scripts/ask.py "What are the symptoms of dengue?"
uv run uvicorn app.main:create_app --factory --reload  # API docs at http://localhost:8000/docs
uv run pytest
```

Full stack with Postgres, Redis and Qdrant: `docker compose up --build` in `backend/`.

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
evals/     eval harness, golden set, v1 baseline results
data/      v1 source PDF (licence unverified; not in the v2 index)
docs/   v2 plan, security analysis, corpus plan, resources, stack diagram
```

Web (Next.js) and Android (Flutter) clients come next; see the milestones in
[`docs/v2-plan.md`](docs/v2-plan.md).

## Disclaimer

AskMedi provides general health information from cited sources. It is not medical advice, a
diagnosis, or a prescription. In an emergency, call your local emergency number.
