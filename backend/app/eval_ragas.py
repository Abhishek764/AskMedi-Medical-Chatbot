"""Ragas evaluation suite: retrieval and answer quality on a golden set.

    uv sync --extra local --extra evals
    uv run python -m app.eval_ragas                       # free: ID-based context metrics only
    uv run python -m app.eval_ragas --judge --limit 20    # + LLM-judged metrics (Gemini/OpenAI key)
    uv run python -m app.eval_ragas --golden ../evals/golden/v2_corpus.jsonl --limit 100

Metrics (all from Ragas):
- id_context_recall      IDBasedContextRecall: share of expected documents that were retrieved.
- id_context_precision   IDBasedContextPrecision: share of retrieved documents that were expected.
- faithfulness           Faithfulness (judge): share of answer claims supported by the passages.
- context_relevance      ContextRelevance (judge): are the retrieved passages relevant to the question?

The ID metrics need no model, so they are free and deterministic. Judge metrics use the first
key found (OpenAI, else Gemini via its OpenAI-compatible endpoint). On Gemini's free tier keep
--limit small (rate limits) and use sample questions only (free-tier prompts may be used by Google).

Writes ../evals/results/v2/ragas.json and ragas.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
import warnings
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.core.container import Container
from app.rag.pipeline import UserContext
from app.rag.query import plan_query

ROOT = Path(__file__).resolve().parents[2] / "evals"
DEFAULT_GOLDEN = ROOT / "golden" / "v2_hard.jsonl"
OUT = ROOT / "results" / "v2"
GEMINI_OPENAI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def judge_llm(settings: Settings) -> tuple[Any, str] | None:
    """A Ragas LLM for judge metrics, or None when no key is configured."""
    from openai import AsyncOpenAI
    from ragas.llms import llm_factory

    if settings.openai_api_key:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        model = settings.openai_model
    elif settings.gemini_api_key:
        client = AsyncOpenAI(base_url=GEMINI_OPENAI_URL, api_key=settings.gemini_api_key)
        model = settings.gemini_model
    else:
        return None
    # Faithfulness lists every claim in the answer; the 1024-token default truncates long ones.
    return llm_factory(model, provider="openai", client=client, max_tokens=4096), model


def _load(path: Path, limit: int | None) -> list[dict[str, Any]]:
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").split("\n") if x.strip()]
    rows = [r for r in rows if r.get("question") and r.get("expect_docs")]
    return rows[:limit] if limit else rows


async def _sample(container: Container, q: str, answer_it: bool) -> dict[str, Any]:
    """Retrieve (as the pipeline does) and, for judge metrics, answer; collect what Ragas needs."""
    plan = plan_query(q, [])
    res = await container.retriever.retrieve(plan, allow_dosing=False)
    doc_ids = list(dict.fromkeys(p.doc_id for p in res.passages))
    contexts = [p.parent_text or p.text for p in res.passages]
    status, answer = "not_run", ""
    if not answer_it:  # ID metrics only need retrieval: no LLM calls
        return {"doc_ids": doc_ids, "contexts": contexts, "status": status, "answer": answer}
    status = "error"
    async for ev in container.pipeline.answer_stream(q, [], UserContext()):
        if ev.type == "result":
            rec = ev.data["record"]
            status, answer = rec.status, rec.content
    return {"doc_ids": doc_ids, "contexts": contexts, "status": status, "answer": answer}


async def run(container: Container, golden: Path, limit: int | None, judge: bool) -> dict[str, Any]:
    from ragas import SingleTurnSample
    from ragas.metrics import IDBasedContextPrecision, IDBasedContextRecall

    container.pipeline.kv = None  # no answer cache during evals
    recall_m, precision_m = IDBasedContextRecall(), IDBasedContextPrecision()
    judge_metrics: dict[str, Any] = {}
    judge_model = None
    if judge:
        found = judge_llm(container.settings)
        if found is None:
            raise SystemExit("--judge needs OPENAI_API_KEY or GEMINI_API_KEY in .env")
        llm, judge_model = found
        from ragas.metrics.collections import ContextRelevance, Faithfulness

        judge_metrics = {
            "faithfulness": Faithfulness(llm=llm),
            "context_relevance": ContextRelevance(llm=llm),
        }

    rows = _load(golden, limit)

    async def one(row: dict[str, Any]) -> dict[str, Any]:
        q = str(row["question"])
        s = await _sample(container, q, answer_it=bool(judge_metrics))
        sample = SingleTurnSample(
            user_input=q,
            # Ragas rejects an empty list; a blank id scores 0, which is right for no retrieval
            retrieved_context_ids=s["doc_ids"] or [""],
            reference_context_ids=list(row["expect_docs"]),
        )
        out: dict[str, Any] = {
            "id": row.get("id"),
            "question": q,
            "status": s["status"],
            "retrieved": s["doc_ids"],
            "expected": row["expect_docs"],
            "id_context_recall": float(await recall_m.single_turn_ascore(sample)),
            "id_context_precision": float(await precision_m.single_turn_ascore(sample)),
        }
        if judge_metrics and s["contexts"]:
            out["context_relevance"] = await _safe(
                judge_metrics["context_relevance"].ascore(
                    user_input=q, retrieved_contexts=s["contexts"]
                )
            )
            if s["status"] == "complete" and s["answer"]:
                out["faithfulness"] = await _safe(
                    judge_metrics["faithfulness"].ascore(
                        user_input=q, response=s["answer"], retrieved_contexts=s["contexts"]
                    )
                )
        return out

    t0 = time.perf_counter()
    results = []
    for i, row in enumerate(rows, 1):  # sequential: local Qdrant and free-tier rate limits
        results.append(await one(row))
        if i % 10 == 0:
            print(f"  {i}/{len(rows)}", flush=True)

    def mean(key: str) -> float | None:
        vals = [r[key] for r in results if isinstance(r.get(key), float)]
        return round(statistics.fmean(vals), 4) if vals else None

    summary = {
        "golden": golden.name,
        "rows": len(results),
        "judge_model": judge_model,
        "seconds": round(time.perf_counter() - t0, 1),
        "metrics": {
            k: mean(k)
            for k in (
                "id_context_recall",
                "id_context_precision",
                "faithfulness",
                "context_relevance",
            )
        },
        "judged_rows": {
            k: sum(isinstance(r.get(k), float) for r in results)
            for k in ("faithfulness", "context_relevance")
        },
        "answered": sum(r["status"] == "complete" for r in results) if judge_metrics else None,
    }
    return {"summary": summary, "rows": results}


async def _safe(coro: Any) -> float | None:
    """Judge calls can fail on a free tier (rate limit, 503); skip the row instead of the run."""
    try:
        res = await coro
        return float(res.value) if res.value is not None else None
    except Exception as exc:  # noqa: BLE001 - provider errors vary; the row is just unjudged
        print(f"  judge skipped a row: {type(exc).__name__}", flush=True)
        return None


def _report(data: dict[str, Any]) -> str:
    s = data["summary"]
    m = s["metrics"]
    fmt = lambda v: "—" if v is None else f"{v:.3f}"  # noqa: E731
    lines = [
        "# Ragas evaluation",
        "",
        f"Golden set `{s['golden']}`, {s['rows']} questions"
        + (f", {s['answered']} answered. " if s["answered"] is not None else " (retrieval only). ")
        + f"Judge: {s['judge_model'] or 'none (ID metrics only)'}. {s['seconds']} s.",
        "",
        "| Metric | Score | Rows |",
        "|---|---|---|",
        f"| ID context recall | {fmt(m['id_context_recall'])} | {s['rows']} |",
        f"| ID context precision | {fmt(m['id_context_precision'])} | {s['rows']} |",
        f"| Faithfulness (judge) | {fmt(m['faithfulness'])} | {s['judged_rows']['faithfulness']} |",
        f"| Context relevance (judge) | {fmt(m['context_relevance'])} | {s['judged_rows']['context_relevance']} |",
        "",
        "## Misses (expected document not retrieved)",
        "",
    ]
    misses = [r for r in data["rows"] if r["id_context_recall"] < 1]
    lines += [
        f"- `{r['id']}` {r['question']} — expected {r['expected']}, got {r['retrieved'][:3]}"
        for r in misses
    ] or ["None."]
    return "\n".join(lines) + "\n"


async def _main(args: argparse.Namespace) -> None:
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    container = Container(get_settings())
    await container.startup()
    try:
        data = await run(container, Path(args.golden), args.limit, args.judge)
    finally:
        await container.shutdown()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ragas.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    report = _report(data)
    (OUT / "ragas.md").write_text(report, encoding="utf-8")
    print(report)


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m app.eval_ragas")
    ap.add_argument("--golden", default=str(DEFAULT_GOLDEN))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--judge", action="store_true", help="add LLM-judged metrics (needs a key)")
    asyncio.run(_main(ap.parse_args()))


if __name__ == "__main__":
    main()
