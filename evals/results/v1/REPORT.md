# AskMedi metrics — `v1` (git dd00aba)


## Retrieval

| Metric | Value |
|---|---|
| Recall@3 (gold page in top 3) | 0.878 |
| Recall@1 | 0.683 |
| Recall@5 | 0.951 |
| MRR@10 | 0.795 |
| Retrieval latency p95 (ms, local) | 26.078 |

## Answers

| Metric | Value |
|---|---|
| Faithfulness (claims supported) | — |
| Answer correctness | — |
| False refusal rate | — |
| Page-level citation rate | — |

## Safety

| Metric | Value |
|---|---|
| Correct refusal (out-of-scope) | — |
| Emergency recall | — |
| Dosing/diagnosis refusal | — |
| Jailbreak success rate | — |

## Speed & cost

| Metric | Value |
|---|---|
| Time to first token p50 (s) | — |
| Full answer p95 (s) | — |
| Cost per answer (USD) | — |

## Runtime

| Metric | Value |
|---|---|
| Embedding model load (s) | 19.18 |
| RAM after model load (MB) | 443 |
| RAM with index (MB) | 777 |

## Corpus

| Metric | Value |
|---|---|
| Documents | 1 |
| Pages | 637 |
| Chunks | 5,859 |
| Junk chunks (<50 chars) | 16 |

## Engineering

| Metric | Value |
|---|---|
| Automated tests | 10 |
| Test coverage % (app+src) | 74 |
| Test suite time (s) | 10.33 |
| Lint issues (ruff) | 0 |
| Avg cyclomatic complexity | 2.14 |
| Static security findings (bandit) | 1 |
| Known dependency CVEs (pip-audit) | 85 |
| Install footprint (MB) | 2,462 |
| Python SLOC (excl. tests) | 534 |
| CI runs tests | no |

_Not yet measured: answers._
