"""Retrieval quality + ingestion/runtime cost. No API keys needed.

Usage: python -m evals.retrieval_eval --label v1 [--pipeline evals.v1_pipeline]

Scores every golden row that has `gold_pages` (0-indexed PDF page numbers):
  hit@k  — any of the top-k chunks comes from a gold page
  MRR@10 — 1 / rank of first gold-page chunk
"""
import argparse
import importlib
import time

from evals.common import load_golden, rss_mb, summary, write_json

KS = (1, 3, 5, 10)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="v1")
    ap.add_argument("--pipeline", default="evals.v1_pipeline")
    a = ap.parse_args()
    if not a.pipeline.startswith("evals.") or not a.pipeline.endswith("_pipeline"):
        ap.error("--pipeline must be an evals.<name>_pipeline module")
    pipe = importlib.import_module(a.pipeline)

    t0 = time.perf_counter()
    build_stats = pipe.build()
    build_stats["cold_start_total_s"] = round(time.perf_counter() - t0, 2)

    rows = [r for r in load_golden() if r.get("gold_pages")]
    hits = {k: 0 for k in KS}
    rr, lat, per_q = [], [], []
    for r in rows:
        q = r.get("retrieval_query") or r["question"]
        t = time.perf_counter()
        res = pipe.retrieve(q, max(KS))
        lat.append((time.perf_counter() - t) * 1000)
        pages = [c["page"] for c in res]
        gold = set(r["gold_pages"])
        rank = next((i + 1 for i, p in enumerate(pages) if p in gold), None)
        for k in KS:
            hits[k] += int(rank is not None and rank <= k)
        rr.append(1 / rank if rank else 0.0)
        per_q.append({"id": r["id"], "rank": rank, "top_pages": pages[:5],
                      "top_score": round(res[0]["score"], 3) if res else None})

    n = len(rows) or 1
    data = {
        "pipeline": a.pipeline,
        "questions_scored": len(rows),
        "recall_at_k": {f"@{k}": round(hits[k] / n, 3) for k in KS},
        "headline_k": getattr(pipe, "K_DEFAULT", 3),
        "mrr_at_10": round(sum(rr) / n, 3),
        "query_latency_ms": summary(lat),
        "ingest_and_runtime": build_stats,
        "rss_mb_end": rss_mb(),
        "misses": [p for p in per_q if p["rank"] is None or p["rank"] > 3],
        "per_question": per_q,
    }
    write_json(a.label, "retrieval", data)
    print("recall:", data["recall_at_k"], "mrr:", data["mrr_at_10"])


if __name__ == "__main__":
    main()
