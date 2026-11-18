"""Prometheus metrics: what the service is doing right now (traffic, latency, errors, safety).

Scraped from GET /metrics (see app.main). Labels are low-cardinality on purpose: route
templates (not raw paths), statuses, reason keys and model names. No user ids, no text.

Note: with several uvicorn worker processes each keeps its own counters; set
PROMETHEUS_MULTIPROC_DIR (prometheus_client multiprocess mode) when running more than one.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS = Counter(
    "askmedi_http_requests_total", "HTTP requests", ["method", "route", "status"]
)
HTTP_LATENCY = Histogram(
    "askmedi_http_request_duration_seconds",
    "HTTP request duration (for SSE: time to first byte)",
    ["method", "route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)
ANSWERS = Counter("askmedi_answers_total", "Assistant turns by outcome", ["status", "reason"])
ANSWER_LATENCY = Histogram(
    "askmedi_answer_duration_seconds",
    "Question to final answer",
    ["status"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8, 15, 30, 60),
)
CACHE_HITS = Counter("askmedi_answer_cache_hits_total", "Answers served from the answer cache")
GUARD_EVENTS = Counter("askmedi_guard_events_total", "Safety guard triggers", ["kind"])
STAGE_LATENCY = Histogram(
    "askmedi_stage_duration_seconds",
    "Pipeline stage duration",
    ["stage"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8, 15, 30),
)
LLM_CALLS = Counter("askmedi_llm_calls_total", "LLM API calls", ["model", "outcome"])
LLM_LATENCY = Histogram(
    "askmedi_llm_call_duration_seconds",
    "LLM API call duration",
    ["model"],
    buckets=(0.25, 0.5, 1, 2, 4, 8, 15, 30, 60),
)
LLM_TOKENS = Counter("askmedi_llm_tokens_total", "LLM tokens", ["model", "direction"])
RAIL_CHECKS = Counter(
    "askmedi_rail_checks_total", "External guardrail checks (NeMo)", ["rail", "outcome"]
)


@contextmanager
def timed(stage: str) -> Iterator[None]:
    t = time.perf_counter()
    try:
        yield
    finally:
        STAGE_LATENCY.labels(stage).observe(time.perf_counter() - t)


def record_answer(
    status: str,
    reason: str | None,
    latency_ms: int,
    *,
    model: str | None,
    tokens_in: int,
    tokens_out: int,
    guard_kind: str | None,
    cached: bool,
) -> None:
    ANSWERS.labels(status, reason or "none").inc()
    ANSWER_LATENCY.labels(status).observe(latency_ms / 1000)
    if cached:
        CACHE_HITS.inc()
    if guard_kind:
        GUARD_EVENTS.labels(guard_kind).inc()
    if model and (tokens_in or tokens_out) and not cached:
        LLM_TOKENS.labels(model, "in").inc(tokens_in)
        LLM_TOKENS.labels(model, "out").inc(tokens_out)


def render() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
