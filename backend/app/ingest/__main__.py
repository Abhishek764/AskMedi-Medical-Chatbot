"""Corpus CLI.

    uv run python -m app.ingest run                      # all sources, seed lists
    uv run python -m app.ingest run --sources medlineplus --limit 10
    uv run python -m app.ingest run --sources pmc --papers-per-topic 5 --no-pdf
    uv run python -m app.ingest pdf ../data/Medical_book.pdf --title "..." --licence cc-by
    uv run python -m app.ingest stats

Raw downloads (XML, JSON, PDFs) are cached in RAW_DATA_DIR (default ./data/raw).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.container import Container
from app.db.models import Document
from app.ingest import seeds
from app.ingest.pipeline import Ingestor, IngestReport
from app.ingest.sources import (
    Fetcher,
    fetch_medlineplus,
    fetch_openfda,
    fetch_pmc,
    local_pdf_doc,
    search_pmc,
)

log = logging.getLogger("askmedi.ingest")


async def _run(args: argparse.Namespace) -> IngestReport:
    settings = get_settings()
    container = Container(settings)
    await container.startup()
    fetcher = Fetcher(Path(settings.raw_data_dir))
    ingestor = Ingestor(
        container.store,
        container.embedder,
        container.bm25,
        container.sessionmaker,
        corpus_version=settings.qdrant_collection,
    )
    report = IngestReport()
    sources = set(args.sources.split(","))
    try:
        if "medlineplus" in sources:
            for topic in seeds.parse(seeds.CONDITIONS)[: args.limit]:
                try:
                    doc = await fetch_medlineplus(fetcher, topic)
                except Exception as exc:  # keep going; report it
                    log.warning("medlineplus %s failed: %s", topic, type(exc).__name__)
                    report.rejected["fetch_error"] += 1
                    continue
                if doc:
                    await ingestor.ingest([doc], report)
                else:
                    report.rejected["not_found"] += 1
                print(f"medlineplus  {topic:<35} {_short(report)}")
        if "openfda" in sources:
            for generic in seeds.parse(seeds.MEDICINES)[: args.limit]:
                try:
                    doc = await fetch_openfda(fetcher, generic)
                except Exception as exc:
                    log.warning("openfda %s failed: %s", generic, type(exc).__name__)
                    report.rejected["fetch_error"] += 1
                    continue
                if doc:
                    await ingestor.ingest([doc], report)
                else:
                    report.rejected["not_found"] += 1
                print(f"openfda      {generic:<35} {_short(report)}")
        if "pmc" in sources:
            for topic in seeds.parse(seeds.PAPER_TOPICS)[: args.limit]:
                try:
                    ids = await search_pmc(
                        fetcher, topic, limit=args.papers_per_topic, since_year=args.since
                    )
                except Exception as exc:
                    log.warning("pmc search %s failed: %s", topic, type(exc).__name__)
                    report.rejected["fetch_error"] += 1
                    continue
                for pmcid in ids:
                    try:
                        doc, status = await fetch_pmc(fetcher, pmcid, download_pdf=not args.no_pdf)
                    except Exception as exc:
                        log.warning("pmc %s failed: %s", pmcid, type(exc).__name__)
                        report.rejected["fetch_error"] += 1
                        continue
                    if doc:
                        await ingestor.ingest([doc], report)
                    else:
                        report.rejected[status.split(":")[0]] += 1
                print(f"pmc          {topic:<35} {_short(report)}")
    finally:
        await fetcher.aclose()
        await container.shutdown()
    return report


async def _pdf(args: argparse.Namespace) -> IngestReport:
    settings = get_settings()
    container = Container(settings)
    await container.startup()
    try:
        ingestor = Ingestor(
            container.store,
            container.embedder,
            container.bm25,
            container.sessionmaker,
            corpus_version=settings.qdrant_collection,
        )
        doc = local_pdf_doc(Path(args.path), title=args.title, licence=args.licence)
        return await ingestor.ingest([doc])
    finally:
        await container.shutdown()


async def _stats() -> dict[str, object]:
    settings = get_settings()
    container = Container(settings)
    await container.startup()
    try:
        async with container.sessionmaker() as s:
            rows = (
                await s.execute(
                    select(
                        Document.source,
                        Document.doc_type,
                        func.count(),
                        func.sum(Document.chunk_count),
                    ).group_by(Document.source, Document.doc_type)
                )
            ).all()
        return {
            "collection": settings.qdrant_collection,
            "vectors": await container.store.count(),
            "documents": [
                {"source": r[0], "doc_type": r[1], "docs": r[2], "chunks": int(r[3] or 0)}
                for r in rows
            ],
        }
    finally:
        await container.shutdown()


def _short(r: IngestReport) -> str:
    return f"added={r.added} updated={r.updated} unchanged={r.unchanged} chunks={r.chunks} rejected={sum(r.rejected.values())}"


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    ap = argparse.ArgumentParser(prog="python -m app.ingest")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="fetch and ingest from public sources")
    run.add_argument("--sources", default="medlineplus,openfda,pmc")
    run.add_argument("--limit", type=int, default=1000, help="max seed items per source")
    run.add_argument("--papers-per-topic", type=int, default=10)
    run.add_argument("--since", type=int, default=2016)
    run.add_argument("--no-pdf", action="store_true", help="skip PDF downloads for PMC papers")
    pdf = sub.add_parser("pdf", help="ingest a local PDF (licence must be declared)")
    pdf.add_argument("path")
    pdf.add_argument("--title", required=True)
    pdf.add_argument("--licence", required=True, help="e.g. cc-by, cc0, public-domain")
    sub.add_parser("stats", help="corpus counts")
    args = ap.parse_args()

    if args.cmd == "run":
        print(json.dumps(asyncio.run(_run(args)).as_dict(), indent=2))
    elif args.cmd == "pdf":
        print(json.dumps(asyncio.run(_pdf(args)).as_dict(), indent=2))
    else:
        print(json.dumps(asyncio.run(_stats()), indent=2))


if __name__ == "__main__":
    main()
