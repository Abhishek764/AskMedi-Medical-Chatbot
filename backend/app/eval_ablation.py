"""Retrieval ablation: how much does each stage add? Same questions, same index, four modes.

    uv run python -m app.eval_ablation                      # all golden corpus rows
    uv run python -m app.eval_ablation --reviewed-only      # only rows a person has reviewed

Modes: dense only · BM25 only · hybrid (dense + BM25, RRF) · hybrid + cross-encoder rerank.
Metric unit is the document: a question counts as found at k if its expected document is among
the first k distinct documents retrieved. Writes ../evals/results/v2/ablation.{md,json}.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

from app.core.config import get_settings
from app.core.container import Container
from app.rag.query import plan_query
from app.rag.retriever import Mode

ROOT = Path(__file__).resolve().parents[2] / "evals"
GOLDEN = ROOT / "golden" / "v2_corpus.jsonl"
OUT = ROOT / "results" / "v2"
MODES: tuple[Mode, ...] = ("dense", "bm25", "hybrid", "hybrid_rerank")
LABELS = {
    "dense": "Dense only (bge-small)",
    "bm25": "BM25 only",
    "hybrid": "Hybrid (dense + BM25, RRF)",
    "hybrid_rerank": "Hybrid + rerank (production)",
}
KS = (1, 3, 5, 10)


def doc_ranking(ranked: list[object]) -> list[str]:
    seen: list[str] = []
    for r in ranked:
        d = r.doc_id  # type: ignore[attr-defined]
        if d not in seen:
            seen.append(d)
    return seen


async def run(reviewed_only: bool, limit: int | None) -> dict[str, object]:
    rows = [
        json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if reviewed_only:
        rows = [r for r in rows if r.get("reviewed")]
    rows = rows[:limit] if limit else rows
    if not rows:
        raise SystemExit("No golden rows to evaluate (check --reviewed-only / --limit).")
    container = Container(get_settings())
    await container.startup()
    results: dict[str, dict[str, object]] = {}
    try:
        for mode in MODES:
            ranks: list[int | None] = []
            latencies: list[float] = []
            for r in rows:
                t0 = time.perf_counter()
                ranked, _ = await container.retriever.rank(
                    plan_query(str(r["question"])), allow_dosing=False, mode=mode
                )
                latencies.append((time.perf_counter() - t0) * 1000)
                docs = doc_ranking(ranked)
                ranks.append(docs.index(r["expect_doc"]) + 1 if r["expect_doc"] in docs else None)
            n = len(ranks)
            results[mode] = {
                **{f"recall@{k}": round(sum(1 for x in ranks if x and x <= k) / n, 3) for k in KS},
                "mrr": round(sum(1 / x for x in ranks if x) / n, 3),
                "p50_ms": round(statistics.median(latencies)),
                "rows": n,
            }
            print(mode, results[mode], flush=True)
    finally:
        await container.shutdown()
    s = get_settings()
    return {
        "golden": GOLDEN.name,
        "reviewed_only": reviewed_only,
        "rows": len(rows),
        "config": {
            "embeddings": s.embeddings_model,
            "reranker": s.rerank_model,
            "collection": s.qdrant_collection,
        },
        "results": results,
    }


def report(data: dict[str, object]) -> str:
    res = data["results"]  # type: ignore[index]
    lines = [
        "# Retrieval ablation",
        "",
        f"{data['rows']} questions from `evals/golden/{data['golden']}`"
        + (" (reviewed rows only)" if data["reviewed_only"] else " (templated, not yet reviewed)")
        + f". Embeddings `{data['config']['embeddings']}`, reranker `{data['config']['reranker']}`.",  # type: ignore[index]
        "A question is found at k when its expected document is in the first k distinct documents.",
        "",
        "| Mode | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | p50 latency |",
        "|---|---|---|---|---|---|---|",
    ]
    for mode in MODES:
        r = res[mode]  # type: ignore[index]
        lines.append(
            f"| {LABELS[mode]} | {r['recall@1']:.3f} | {r['recall@3']:.3f} | {r['recall@5']:.3f} | "
            f"{r['recall@10']:.3f} | {r['mrr']:.3f} | {r['p50_ms']} ms |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    ap = argparse.ArgumentParser(prog="python -m app.eval_ablation")
    ap.add_argument("--reviewed-only", action="store_true")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    data = asyncio.run(run(args.reviewed_only, args.limit))
    OUT.mkdir(parents=True, exist_ok=True)
    suffix = "-reviewed" if args.reviewed_only else ""
    (OUT / f"ablation{suffix}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (OUT / f"ablation{suffix}.md").write_text(report(data), encoding="utf-8")
    print(report(data))


if __name__ == "__main__":
    main()
