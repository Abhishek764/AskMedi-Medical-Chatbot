"""Shared helpers for the AskMedi eval/metrics harness."""
import json
import os
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVALS = ROOT / "evals"
GOLDEN = EVALS / "golden" / "v0.jsonl"
CACHE = EVALS / ".cache"
RESULTS = EVALS / "results"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_golden(path=GOLDEN):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("//"):
                rows.append(json.loads(line))
    return rows


def safe_label(label: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,40}", label or "") or ".." in label:
        raise SystemExit(f"invalid label {label!r} (use letters, digits, . _ -)")
    return label


def results_dir(label: str) -> Path:
    d = RESULTS / safe_label(label)
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_json(label: str, name: str, data) -> Path:
    p = results_dir(label) / f"{name}.json"
    p.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(f"wrote {p.relative_to(ROOT)}")
    return p


def pct(values, q):
    if not values:
        return None
    vals = sorted(values)
    idx = min(len(vals) - 1, max(0, round(q / 100 * (len(vals) - 1))))
    return vals[idx]


def summary(values):
    if not values:
        return {}
    return {
        "n": len(values),
        "mean": round(statistics.mean(values), 4),
        "p50": round(pct(values, 50), 4),
        "p95": round(pct(values, 95), 4),
        "max": round(max(values), 4),
    }


def rss_mb():
    try:
        import psutil

        return round(psutil.Process(os.getpid()).memory_info().rss / 1e6, 1)
    except Exception:
        return None
