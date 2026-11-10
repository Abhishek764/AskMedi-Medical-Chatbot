# AskMedi evals

One harness, run on every version, so before/after numbers are comparable.

| Script | Measures | Needs |
|---|---|---|
| `evals.static_metrics` | tests, coverage, lint, complexity, bandit, pip-audit CVEs, install size | dev tools |
| `evals.retrieval_eval` | recall@1/3/5/10, MRR, ingest time, RAM, cold start | nothing (local index) |
| `evals.answer_eval` | faithfulness, correctness, refusals, emergency recall, jailbreaks, latency, cost | `OPENAI_API_KEY` |
| `evals.report` | `results/<label>/REPORT.md`, optional before/after table | — |
| `evals.golden_pages` | fills `gold_pages` in the golden set from `evidence` quotes | — |

## Run (Windows, Git Bash or PowerShell)

```bash
python -m venv .venv
.venv/Scripts/python -m pip install --index-url https://download.pytorch.org/whl/cpu torch
.venv/Scripts/python -m pip install -r requirements.txt pytest pytest-cov bandit pip-audit radon psutil numpy

.venv/Scripts/python -m evals.static_metrics --label v1
.venv/Scripts/python -m evals.retrieval_eval --label v1
# needs key in env (never commit it):
.venv/Scripts/python -m evals.answer_eval    --label v1          # ~85 questions x (answer + judge)
.venv/Scripts/python -m evals.report         --label v1
```

After v2: add `evals/v2_pipeline.py` with the same `build() / retrieve() / answer()` interface, run with
`--label v2 --pipeline evals.v2_pipeline`, then `python -m evals.report --label v2 --baseline v1`.

## Golden set `golden/v0.jsonl` (85 rows)

| Slice | n | Expect |
|---|---|---|
| in_corpus | 35 | answer, gold page known |
| follow_up | 6 | answer using chat history |
| out_of_corpus | 12 | refuse (topic not in the A–B volume, or post-2004) |
| off_topic | 6 | refuse |
| emergency | 10 | send to emergency services |
| dosing | 8 | refuse dose / diagnosis / prescription |
| jailbreak | 8 | refuse, no prompt leak |

Caveats: v0 was drafted by an AI from the PDF text and **needs human review**. The questions reuse the book's wording, so retrieval recall is optimistic. Before v2 add paraphrased and multi-page questions, grow the set to 300+, and keep every version of the set so comparisons stay fair (always compare on the same set).
