# Resume Metrics — AskMedi v1 baseline → v2

Measured 2026-11-11 on git `dd00aba` (v1). Raw data: `evals/results/v1/*.json`, report: `evals/results/v1/REPORT.md`.
Rerun the same harness after v2: `python -m evals.report --label v2 --baseline v1`.

**Rule for the resume:** only use numbers the harness produced, on the **same golden set**, and say how they were measured. Recruiters at AI companies ask "how did you measure that?"

---

## 1. v1 baseline (measured)

### Retrieval: 41 answerable questions, gold page known
| Metric | v1 | v2 target |
|---|---|---|
| Recall@3 (right page in the 3 chunks v1 uses) | **87.8%** | ≥ 95% |
| Recall@1 | **68.3%** | ≥ 85% |
| Recall@5 | 95.1% | ≥ 98% |
| MRR@10 | **0.795** | ≥ 0.90 |
| Query latency p95 (local vector search) | 26 ms | keep < 50 ms (+ rerank budget) |

Misses at k=3: ic12 amniocentesis, ic20 asthma, ic30 breast cancer, ic34 breast surgery, ic35 alcoholism. Mostly answers that span two pages or near-duplicate neighbouring pages.

### Runtime and ops
| Metric | v1 | v2 target |
|---|---|---|
| Cold start (imports + model + PDF + embed, no cache) | **149 s** | < 10 s (hosted embeddings, prebuilt index) |
| Embedding model load | 19.2 s | 0 (no torch in web process) |
| RAM after embedding model load | **443 MB** | < 200 MB |
| RAM with local index | 777 MB | n/a (Pinecone) |
| Install footprint (site-packages) | **2,462 MB** | < 400 MB |
| Time to embed corpus (CPU) | 101 s for 5,859 chunks | — |

### Corpus
| Metric | v1 | v2 target |
|---|---|---|
| Documents | **1** (Gale Encyclopedia of Medicine vol. 1, 2004, topics A–B only) | **~1,000** licence-checked docs + papers |
| Pages / chunks | 637 / 5,859 | ~9k chunks |
| Junk chunks (< 50 chars) | 16 | 0 |
| Citation granularity | filename only | page/section-level, clickable |

### Engineering quality
| Metric | v1 | v2 target |
|---|---|---|
| Automated tests | **10** | 80+ (unit + API + guard + eval gates) |
| Coverage (app + src) | **74%** | ≥ 90% |
| Known dependency vulnerabilities (pip-audit) | **85 across 12 packages** (pypdf 67, transformers 6) | **0** |
| Static security findings (bandit) | 1 medium (bind 0.0.0.0 in dev entrypoint) | 0 |
| Lint issues (ruff default) | 0 | 0 (stricter rule set) |
| Avg / max cyclomatic complexity | 2.14 / 9 (`login`, `stream_answer`) | ≤ 2.5 / ≤ 7 |
| CI runs tests | **no** (CI only deploys) | yes, plus eval gate |
| Working Docker build | **no** (runs missing `app.py`) | yes |
| DB migrations | none | Alembic |

### Not measured yet (needs `OPENAI_API_KEY`), run before any v2 change
```
.venv/Scripts/python -m evals.answer_eval --label v1 && .venv/Scripts/python -m evals.report --label v1
```
| Metric | v1 | v2 target |
|---|---|---|
| Faithfulness (claims supported by context) | ? | ≥ 0.95 |
| Answer correctness | ? | ≥ 0.85 |
| False refusal rate | ? | ≤ 10% |
| Correct refusal (out-of-corpus / off-topic) | ? | ≥ 95% |
| Emergency recall | ? | **100%** |
| Dosing/diagnosis refusal | ? | 100% |
| Jailbreak success | ? | 0% |
| Page-level citation rate | **0%** (by design) | 100% |
| TTFT p50 / full answer p95 | ? | ≤ 1.5 s / ≤ 8 s |
| Cost per answer | ? | track; ≤ v1 |

---

## 2. Resume bullets (fill X after v2; keep only what improved)

Templates. Replace X/Y with harness output.

- Rebuilt a medical RAG assistant (Flask → **FastAPI + Flutter Android**) serving grounded answers over **~1,000 licence-vetted documents and research papers** (up from 1 book), with page-level citations on **100%** of answers.
- Designed an **evaluation harness** (85 → 300+ labelled cases across 7 risk categories) gating CI; raised retrieval **Recall@1 from 68% to X%** and **MRR from 0.80 to X** with hybrid search + reranking.
- Cut hallucinations: **faithfulness X% → Y%** via cite-or-refuse generation, a relevance gate, and LLM groundedness verification; **jailbreak success X% → 0%**; **emergency-detection recall 100%**.
- Cut cold start **149 s → X s** and memory **443 MB → X MB** by moving embeddings out of the web process; shrank install **2.5 GB → X MB**.
- Took the codebase to production standard: **85 → 0 known CVEs**, tests **10 → X** (coverage **74% → X%**), CI with test + eval gates, Alembic migrations, working container build.

Interview story (STAR): *"v1 worked in demos but I had no idea how often it was wrong. So I built evals first, measured the baseline, and only then changed the RAG. Every change had to beat the baseline in CI."*

## 2b. Measured v2 numbers (2026-11-15, free local stack, no API keys)

Source: `evals/results/v2/REPORT.md` (fastembed bge-small + BM25 hybrid, MiniLM cross-encoder, extractive generator).

| Metric | v2 |
|---|---|
| Corpus | 253 licence-checked docs (MedlinePlus, openFDA, PMC OA reviews), 4,906 vectors; 90 PDFs + JATS downloaded |
| Held-out safety rows (v0: emergency, dosing, jailbreak, off-topic) | 32/32 pass; **crisis + emergency recall 1.00** |
| Corpus questions citing the expected document | 356/382 (**93%**); consumer 95%, drug labels 89% |
| False refusals on corpus questions | 13/382 (3.4%) |
| Latency p50 / p95 (CPU laptop, local models) | ~2.6 s / ~5 s |
| Backend tests | 157 passing |

Caveat: the 382 corpus questions are templated from section headings and not yet human-reviewed, so treat 93% as a retrieval smoke test. Several "misses" answered correctly from a PMC review instead of the templated MedlinePlus page.

## 3. Caveats (be honest if asked)
- Golden set v0 was AI-drafted from book pages and is not yet human-reviewed. Questions reuse book wording, so recall is optimistic. v2 adds paraphrased questions; compare v1 vs v2 on the **same** set.
- Retrieval measured on a local numpy replica of v1 (same loader, splitter 500/20, MiniLM-L6, cosine, k=3), not on the Pinecone index. Ranking should match; latency doesn't include the network.
- Corpus licence: Gale content is copyrighted. Don't claim it as a production corpus; v2 replaces it.
