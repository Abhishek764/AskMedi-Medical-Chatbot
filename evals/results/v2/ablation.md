# Retrieval ablation

382 questions from `evals/golden/v2_corpus.jsonl` (templated, not yet reviewed). Embeddings `BAAI/bge-small-en-v1.5`, reranker `Xenova/ms-marco-MiniLM-L-6-v2`.
A question is found at k when its expected document is in the first k distinct documents.

| Mode | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | p50 latency |
|---|---|---|---|---|---|---|
| Dense only (bge-small) | 0.932 | 0.990 | 0.995 | 0.995 | 0.960 | 1618 ms |
| BM25 only | 0.654 | 0.856 | 0.898 | 0.937 | 0.762 | 2446 ms |
| Hybrid (dense + BM25, RRF) | 0.877 | 0.987 | 0.992 | 0.995 | 0.930 | 3765 ms |
| Hybrid + rerank (production) | 0.929 | 0.982 | 0.984 | 0.987 | 0.955 | 6266 ms |
