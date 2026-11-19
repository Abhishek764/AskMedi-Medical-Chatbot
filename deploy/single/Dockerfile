# syntax=docker/dockerfile:1.7
# AskMedi in one container (Render free web service or a Hugging Face Docker Space): API + built web app in one container, one origin.
# Build context = repo root (Render) or the Space repo that deploy/single/push.sh assembles.
# Postgres (Neon), vectors (Qdrant Cloud) and the LLM key come from host secrets.

FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web ./
RUN npm run build

FROM python:3.12-slim AS build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY --from=ghcr.io/astral-sh/uv:0.8.15 /uv /usr/local/bin/uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --extra local
COPY backend/app ./app
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./
RUN uv sync --frozen --no-dev --extra local
# Bake the ONNX models into the image so a cold start does not download them.
ENV FASTEMBED_CACHE_PATH=/app/models
RUN .venv/bin/python -c "from fastembed import TextEmbedding as E; from fastembed.rerank.cross_encoder import TextCrossEncoder as C; E('BAAI/bge-small-en-v1.5'); C('Xenova/ms-marco-MiniLM-L-6-v2')"

FROM python:3.12-slim
# Spaces run the container as uid 1000.
RUN useradd --create-home --uid 1000 askmedi
WORKDIR /app
COPY --from=build --chown=askmedi:askmedi /app /app
COPY --from=web --chown=askmedi:askmedi /web/dist /app/web
COPY --chown=askmedi:askmedi data/policies /app/policies
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PORT=7860 \
    FASTEMBED_CACHE_PATH=/app/models \
    ENV=prod DB_AUTO_CREATE=false ALLOW_INPROCESS_KV=true \
    WEB_DIST_DIR=/app/web POLICIES_DIR=/app/policies \
    EMBEDDINGS_PROVIDER=fastembed RERANK_PROVIDER=fastembed \
    QDRANT_COLLECTION=corpus-v1 LLM_PROVIDER=auto GUARDRAILS_PROVIDER=builtin
USER askmedi
EXPOSE 7860
# Trust X-Forwarded-For only from private-range hops (the Space proxy). Uvicorn walks the
# header from the right and stops at the first untrusted address, so a client-sent value
# cannot replace the real client IP used by rate limits.
ENV FORWARDED_ALLOW_IPS="127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
# One worker: rate limits and quotas live in process memory (ALLOW_INPROCESS_KV).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers --forwarded-allow-ips=\"$FORWARDED_ALLOW_IPS\""]
