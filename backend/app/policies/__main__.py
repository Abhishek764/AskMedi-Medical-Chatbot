"""Policy library CLI. Run from backend/.

    uv run python -m app.policies build                  # download FEMA SFIP forms, parse, save, index
    uv run python -m app.policies add ../path/form.pdf --id acme-cgl --title "..." --form "..."
    uv run python -m app.policies compare                # print the exclusions table

Parsed policies are saved to POLICIES_DIR (default ../data/policies) as JSON; raw PDFs go to
RAW_DATA_DIR/policies (gitignored).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.core.container import Container
from app.policies.forms import FORMS
from app.policies.parse import parse_cfr_form, parse_generic_pdf


async def _download(url: str, dest: Path) -> Path:
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(
        timeout=60, follow_redirects=True, headers={"User-Agent": "AskMedi-ingest/2.0"}
    ) as c:
        r = await c.get(url)
        r.raise_for_status()
        if not r.content.startswith(b"%PDF"):
            raise RuntimeError(f"{url} did not return a PDF")
        dest.write_bytes(r.content)
    return dest


async def build() -> None:
    s = get_settings()
    c = Container(s)
    await c.startup()
    try:
        raw = Path(s.raw_data_dir) / "policies"
        for f in FORMS:
            pdf = await _download(f.url, raw / f"cfr2025-{f.file}.pdf")
            doc = parse_cfr_form(
                pdf,
                f.appendix,
                id=f.id,
                title=f.title,
                form=f.form,
                edition=f.edition,
                source_url=f.url,
                licence=f.licence,
            )
            c.policies.save(doc)
            n = await c.policies.index(doc)
            print(f"{f.id}: {len(doc.sections)} sections, {n} chunks indexed")
    finally:
        await c.shutdown()


async def add(args: argparse.Namespace) -> None:
    c = Container(get_settings())
    await c.startup()
    try:
        doc = parse_generic_pdf(
            Path(args.path),
            id=args.id,
            title=args.title,
            form=args.form,
            edition=args.edition,
            source_url=args.url,
            licence=args.licence,
        )
        c.policies.save(doc)
        n = await c.policies.index(doc)
        exc = doc.section("exclusion")
        print(
            f"{doc.id}: {len(doc.sections)} sections ({', '.join(s.title for s in doc.sections[:8])}), "
            f"exclusion clauses: {len(exc.clauses) if exc else 0}, {n} chunks indexed"
        )
    finally:
        await c.shutdown()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    ap = argparse.ArgumentParser(prog="python -m app.policies")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="download, parse and index the FEMA SFIP forms")
    a = sub.add_parser("add", help="parse and index your own policy PDF")
    a.add_argument("path")
    a.add_argument("--id", required=True)
    a.add_argument("--title", required=True)
    a.add_argument("--form", required=True)
    a.add_argument("--edition", default="")
    a.add_argument("--url", default="")
    a.add_argument("--licence", default="specimen, demo use only")
    sub.add_parser("compare", help="print the exclusions comparison as JSON")
    args = ap.parse_args()
    if args.cmd == "build":
        asyncio.run(build())
    elif args.cmd == "add":
        asyncio.run(add(args))
    else:
        from app.policies.compare import compare
        from app.policies.service import load_policies

        docs = list(load_policies(Path(get_settings().policies_dir)).values())
        print(json.dumps(compare(docs), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
