# AskMedi v1 — Repo Study

Snapshot of the repo as of `dd00aba` (2026-06-07), studied 2026-11-11.
Purpose: baseline for planning **v2**. Read this before changing architecture.

---

## 1. What it is

Flask web app. User signs up, asks medical questions, gets streamed answers
grounded in one PDF (`data/Medical_book.pdf`) via RAG. Conversations saved per user.

- 12 commits. Two eras:
  - **v0 (2026-05-12)**: single-file `app.py` + root `templates/chat.html` + `static/style.css` (notebook-derived prototype). `app.py` since deleted; root `templates/` + `static/` are **dead leftovers**.
  - **v1 (2026-06-07)**: refactor into `app/` package (factory, blueprints, auth, SSE streaming, tests, Render deploy).
- Tests: `python -m pytest -q` → **10 passed** (Python 3.11.9 local; Render pins 3.10.14).

## 2. Stack

| Layer | Tech |
|---|---|
| Web | Flask 3.1, Jinja templates, vanilla JS (`app/static/chat.js`) |
| Auth | Flask-Login, bcrypt, Flask-WTF (CSRF), Flask-Limiter |
| DB | SQLAlchemy (SQLite local / Postgres prod), Flask-Migrate installed but **no migrations dir** |
| RAG | LangChain 0.3.26, `ChatOpenAI(gpt-4o, temperature=0)`, Pinecone (`medical-chatbot`, 384-dim cosine, aws us-east-1) |
| Embeddings | HuggingFace `sentence-transformers/all-MiniLM-L6-v2` **run in-process** (pulls torch) |
| Frontend libs | `marked@12` + `DOMPurify@3.1.6` from jsDelivr CDN (no SRI) |
| Serve | gunicorn 2 workers × 4 threads, timeout 120 |
| Deploy | Render blueprint (`render.yaml`) **and** a stale AWS ECR/EC2 GitHub Action |

## 3. Architecture

```
Browser (chat.js, fetch + ReadableStream SSE parse)
   │  POST /api/chat {message, conversation_id}  + X-CSRFToken
   ▼
Flask app factory  (app/__init__.py)
   ├─ main_bp   /  /disclaimer  /healthz (SELECT 1)
   ├─ auth_bp   /register  /login (10/min)  /logout
   └─ chat_bp   /chat  /api/chat (30/min, SSE)  /api/conversations[...]
          │
          ├─ app/chat/rag.py  — lazy singleton chain (thread lock)
          │     history-aware retriever (LLM rewrites follow-up → standalone q)
          │     → Pinecone similarity k=3 → stuff-docs QA prompt → gpt-4o stream
          ├─ Postgres/SQLite  users · conversations · messages
          └─ Pinecone index   chunks of Medical_book.pdf
```

### Request flow `/api/chat`
1. Validate: non-empty, `len <= MAX_MESSAGE_LEN` (2000) else 400.
2. Resolve conversation (ownership check → 404) or create one (title = msg[:60]).
3. Load last `CHAT_HISTORY_TURNS*2` (12) messages → LangChain messages.
4. Persist user message **before** streaming.
5. SSE events: `meta{conversation_id}` → `token{content}`* → `done{sources}` | `error{message}`.
6. `finally`: persist joined assistant answer (also saves partial answer on error/abort).

### Ingestion (offline, `store_index.py`)
PDF (`DirectoryLoader` + `PyPDFLoader`) → strip metadata to `source` only →
`RecursiveCharacterTextSplitter(500, 20)` → MiniLM embeddings → `PineconeVectorStore.from_documents`.

## 4. File map

| Path | Role |
|---|---|
| `wsgi.py` | gunicorn entry; `python wsgi.py` = dev server :8080 |
| `app/__init__.py` | `create_app`, extensions, user_loader, blueprints, `flask init-db` CLI |
| `app/config.py` | env config; `postgres://`→`postgresql://`; Dev/Prod by `FLASK_ENV` (default **production**) |
| `app/extensions.py` | db, migrate, login_manager, csrf, limiter singletons |
| `app/models.py` | `User`, `Conversation`, `Message` |
| `app/auth/` | forms + routes; safe `next` redirect check |
| `app/chat/rag.py` | chain build, `stream_answer(question, history)` generator, `to_lc_history` |
| `app/chat/routes.py` | chat page, conversation CRUD API, SSE endpoint |
| `app/main/routes.py` | landing, disclaimer, healthz |
| `app/errors.py` | 404/429/500 → JSON for `/api/*`, HTML otherwise |
| `app/templates/`, `app/static/` | live UI |
| `src/helper.py` | load/split/embed helpers (deprecated `langchain.*` import paths) |
| `src/prompt.py` | `system_prompt` (guardrails), `contextualize_q_prompt` |
| `store_index.py` | one-shot index builder |
| `research/trials.ipynb` | original exploration notebook |
| `tests/conftest.py` | stubs all LangChain/Pinecone modules via `sys.modules`; temp SQLite |
| `tests/test_app.py` | 10 tests: pages, healthz, auth, validation, SSE persist, ownership |
| `templates/`, `static/` (root) | **dead** v0 UI |
| `template.sh` | project scaffold script (creates `app.py` that no longer exists) |
| `Dockerfile`, `.github/workflows/cicd.yaml` | **stale** AWS path |
| `render.yaml`, `Procfile` | live Render deploy |

## 5. Data model

```
users(id, email UNIQUE idx, password_hash, created_at)
  1─* conversations(id, user_id FK idx, title, created_at)
        1─* messages(id, conversation_id FK idx, role 'user'|'assistant', content TEXT, created_at)
```
Cascade delete-orphan both levels. No `updated_at`; sidebar sorts by `created_at`.

## 6. Config / env

`SECRET_KEY`, `DATABASE_URL`, `PINECONE_API_KEY`, `OPENAI_API_KEY`, `PINECONE_INDEX` (medical-chatbot),
`OPENAI_MODEL` (gpt-4o), `CHAT_HISTORY_TURNS` (6), `MAX_MESSAGE_LEN` (2000),
`RATELIMIT_STORAGE_URI` (memory://), `FLASK_ENV`.

## 7. Testing approach

- Seam 1: **HTTP** via Flask test client (whole app minus RAG).
- Seam 2: **`app.chat.routes.stream_answer`** monkeypatched with a fake token generator.
- No tests for: RAG quality/retrieval, `store_index.py`, `src/helper.py`, prompts, JS.
- `pytest` not in `requirements.txt`; CI never runs tests.

## 8. Known issues / tech debt (ranked)

### Broken
1. **Dockerfile** runs `python3 app.py` — file gone. Base `python:3.10-slim-buster` is EOL.
2. **GitHub Action** (`cicd.yaml`) deploys to EC2 on every push to `main`: no tests, deprecated `set-output`, old action versions, no `SECRET_KEY`/`DATABASE_URL` passed → would run with SQLite + dev secret. Conflicts with Render as the deploy target.
3. `store_index.py`: `os.environ[...] = None` → `TypeError` if a key missing; index name hardcoded (ignores `PINECONE_INDEX`); re-running **duplicates vectors** (no stable ids / no upsert by id).

### Risky
4. `SECRET_KEY` falls back to `"dev-only-change-me"` in **prod** if unset (no fail-fast).
5. Rate limits use `memory://` → per-worker (2 workers ⇒ effective limits ×2, reset on restart). `/register` not rate-limited.
6. Embedding model + torch loaded in web process → large RAM, slow cold start (Render starter = 512 MB).
7. Notebook added a non-medical doc ("dswithabhishek … youtube") to the index — **index may be polluted**.
8. Citations = filename only; page numbers dropped by `filter_to_minimal_docs`.
9. Client disconnect / error mid-stream → partial answer saved as if complete.
10. CDN scripts without SRI; no CSP header.
11. `datetime.utcnow` deprecated; `langchain.document_loaders` / `langchain.embeddings` deprecated paths.
12. `init-db` = `create_all`; no Alembic migrations yet → schema changes painful.

### Missing
- No RAG evaluation (faithfulness, retrieval recall), no observability (latency, tokens, cost), no feedback (👍/👎), no admin, single PDF only, no password reset/email verify, no conversation rename/search, chunking 500/20 + k=3 untuned.

## 9. Seams worth keeping in v2

- `stream_answer(question, history) -> Iterator[("token", str) | ("done", {...})]` — clean, test-proven boundary between web and AI. Good deep-module candidate.
- App factory + blueprints + config object injection (tests rely on it).
- SSE event protocol (`meta/token/done/error`) — frontend contract.

## 10. v2 open questions (to grill)

- Keep Flask or move to FastAPI (async streaming)?
- Hosted embeddings (OpenAI/Pinecone inference) vs in-process MiniLM?
- Multi-document corpus + admin upload? Page-level citations?
- Single deploy target (Render) — delete AWS path?
- Eval harness + guardrail tests before changing prompts/models?
- Frontend: keep Jinja+vanilla JS or SPA?
