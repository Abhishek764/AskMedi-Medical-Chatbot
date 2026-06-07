# AskMedi — Medical Chatbot

A Flask RAG web app that answers medical questions from a curated medical
reference (PDF), with user accounts, saved conversations, streaming answers,
source citations, and safety guardrails.

## Features

- **Auth** — register / login / logout (Flask-Login, bcrypt, CSRF protection).
- **RAG** — LangChain + OpenAI `gpt-4o`, Pinecone vector store, HuggingFace embeddings.
- **Conversational memory** — history-aware retriever resolves follow-up questions.
- **Streaming UX** — token-by-token answers over SSE, markdown rendering, stop button, source citations.
- **Persistence** — conversations and messages stored per user (Postgres in prod, SQLite locally).
- **Safety** — medical disclaimer, guardrail prompt, rate limiting, input validation.
- **Deploy** — production-ready for Render (gunicorn, `$PORT`, health check, managed Postgres).

## Architecture

```
Browser ──HTTPS──► Flask (gunicorn)
                     ├── Auth (Flask-Login + bcrypt)
                     ├── RAG chain (LangChain, gpt-4o, streaming)
                     ├──► Postgres  (users, conversations, messages)
                     └──► Pinecone  (medical-chatbot vectors)
```

Key paths:
- `app/` — application package (factory, config, models, blueprints).
  - `app/auth/` — registration & login.
  - `app/chat/` — chat pages, streaming API (`app/chat/routes.py`), RAG chain (`app/chat/rag.py`).
  - `app/main/` — landing, disclaimer, `/healthz`.
  - `app/templates/`, `app/static/` — UI.
- `src/helper.py` — PDF load/split/embeddings. `src/prompt.py` — system + contextualize prompts.
- `store_index.py` — one-time Pinecone index builder.
- `wsgi.py` — gunicorn entrypoint. `render.yaml` / `Procfile` — deploy config.

## Local setup

```bash
conda create -n medibot python=3.10 -y && conda activate medibot
pip install -r requirements.txt
cp .env.example .env   # then fill in PINECONE_API_KEY and OPENAI_API_KEY
```

Build the vector index once (uploads PDF embeddings to Pinecone):

```bash
python store_index.py
```

Create local DB tables, then run:

```bash
flask --app wsgi init-db      # creates SQLite tables
python wsgi.py                # dev server on http://localhost:8080
```

## Deploy to Render

1. Push this repo to GitHub.
2. In Render: **New → Blueprint**, point at the repo. `render.yaml` provisions a
   web service + Postgres automatically.
3. Set the two secret env vars (marked `sync: false`): `PINECONE_API_KEY`,
   `OPENAI_API_KEY`. `SECRET_KEY` and `DATABASE_URL` are generated/injected.
4. The pre-deploy step runs `flask --app wsgi init-db` to create tables.
5. Build the Pinecone index once (run `store_index.py` locally — not at deploy).

Notes:
- `DATABASE_URL` from Render uses the `postgres://` scheme; `app/config.py`
  rewrites it to `postgresql://` for SQLAlchemy 2.x.
- First request loads the HuggingFace embedding model (cold-start delay).
- The HF model is ~90 MB; expect a slow first boot on small instances.

## Schema migrations

First deploy uses `init-db` (idempotent `create_all`). For later schema
changes, switch to Flask-Migrate:

```bash
flask --app wsgi db init        # once
flask --app wsgi db migrate -m "describe change"
flask --app wsgi db upgrade
```

Then change the deploy command back to `flask --app wsgi db upgrade`.

## Tech stack

Python · Flask · LangChain · OpenAI · Pinecone · SQLAlchemy · gunicorn · Render
