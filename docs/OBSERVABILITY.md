# Observability, guardrails and evals

What AskMedi records about itself, where to look, and how each piece is switched on.
Everything below is off or local by default, so the app runs with no accounts.

| Question you're asking | Where to look | Needs |
|---|---|---|
| Is the product working for users? | Web dashboard `/admin` | an admin account |
| Is the service healthy right now? | Grafana `AskMedi` dashboard (Prometheus) | Docker |
| Why did *this* answer come out that way? | Logfire or LangSmith trace | a free account + key |
| Did a change make answers worse? | Ragas suite, CI eval gate | nothing (judge metrics: an LLM key) |
| What blocked a message? | `refusals_by_reason` in `/admin`, `nemo_*_rail` trace steps | — |

## 1. Admin dashboard (`/admin`)

Counts from the database (no message text): answers by outcome, answer rate, p50/p95 latency,
refusals by reason, safety events by kind, 👍/👎 helpful rate, users, tokens, corpus size,
the live model chain, and per-day charts. 7/30/90-day window, refreshes every 30 s.

Make yourself admin (there is deliberately no HTTP route that grants admin):

```bash
cd backend
uv run python -m app.admin promote you@example.com   # then sign out and in again
uv run python -m app.admin list
```

API: `GET /v1/admin/metrics?days=7` (admin only).

## 2. Prometheus + Grafana (`/metrics`)

`GET /metrics` exposes:

| Metric | Labels | Use |
|---|---|---|
| `askmedi_http_requests_total` / `_request_duration_seconds` | method, route template, status | traffic, errors, latency |
| `askmedi_answers_total` / `askmedi_answer_duration_seconds` | status, reason | outcomes, answer latency |
| `askmedi_guard_events_total` | kind | crisis, emergency, injection, rails… |
| `askmedi_stage_duration_seconds` | stage (retrieve, generate, verify) | where time goes |
| `askmedi_llm_calls_total` / `_call_duration_seconds` / `_tokens_total` | model, outcome / direction | provider errors, 429s, cost |
| `askmedi_rail_checks_total` | rail, outcome | NeMo passed / blocked / error |
| `askmedi_answer_cache_hits_total` | — | cache effectiveness |

Open in dev. Outside dev it needs `METRICS_TOKEN` (bearer) and is disabled without one.

```bash
docker compose -f deploy/observability/docker-compose.yml up -d
# Grafana   http://localhost:3001   (dashboard "AskMedi"; admin / admin to edit)
# Prometheus http://localhost:9090
```

## 3. Step tracing: Pydantic Logfire and LangSmith

Each assistant turn is one trace:

```
answer                      status, reason, model, citations, latency
├── input_guard             action, reason, flags, PII kinds found
├── nemo_input_rail         blocked, rail, error            (GUARDRAILS_PROVIDER=nemo)
├── medicine_check          step, status                    (medicine questions)
├── retrieve   [retriever]  top score, candidates, doc ids, abstain
├── generate                model, sentences, tokens, fallback notes
│   └── llm <model> [llm]   outcome (ok / rate_limited / http_5xx), tokens, latency
├── verify                  ok, reason, dropped sentences by cause
└── nemo_output_rail        blocked, rail, error
```

- **Logfire** (`LOGFIRE_TOKEN`): the trace above as OpenTelemetry spans, plus automatic
  FastAPI, httpx and SQLAlchemy spans. Endpoint arguments (the question body) and headers
  are never recorded.
- **LangSmith** (`LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`): the same tree as runs, with the
  retriever and llm run types and token usage, so LangSmith's cost and latency views work.

Privacy: `TRACE_CONTENT=false` (default) sends ids, scores, statuses and models only.
`TRACE_CONTENT=true` adds the PII-redacted question and answer text. Keep it false with real
patients' data unless the vendor is covered by your privacy terms.

Code: `backend/app/core/tracing.py`. Both backends can run at once.

## 4. Guardrails

Two layers, in this order:

1. **Deterministic rules** (`backend/app/guards/`), always on: crisis, emergency, injection,
   persona, harmful substances, scope, PII redaction. Crisis and emergency never wait on an LLM.
2. **NeMo Guardrails** (`GUARDRAILS_PROVIDER=nemo`, `uv sync --extra rails`):
   `self check input` after the rules allow a message, `self check output` on the verified
   answer. Prompts: `backend/guardrails/prompts.yml`. Judged by the OpenAI key, else Gemini.
   Timeouts (`GUARDRAILS_TIMEOUT_SECONDS`) and provider errors fail open by default
   (`GUARDRAILS_FAIL_CLOSED=true` to invert); every outcome is counted and traced.

## 5. Evals

| Suite | Command | Needs | Gate |
|---|---|---|---|
| CI eval gate | `uv run python -m app.eval_ci` | nothing (runs in GitHub Actions) | `evals/ci/thresholds.json` |
| Scorecard | `uv run python -m app.eval_run run` | local index | safety recall 1.00 |
| Ablation | `uv run python -m app.eval_ablation --golden ../evals/golden/v2_hard.jsonl` | local index | — |
| **Ragas** | `uv run python -m app.eval_ragas [--judge] [--limit N]` | `--extra evals`; judge: a key | — |

Ragas metrics: `IDBasedContextRecall` and `IDBasedContextPrecision` (free, from the golden
set's expected document ids), plus `Faithfulness` and `ContextRelevance` with `--judge`.
Results: `evals/results/v2/ragas.{md,json}`. Stop the API first when using the local Qdrant
folder (one process at a time). On Gemini's free tier keep `--limit` small; rows the judge
can't score (rate limits, 503s) are skipped and counted, not guessed.
