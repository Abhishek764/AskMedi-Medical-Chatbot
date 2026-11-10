# AskMedi v2 — Production Plan

**Goal:** a production-ready medical RAG assistant with guardrails, anti-hallucination, evals, and an Android app.
**Decided (2026-11-11):** Flutter (Android first, iOS later) · FastAPI backend · **strict "grounded or refuse"** safety posture.
**Baseline:** [v1-README.md](v1-README.md). **Workflow:** [real-engineer.md](real-engineer.md).

> Status: **draft plan**. Feed it into `/grill-with-docs`, which should challenge it and turn decisions into ADRs, then run `/to-spec` and `/to-tickets`.

---

## 1. Principles

1. **Eval first.** Build the eval harness and score v1 *before* changing the RAG. Every later change must beat the baseline.
2. **Cite or refuse.** No claim reaches the user without a source chunk behind it. If unsure, abstain.
3. **Safety beats helpfulness.** Emergency detection must have 100% recall. Diagnosis, dosing, and prescriptions are always refused.
4. **One API, many clients.** FastAPI serves both the Flutter app and the web client through the same versioned `/v1` API.
5. **Keep the deep module.** `answer_stream(question, history) -> events` stays the single boundary between the web layer and the AI.

---

## 2. Target architecture

```
┌──────────────┐   ┌──────────────┐
│ Flutter app  │   │ Web client   │   (port chat.js to /v1 API, or Flutter web later)
│ (Android)    │   │              │
└──────┬───────┘   └──────┬───────┘
       │ HTTPS  JWT (access 15m + refresh 30d)  SSE stream
       ▼
┌─────────────────────────────────────────────────────────────┐
│ FastAPI  /v1                                                 │
│  auth · conversations · chat(SSE) · feedback · health        │
│  middleware: request-id, rate limit (Redis), CORS, logging   │
│                                                              │
│  ┌──────────────── answer pipeline (deep module) ─────────┐  │
│  │ 1 Input guard   → emergency? out-of-scope? injection?  │  │
│  │                   PII redaction                        │  │
│  │ 2 Rewrite       → standalone question (history-aware)  │  │
│  │ 3 Retrieve      → hybrid (dense + BM25) → rerank       │  │
│  │ 4 Gate          → top score < τ  ⇒ REFUSE (no LLM call)│  │
│  │ 5 Generate      → JSON: sentences[] each w/ chunk ids  │  │
│  │ 6 Verify        → citation check + groundedness judge  │  │
│  │ 7 Output guard  → dosing/diagnosis filter, disclaimer  │  │
│  └────────────────────────────────────────────────────────┘  │
└───────┬───────────┬──────────────┬─────────────┬────────────┘
        ▼           ▼              ▼             ▼
   Postgres     Redis (KV)     Pinecone     OpenAI (LLM +
   (Alembic)    rate limit,    namespaced,  hosted embeddings)
                cache          stable IDs
        │
        └─► Traces/metrics: Langfuse (or OpenTelemetry) — latency, tokens, cost, refusals, feedback

Offline:  ingest CLI (idempotent, page metadata)  ·  eval CLI (golden set → scorecard)  ·  CI gates
```

### Data model additions
- `messages`: + `status` (`complete` | `aborted` | `error` | `refused`), `refusal_reason`, `latency_ms`, `model`, `tokens_in/out`.
- `citations(message_id, chunk_id, source, page, score)`
- `feedback(message_id, user_id, rating ±1, reason, created_at)`
- `refresh_tokens(user_id, token_hash, expires_at, revoked_at)`
- `users`: + `email_verified_at`, `deleted_at` (account deletion is required by Play Store policy).

---

## 3. Guardrails (layered)

| Layer | Check | Action | How |
|---|---|---|---|
| Input | **Emergency** (chest pain, suicidal ideation, stroke signs, overdose…) | Stop generation. Show the emergency card with local numbers. | Keyword/regex list **plus** an LLM classifier; either one triggers (favour recall). Mobile shows a native emergency screen. |
| Input | **Out of scope** (non-medical, code, homework) | Polite refusal | Small classifier prompt or embedding similarity to the corpus centroid |
| Input | **Prompt injection / jailbreak** | Refuse and log | Pattern list + classifier. User text is never put in the system role. |
| Input | **PII** (names, phone, Aadhaar/SSN, email) | Redact before LLM and logs | Regex + a library such as Presidio (to research) |
| Input | Length / rate | 400 / 429 | Pydantic + Redis limiter per user **and** per IP |
| Retrieval | **Relevance gate** | Score < τ ⇒ "I don't have reliable information on that in my sources." | τ tuned on the eval set |
| Generation | **Grounded prompt** | Only the context; every sentence must cite `[c1]`…; no dosing or diagnosis | temperature 0, structured JSON output |
| Output | **Citation validator** | Drop or flag sentences whose cited ids weren't retrieved | Deterministic code |
| Output | **Groundedness judge** | Unsupported claim ⇒ regenerate once, else refuse | LLM-as-judge or NLI model; async sampling if latency is too high (see trade-off below) |
| Output | **Dosing/diagnosis filter** | Replace with "consult a clinician" | Regex for mg/ml/"take X times" + classifier |
| Output | **Disclaimer** | Always appended (structured field, not LLM text) | API field `disclaimer` the client renders |

**Streaming trade-off (decide in grilling, ADR):** full verification needs the whole answer before showing it.
Options: (a) generate → verify → then stream verified text (adds about 1–2 s, safest; recommended for strict mode); (b) stream live and retract if verification fails (better UX, but the user may see an unsafe sentence briefly).

---

## 4. Anti-hallucination (retrieval quality)

1. **Fix ingestion:** stable chunk IDs (`hash(source,page,offset)`), keep the `page` metadata, idempotent upsert, a namespace per corpus version, clear the polluted "youtube" vector.
2. **Better chunks:** tune size/overlap on the eval set (start 800/120); heading-aware splitting.
3. **Hosted embeddings:** OpenAI `text-embedding-3-small` (or Pinecone inference). Removes torch from the server; needs a re-index under a new namespace. Use `research` to confirm dims and cost.
4. **Hybrid search + rerank:** dense + BM25 (Pinecone sparse-dense or a local BM25), then a cross-encoder or Cohere/Jina rerank, top 5.
5. **Abstain gate** before the LLM (see guardrails).
6. **Structured citations:** model returns `{sentences:[{text, chunk_ids[]}]}`; UI shows "Medical_book.pdf p. 213" chips; tap opens the chunk text.
7. **Corpus governance:** a `corpus/manifest.yaml` with source, edition, licence, and review date. Scale to ~1,000 docs + research papers: see **[idea.md](idea.md)** for verified sources, licence allowlist, ingestion pipeline, and the M3a milestone.

---

## 5. Evals

### Golden dataset (`evals/golden/*.jsonl`, versioned in git)
| Slice | Size (start) | Expected |
|---|---|---|
| In-corpus factual | 120 | correct answer + correct page cited |
| Follow-up / multi-turn | 30 | standalone rewrite correct |
| Out-of-corpus medical | 40 | **refuse** |
| Off-topic | 20 | refuse |
| Emergency | 40 | **emergency path, 100%** |
| Dosing/diagnosis requests | 30 | refuse + clinician advice |
| Adversarial / jailbreak / injection | 40 | refuse, no leak of system prompt |
| PII in question | 15 | redacted in logs and LLM input |

Build it: the agent drafts questions from corpus pages, **you review every row** (the source of truth must be independent of the code, which is the `tdd` rule).

### Metrics and release gates
| Metric | Gate |
|---|---|
| Retrieval recall@5 (gold page in top 5) | ≥ 0.85 |
| Faithfulness / groundedness | ≥ 0.95 |
| Citation precision (cited chunk supports sentence) | ≥ 0.95 |
| Correct refusal rate (out-of-corpus + unsafe) | ≥ 0.95 |
| False refusal rate (in-corpus) | ≤ 0.10 |
| **Emergency recall** | **= 1.00 (hard gate)** |
| Jailbreak success | 0 |
| p95 time-to-first-token / full answer | ≤ 2.5 s / ≤ 8 s |
| Cost per answer | tracked; alert on +30% |

Gates are starting targets. Set real ones after the v1 baseline run.

### Where evals run
- **PR CI (fast, no secrets):** unit tests for guards, validator, and pipeline with fakes.
- **PR CI with label `rag` / nightly (secrets):** full golden run → scorecard markdown posted to the PR; fails if below the gate.
- **Production:** sample 5% of traces through the groundedness judge, review 👎 feedback weekly, and add each failure to the golden set (the data flywheel).
- Tooling: custom pytest-based harness + LLM judge; compare with `ragas` and pick via `research`.

---

## 6. Backend (FastAPI) production checklist

- Layout: `backend/app/{api,core,db,rag,guards,evals}`; `pyproject.toml` (uv), ruff, mypy, pytest.
- SQLAlchemy 2 async + **Alembic** migrations, carrying over v1 tables (data migration script from v1 Postgres).
- Auth: email+password (argon2/bcrypt), JWT access + rotating refresh tokens, email verification, password reset, **account + data deletion endpoint**.
- API contract: OpenAPI is the source of truth; generate the Dart client (`openapi-generator`) for Flutter.
- SSE events v2: `meta`, `status` (retrieving/verifying), `token` (or `sentence`), `citations`, `refusal{reason}`, `emergency{numbers}`, `done{message_id}`, `error`.
- Hardening: fail fast on missing secrets, CORS allowlist, security headers/CSP for web, request-id logging, structured JSON logs, no PII in logs, Sentry for errors.
- Resilience: OpenAI/Pinecone timeouts + retry with backoff + circuit breaker; graceful "service busy" message.
- Health: `/healthz` (liveness), `/readyz` (DB + Redis + Pinecone ping).
- Delete: root `templates/`, `static/`, `template.sh`, `Dockerfile` (rewrite), `cicd.yaml` (rewrite).

---

## 7. Android app (Flutter)

- Layout: `mobile/` with Riverpod (state), `dio` (+ SSE stream parsing), `go_router`, `flutter_secure_storage` (tokens), `flutter_markdown`, generated API client.
- Screens: onboarding + **medical disclaimer consent** (must accept), sign up/in/verify/reset, conversation list, chat (streaming, stop, citation chips → source sheet, 👍/👎), emergency screen (tap-to-call), settings (delete account, privacy policy, export data).
- Quality: widget tests for chat states (streaming/refused/emergency/error), integration test against a staging API, Crashlytics, offline/retry handling, dark mode, accessibility (TalkBack, text scaling).
- Release: Play Console → internal testing → closed testing → production. App signing, `versionCode` from CI, privacy policy URL, **Data Safety form** (health data + email), health app declaration. Use `research` on Play's current *Health apps* and *medical misinformation* policies before submitting.
- CI: GitHub Actions `flutter analyze` + `flutter test` on PR; build an AAB and upload to the internal track on tag (fastlane or `r0adkll/upload-google-play`).

---

## 8. Deployment and ops

| Env | Where | Notes |
|---|---|---|
| dev | local docker-compose (api + postgres + redis) | `.env` from `.env.example` |
| staging | Render (web service + Postgres + Key Value) | own Pinecone namespace, nightly evals run here |
| prod | Render (separate project) | autodeploy on tag after eval gate passes |

- Dockerfile (multi-stage, slim, non-root, uvicorn/gunicorn workers), `render.yaml` with `preDeployCommand: alembic upgrade head`.
- Index switching: ingest → new namespace → evals → flip `PINECONE_NAMESPACE` env var. Rollback = flip back.
- Alerts: error rate, p95 latency, refusal-rate spike, emergency-path count, OpenAI spend.
- Backups: Render Postgres daily backups; test a restore once.
- Legal/compliance (to research; not legal advice): privacy policy, terms, "not a medical device" positioning, data retention, applicable privacy law for your users' region (e.g. India DPDP Act / GDPR). Get a clinician to review the guardrail list and the emergency copy.

---

## 9. Milestones (each = one `/to-spec`; tickets via `/to-tickets`)

| M | Name | Outcome | Est. |
|---|---|---|---|
| **M0** | Foundations | `/setup-matt-pocock-skills`, CLAUDE.md, monorepo layout (`backend/` `mobile/` `evals/`), CI runs pytest, dead files removed | 2–3 d |
| **M1** | Eval harness + v1 baseline | golden set v0 (reviewed), eval CLI, scorecard on **v1 chain** | 4–5 d |
| **M2** | FastAPI backend parity | auth (JWT), conversations, SSE chat with the *current* chain, Alembic, v1 data migration, Docker, staging on Render | 5–7 d |
| **M3** | Ingestion + retrieval v2 | idempotent ingest, page metadata, hosted embeddings, hybrid + rerank, abstain gate → **beats baseline** | 4–6 d |
| **M4** | Guardrails + verification | input guards, structured citations, validator, groundedness judge, output filter, emergency path → **all gates green** | 5–7 d |
| **M5** | Flutter app | screens, streaming, citations, emergency screen, account deletion, tests, internal track build | 8–12 d |
| **M6** | Production hardening | observability, alerts, Sentry, rate limits, security review, load test, privacy docs, prod deploy | 4–5 d |
| **M7** | Launch + flywheel | Play closed testing → production, feedback triage loop, weekly eval refresh | ongoing |

Critical path: M0 → M1 → (M2 ∥ M3) → M4 → M5 → M6. **M5 can start on mocked API after M2's OpenAPI spec exists.**
Estimates assume one developer + agent. Re-estimate after `/to-tickets`.

---

## 10. How to run this with the skills

```text
/setup-matt-pocock-skills
research (background, docs/research/):
  - hosted embeddings vs MiniLM (dims, cost)        - ragas vs custom judge
  - Pinecone hybrid search + rerank options          - PII redaction libs (Presidio)
  - Google Play health app + data safety policy      - FastAPI SSE + JWT refresh best practice
  - Flutter SSE streaming client patterns
/wayfinder AskMedi v2 production + Android     ← v2 is bigger than one session
  (map = this file's milestones; resolve one decision ticket per session)
Per milestone:
  /grill-with-docs M<n> → ADRs + GLOSSARY.md
  /to-spec → /to-tickets → /implement #ticket (tdd) or /implement-spec
  pr skill → merge → /retro
Every few days: /improve-codebase-architecture
Deploy steps you must do by hand: wizard (Render, Pinecone, Play Console, GitHub secrets)
```

### ADRs to expect
0001 FastAPI replaces Flask · 0002 Flutter for mobile · 0003 strict grounded-or-refuse · 0004 hosted embeddings + re-index · 0005 verify-then-stream · 0006 Render only, staging + prod · 0007 JWT access/refresh · 0008 eval gates block release · 0009 corpus sources + licensing

## 11. Open questions for grilling
1. Verify-then-stream (safer, slower) or stream-then-retract?
2. Which new corpus sources, and do their licences allow commercial use?
3. Target countries → emergency numbers, privacy law, Play listing regions?
4. Free app or paid tier? (sets rate limits and OpenAI cost budget)
5. Keep a web client in v2, or mobile only at launch?
6. Is there a clinician available to review the golden set and guardrails?
7. LLM choice: keep `gpt-4o`, or a cheaper model plus a stronger judge?
