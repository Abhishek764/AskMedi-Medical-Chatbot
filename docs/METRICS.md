# AskMedi metrics

Every number here comes from a command you can rerun. If a metric moves the wrong way after a
change, that change doesn't ship.

**Where the numbers come from**
- **Offline evals:** `cd backend && uv run python -m app.eval_run run` writes `evals/results/v2/REPORT.md`.
- **Live product metrics:** `GET /v1/admin/metrics?days=7`, admin only (see below).
- **Engineering:** CI (`.github/workflows/backend.yml`, `web.yml`).

## 1. Metric matrix

Status: ✅ meets target · ⚠️ below target · ⏳ not measured yet (needs an LLM key or real users).

| Area | Metric | How it is measured | v1 | v2 now | Target | Status |
|---|---|---|---|---|---|---|
| **Safety** | Crisis + emergency recall | eval_run, held-out v0 rows | not measured | **1.00** (10/10) | 1.00 (hard gate) | ✅ |
| Safety | Unsafe requests refused (dosing, diagnosis, jailbreak, off-topic) | eval_run, held-out v0 rows | not measured | **22/22** | 100% | ✅ |
| Safety | Guard eval rows passing | `pytest tests/test_guards.py` | none | 77/77 | 100% | ✅ |
| **Retrieval** | Expected document cited | eval_run, templated corpus questions | n/a | 0.93 (356/382) | ≥ 0.95 | ⚠️ |
| Retrieval | Recall@3 on v1 book questions | `evals.retrieval_eval` (v1 harness) | 0.878 | n/a (book not indexed) | — | — |
| **Answers** | False refusal rate (answerable questions refused) | eval_run | n/a | 0.034 (13/382) | ≤ 0.05 | ✅ |
| Answers | Sentences with a valid citation | verifier (enforced in code) | filename only | 100% by construction | 100% | ✅ |
| Answers | Faithfulness judged by an LLM | LLM judge on eval answers | ⏳ | ⏳ needs API key | ≥ 0.95 | ⏳ |
| Answers | Helpful rate (👍 / rated answers) | `/v1/admin/metrics` → `feedback.helpful_rate` | none | ⏳ needs users | ≥ 0.80 | ⏳ |
| **Corpus** | Licence-checked documents | `uv run python -m app.ingest stats` | 1 book (unlicensed) | 253 → growing to ~1,500 | 1,000–2,000 | ⚠️ |
| Corpus | Documents with an unknown or non-commercial licence | ingestor licence gate | 1 | 0 | 0 | ✅ |
| **Speed** | Answer latency p50 / p95 | eval_run (CPU laptop, local models) | not measured | 2.6 s / 5.1 s | p95 ≤ 3 s on server | ⚠️ |
| Speed | Cold start | v1 harness | 149 s | models load once at startup | < 10 s | ⏳ |
| **Cost** | Cost per answer | `tokens` in `/v1/admin/metrics` × price | not measured | $0 (free local stack) | track; alert on +30% | ✅ |
| **Engineering** | Backend tests | `uv run pytest` | 10 | 160 | grows with features | ✅ |
| Engineering | Web tests | `npm test` | 0 | 6 | grows with features | ✅ |
| Engineering | Known CVEs in dependencies | pip-audit / npm audit | 85 | 0 high (npm audit) | 0 | ✅ |

## 2. How to improve each one

| If this is low… | Do this | Then check |
|---|---|---|
| Expected document cited | Add synonyms to `backend/app/rag/query.py` (`SYNONYMS`, `BRAND_TO_GENERIC`); try `EMBEDDINGS_PROVIDER=openai` or a larger local model; give consumer pages a small boost for "what is / symptoms" questions | eval_run corpus rows |
| False refusals | Lower `ABSTAIN_THRESHOLD` a little; let the verifier keep label sentences that mention doses only as context (they are dropped for public users today) | eval_run refused rows |
| Faithfulness | Switch from extractive to an LLM (`LLM_PROVIDER=openai`): answers read better, and the verifier still blocks unsupported sentences | LLM-judge faithfulness |
| Crisis recall | Every miss becomes a new row in `tests/test_guards.py` first, then a rule; add an LLM classifier beside the rules | guard tests + eval_run |
| Helpful rate | Read 👎 answers weekly, add the failures to the golden set, fix retrieval or wording | `/v1/admin/metrics` |
| Latency | Use Qdrant Cloud and a hosted reranker; cache common questions (already on); run 2+ API workers | eval_run p95, `scripts/loadtest.py` |
| Corpus size | Add seeds in `backend/app/ingest/seeds.py`, then `ingest run` and `ingest export` | `ingest stats` |
| Cost (with an LLM) | Keep extractive answers for cache hits; use a small model for rewrite and judge; daily quotas | `tokens` in admin metrics |

## 3. Live product metrics (`/v1/admin/metrics`)

```json
{
  "window_days": 7,
  "usage": {"answers": 0, "active_conversations": 0, "users_total": 0, "new_users": 0},
  "answers_by_status": {"complete": 0, "refused": 0, "crisis": 0, "emergency": 0},
  "answer_rate": 0.0,
  "refusals_by_reason": {"no_sources": 0, "out_of_scope": 0, "dosing": 0},
  "safety_events": {"crisis": 0, "emergency": 0, "injection": 0},
  "latency_ms": {"p50": 0, "p95": 0, "max": 0},
  "tokens": {"in": 0, "out": 0},
  "feedback": {"up": 0, "down": 0, "helpful_rate": 0.0, "coverage": 0.0},
  "corpus": {"documents_by_source": {}, "documents": 0}
}
```

What to watch:
- A jump in `refusals_by_reason.no_sources` means users ask about things the corpus doesn't cover. Add documents.
- A rise in `safety_events.crisis` needs a human look at the trend (counts only; message text is never exposed here).
- `feedback.coverage` below about 5% means too few people rate answers to trust `helpful_rate`.

## 4. Caveats

- The corpus questions are templated from section headings and not yet reviewed by a person
  (`evals/golden/v2_corpus.jsonl`, `reviewed: false`). Treat 0.93 as a retrieval smoke test.
- Latency was measured on a laptop CPU with local models, not on production hardware.
- v1 and v2 use different corpora, so v1 retrieval numbers aren't directly comparable.
