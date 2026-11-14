# syntax=docker/dockerfile:1.7
# AskMedi backend: multi-stage, slim, non-root. Same image runs the API and the worker.

FROM python:3.12-slim AS build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY --from=ghcr.io/astral-sh/uv:0.8.15 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
ARG EXTRAS="--extra local"
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project ${EXTRAS}
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev ${EXTRAS}

FROM python:3.12-slim
RUN useradd --create-home --uid 10001 askmedi
WORKDIR /app
COPY --from=build --chown=askmedi:askmedi /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PORT=8000 FORWARDED_ALLOW_IPS=127.0.0.1
USER askmedi
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/healthz')"
CMD ["sh", "-c", "uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT} --workers ${WEB_CONCURRENCY:-2} --proxy-headers --forwarded-allow-ips=${FORWARDED_ALLOW_IPS}"]
