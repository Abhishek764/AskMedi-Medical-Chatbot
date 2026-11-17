"""Build a Markdown scorecard from results JSON; optionally compare two labels.

Usage:
  python -m evals.report --label v1
  python -m evals.report --label v2 --baseline v1     # before/after table
"""
import argparse
import json

from evals.common import RESULTS, ROOT, safe_label

# (section, json path, display name, better: "up" | "down" | None)
METRICS = [
    ("Retrieval", "retrieval.recall_at_k.@3", "Recall@3 (gold page in top 3)", "up"),
    ("Retrieval", "retrieval.recall_at_k.@1", "Recall@1", "up"),
    ("Retrieval", "retrieval.recall_at_k.@5", "Recall@5", "up"),
    ("Retrieval", "retrieval.mrr_at_10", "MRR@10", "up"),
    ("Retrieval", "retrieval.query_latency_ms.p95", "Retrieval latency p95 (ms, local)", "down"),
    ("Answers", "answers.quality.faithfulness_supported_claims", "Faithfulness (claims supported)", "up"),
    ("Answers", "answers.quality.answer_correctness", "Answer correctness", "up"),
    ("Answers", "answers.quality.false_refusal_rate", "False refusal rate", "down"),
    ("Answers", "answers.quality.inline_page_citation_rate", "Page-level citation rate", "up"),
    ("Safety", "answers.safety.correct_refusal_rate_unanswerable", "Correct refusal (out-of-scope)", "up"),
    ("Safety", "answers.safety.emergency_recall", "Emergency recall", "up"),
    ("Safety", "answers.safety.dosing_diagnosis_refusal_rate", "Dosing/diagnosis refusal", "up"),
    ("Safety", "answers.safety.jailbreak_success_rate", "Jailbreak success rate", "down"),
    ("Speed & cost", "answers.latency.ttft_s.p50", "Time to first token p50 (s)", "down"),
    ("Speed & cost", "answers.latency.total_s.p95", "Full answer p95 (s)", "down"),
    ("Speed & cost", "answers.cost.usd_per_answer.mean", "Cost per answer (USD)", "down"),
    ("Runtime", "retrieval.ingest_and_runtime.model_load_s", "Embedding model load (s)", "down"),
    ("Runtime", "retrieval.ingest_and_runtime.rss_mb_after_model", "RAM after model load (MB)", "down"),
    ("Runtime", "retrieval.ingest_and_runtime.rss_mb_after_index", "RAM with index (MB)", "down"),
    ("Corpus", "retrieval.ingest_and_runtime.documents", "Documents", "up"),
    ("Corpus", "retrieval.ingest_and_runtime.pages", "Pages", "up"),
    ("Corpus", "retrieval.ingest_and_runtime.chunks", "Chunks", None),
    ("Corpus", "retrieval.ingest_and_runtime.empty_or_tiny_chunks_lt50", "Junk chunks (<50 chars)", "down"),
    ("Engineering", "static.tests.passed", "Automated tests", "up"),
    ("Engineering", "static.tests.coverage_pct_app_src", "Test coverage % (app+src)", "up"),
    ("Engineering", "static.tests.duration_s", "Test suite time (s)", "down"),
    ("Engineering", "static.lint.ruff_issues", "Lint issues (ruff)", "down"),
    ("Engineering", "static.complexity.avg_cyclomatic", "Avg cyclomatic complexity", "down"),
    ("Engineering", "static.security.bandit_findings", "Static security findings (bandit)", "down"),
    ("Engineering", "static.security.known_vulns", "Known dependency CVEs (pip-audit)", "down"),
    ("Engineering", "static.deps.site_packages_mb", "Install footprint (MB)", "down"),
    ("Engineering", "static.loc.python_sloc_excl_tests", "Python SLOC (excl. tests)", None),
    ("Engineering", "static.project.ci_runs_tests", "CI runs tests", "up"),
]


def load(label):
    d = {}
    for name in ("static", "retrieval", "answers"):
        p = RESULTS / label / f"{name}.json"
        if p.exists():
            d[name] = json.loads(p.read_text(encoding="utf-8"))
    return d


def get(d, path):
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def fmt(v):
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:.3f}".rstrip("0").rstrip(".") if abs(v) < 100 else f"{v:,.0f}"
    return f"{v:,}" if isinstance(v, int) else str(v)


def delta(a, b, better):
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (a, b)):
        return ""
    if a == 0:
        return f"{b - a:+g}"
    pct = (b - a) / abs(a) * 100
    good = (better == "up" and b > a) or (better == "down" and b < a)
    mark = " ✅" if good else (" ⚠️" if better and a != b else "")
    return f"{pct:+.0f}%{mark}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="v1")
    ap.add_argument("--baseline")
    a = ap.parse_args()
    safe_label(a.label)
    if a.baseline:
        safe_label(a.baseline)
    cur, base = load(a.label), load(a.baseline) if a.baseline else None

    sha = get(cur, "static.project.git_sha") or "?"
    lines = [f"# AskMedi metrics — `{a.label}` (git {sha})", ""]
    if base is not None:
        lines += [f"Compared against `{a.baseline}`.", ""]
    section = None
    for sec, path, name, better in METRICS:
        if sec != section:
            section = sec
            hdr = f"| Metric | {a.baseline} | {a.label} | Δ |" if base is not None else "| Metric | Value |"
            sep = "|---|---|---|---|" if base is not None else "|---|---|"
            lines += ["", f"## {sec}", "", hdr, sep]
        v = get(cur, path)
        if base is not None:
            b = get(base, path)
            lines.append(f"| {name} | {fmt(b)} | {fmt(v)} | {delta(b, v, better)} |")
        else:
            lines.append(f"| {name} | {fmt(v)} |")
    missing = [n for n in ("static", "retrieval", "answers") if n not in cur]
    if missing:
        lines += ["", f"_Not yet measured: {', '.join(missing)}._"]
    out = RESULTS / a.label / "REPORT.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
