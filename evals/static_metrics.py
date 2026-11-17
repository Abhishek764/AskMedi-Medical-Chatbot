"""Engineering metrics: size, tests, coverage, lint, security, dependencies.

Usage: python -m evals.static_metrics --label v1
Needs: pytest, pytest-cov, ruff, bandit, pip-audit, radon (dev tools only).
"""
import argparse
import json
import re
import subprocess
import sys
import time

from evals.common import ROOT, write_json

PY = sys.executable
CODE_DIRS = ["app", "src"]


def run(cmd, timeout=900):
    p = subprocess.run(
        cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout,
        encoding="utf-8", errors="replace",
    )
    return p.returncode, p.stdout, p.stderr


def tracked_files():
    _, out, _ = run(["git", "ls-files"])
    return [f for f in out.splitlines() if f]


def loc():
    by_ext, sloc_py = {}, 0
    for f in tracked_files():
        if f.endswith((".pdf", ".png", ".ipynb")) or f.startswith("evals/"):
            continue
        try:
            lines = (ROOT / f).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        ext = f.rsplit(".", 1)[-1] if "." in f else f
        by_ext[ext] = by_ext.get(ext, 0) + len(lines)
        if f.endswith(".py") and not f.startswith("tests/"):
            sloc_py += sum(1 for ln in lines if ln.strip() and not ln.strip().startswith("#"))
    return {"lines_by_ext": by_ext, "python_sloc_excl_tests": sloc_py}


def tests():
    t0 = time.perf_counter()
    rc, out, err = run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                        "--cov=app", "--cov=src", "--cov-report=term", "tests"])
    dur = round(time.perf_counter() - t0, 2)
    text = out + err
    m = re.search(r"(\d+) passed", text)
    f = re.search(r"(\d+) failed", text)
    cov = re.search(r"^TOTAL\s+\d+\s+\d+\s+(\d+)%", text, re.M)
    return {
        "passed": int(m.group(1)) if m else 0,
        "failed": int(f.group(1)) if f else 0,
        "duration_s": dur,
        "coverage_pct_app_src": int(cov.group(1)) if cov else None,
        "exit_code": rc,
    }


def lint():
    rc, out, _ = run([PY, "-m", "ruff", "check", "--output-format=json",
                      "--exclude", ".venv,evals", "."])
    try:
        items = json.loads(out or "[]")
    except json.JSONDecodeError:
        return {"error": out[:300]}
    codes = {}
    for it in items:
        codes[it["code"]] = codes.get(it["code"], 0) + 1
    return {"ruff_issues": len(items), "by_rule": codes}


def security():
    res = {}
    rc, out, _ = run([PY, "-m", "bandit", "-r", *CODE_DIRS, "store_index.py",
                      "wsgi.py", "-f", "json", "-q"])
    try:
        data = json.loads(out)
        sev = {}
        for r in data.get("results", []):
            sev[r["issue_severity"]] = sev.get(r["issue_severity"], 0) + 1
        res["bandit_findings"] = len(data.get("results", []))
        res["bandit_by_severity"] = sev
        res["bandit_issues"] = [
            f'{r["test_id"]} {r["issue_severity"]} {r["filename"]}:{r["line_number"]} {r["issue_text"]}'
            for r in data.get("results", [])
        ]
    except json.JSONDecodeError:
        res["bandit_error"] = out[:300]

    rc, out, err = run([PY, "-m", "pip_audit", "-r", "requirements.txt",
                        "--format", "json", "--progress-spinner", "off"], timeout=1200)
    try:
        start = out.find("{")
        if start < 0:
            raise ValueError("no JSON in pip-audit output")
        data = json.loads(out[start:])
        vulns = [
            {"package": d["name"], "version": d["version"],
             "ids": sorted({v["id"] for v in d.get("vulns", [])})}
            for d in data.get("dependencies", []) if d.get("vulns")
        ]
        res["vulnerable_packages"] = len(vulns)
        res["known_vulns"] = sum(len(v["ids"]) for v in vulns)
        res["vulns"] = vulns
    except (json.JSONDecodeError, ValueError):
        res["pip_audit_error"] = (err or out)[-400:]
    return res


def complexity():
    rc, out, _ = run([PY, "-m", "radon", "cc", "-s", "-a", "-j", *CODE_DIRS])
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {}
    blocks = [b for items in data.values() for b in items if isinstance(b, dict)]
    ccs = [b["complexity"] for b in blocks]
    worst = sorted(blocks, key=lambda b: -b["complexity"])[:3]
    return {
        "functions": len(ccs),
        "avg_cyclomatic": round(sum(ccs) / len(ccs), 2) if ccs else None,
        "max_cyclomatic": max(ccs) if ccs else None,
        "worst": [f'{b["name"]}={b["complexity"]}' for b in worst],
    }


def deps():
    direct = [ln for ln in (ROOT / "requirements.txt").read_text().splitlines()
              if ln.strip() and not ln.startswith(("#", "-e"))]
    rc, out, _ = run([PY, "-m", "pip", "list", "--format=json"])
    installed = json.loads(out) if rc == 0 else []
    import site
    from pathlib import Path

    size = 0
    for sp in site.getsitepackages():
        for p in Path(sp).rglob("*"):
            try:
                if p.is_file():
                    size += p.stat().st_size
            except OSError:
                pass
    return {
        "direct_deps": len(direct),
        "installed_packages_total": len(installed),
        "site_packages_mb": round(size / 1e6),
    }


def project_facts():
    def read(p):
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    routes = 0
    for f in (ROOT / "app").rglob("*.py"):
        routes += len(re.findall(r"@\w+\.(?:route|get|post|put|delete)\(", read(f)))
    workflows = "".join(read(p) for p in (ROOT / ".github/workflows").glob("*.y*ml"))
    _, n_commits, _ = run(["git", "rev-list", "--count", "HEAD"])
    _, sha, _ = run(["git", "rev-parse", "--short", "HEAD"])
    return {
        "http_routes": routes,
        "commits": int(n_commits.strip() or 0),
        "git_sha": sha.strip(),
        "ci_runs_tests": "pytest" in workflows,
        "dockerfile_entrypoint_exists": (ROOT / "app.py").exists(),
        "migrations_dir": (ROOT / "migrations").exists(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="v1")
    a = ap.parse_args()
    data = {
        "project": project_facts(),
        "loc": loc(),
        "tests": tests(),
        "lint": lint(),
        "complexity": complexity(),
        "security": security(),
        "deps": deps(),
    }
    write_json(a.label, "static", data)


if __name__ == "__main__":
    main()
