"""Ragas suite helpers (the full run needs the real index; see docs/OBSERVABILITY.md)."""

import pytest

pytest.importorskip("ragas")

from app import eval_ragas  # noqa: E402


async def test_id_metrics_are_free_and_correct():
    from ragas import SingleTurnSample
    from ragas.metrics import IDBasedContextPrecision, IDBasedContextRecall

    s = SingleTurnSample(
        retrieved_context_ids=["medlineplus:dengue", "pmc:1"],
        reference_context_ids=["medlineplus:dengue"],
    )
    assert await IDBasedContextRecall().single_turn_ascore(s) == 1.0
    assert await IDBasedContextPrecision().single_turn_ascore(s) == 0.5


def test_no_key_means_no_judge(settings):
    assert eval_ragas.judge_llm(settings) is None


def test_report_lists_misses():
    data = {
        "summary": {
            "golden": "g.jsonl",
            "rows": 2,
            "answered": 1,
            "judge_model": None,
            "seconds": 1.0,
            "metrics": {
                "id_context_recall": 0.5,
                "id_context_precision": 0.25,
                "faithfulness": None,
                "context_relevance": None,
            },
            "judged_rows": {"faithfulness": 0, "context_relevance": 0},
        },
        "rows": [
            {
                "id": "a",
                "question": "q1",
                "id_context_recall": 1.0,
                "expected": ["x"],
                "retrieved": ["x"],
            },
            {
                "id": "b",
                "question": "q2",
                "id_context_recall": 0.0,
                "expected": ["y"],
                "retrieved": ["z"],
            },
        ],
    }
    md = eval_ragas._report(data)
    assert "| ID context recall | 0.500 | 2 |" in md
    assert "`b` q2" in md and "`a` q1" not in md
