"""Fill `gold_pages` in the golden set by locating each row's `evidence` quote.

Usage: python -m evals.golden_pages
Pages are 0-indexed (same as PyPDFLoader `page` metadata). Text is normalised
(lower-case, hyphenated line breaks joined, whitespace collapsed) before search.
Re-run whenever the golden set or the corpus PDF changes.
"""
import json
import re

from evals.common import GOLDEN, ROOT


def norm(s: str) -> str:
    s = s.lower().replace("­", "")
    s = re.sub(r"(\w)-\s+(\w)", r"\1\2", s)  # join "para- sitic"
    s = re.sub(r"[^\w%]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def main():
    from pypdf import PdfReader

    pdfs = sorted((ROOT / "data").glob("*.pdf"))
    pages = []  # (source, page_idx, normalised_text)
    for p in pdfs:
        for i, pg in enumerate(PdfReader(str(p)).pages):
            pages.append((p.name, i, norm(pg.extract_text() or "")))

    lines = GOLDEN.read_text(encoding="utf-8").splitlines()
    out, missing = [], []
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        ev = row.get("evidence")
        if ev:
            needle = norm(ev)
            hits = [i for (_, i, t) in pages if needle in t]
            row["gold_pages"] = hits
            if not hits:
                missing.append(row["id"])
        out.append(json.dumps(row, ensure_ascii=False))
    GOLDEN.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"rows={len(out)} with_evidence_missing={missing}")


if __name__ == "__main__":
    main()
