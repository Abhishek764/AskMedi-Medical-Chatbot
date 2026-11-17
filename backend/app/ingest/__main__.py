"""Corpus CLI. Run from backend/.

    uv run python -m app.ingest run                      # download (cached) + index, seed lists
    uv run python -m app.ingest run --sources medlineplus --limit 10
    uv run python -m app.ingest run --sources pmc --papers-per-topic 5 --no-pdf
    uv run python -m app.ingest export                   # parsed corpus -> ../data/corpus/
    uv run python -m app.ingest load                     # rebuild the index from ../data/corpus/ offline
    uv run python -m app.ingest pdf ../data/Medical_book.pdf --title "..." --licence cc-by
    uv run python -m app.ingest stats

Raw downloads (XML, JSON, PDFs) are cached in RAW_DATA_DIR (default ../data/raw).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.container import Container
from app.db.models import Document
from app.ingest import seeds
from app.ingest.corpus_file import read_corpus, write_corpus
from app.ingest.pipeline import Ingestor, IngestReport
from app.ingest.sources import (
    Fetcher,
    fetch_medlineplus,
    fetch_medlineplus_bulk,
    fetch_openfda,
    fetch_pmc,
    local_pdf_doc,
    search_pmc,
)
from app.rag.types import SourceDoc

log = logging.getLogger("askmedi.ingest")


async def collect_docs(
    fetcher: Fetcher, args: argparse.Namespace
) -> AsyncIterator[tuple[str, SourceDoc | None, str]]:
    """Yield (label, doc or None, status) for every seed item of the selected sources."""
    sources = set(args.sources.split(","))
    if "medlineplus_all" in sources:
        try:
            for doc in await fetch_medlineplus_bulk(fetcher):
                yield f"medlineplus  {doc.title}", doc, "ok"
        except Exception as exc:
            log.warning("medlineplus bulk failed: %s", type(exc).__name__)
            yield "medlineplus  bulk", None, "fetch_error"
    if "medlineplus" in sources:
        for topic in seeds.parse(seeds.CONDITIONS)[: args.limit]:
            try:
                doc = await fetch_medlineplus(fetcher, topic)
                yield f"medlineplus  {topic}", doc, "ok" if doc else "not_found"
            except Exception as exc:  # keep going; report it
                log.warning("medlineplus %s failed: %s", topic, type(exc).__name__)
                yield f"medlineplus  {topic}", None, "fetch_error"
    if "openfda" in sources:
        for generic in seeds.parse(seeds.MEDICINES)[: args.limit]:
            try:
                doc = await fetch_openfda(fetcher, generic)
                yield f"openfda      {generic}", doc, "ok" if doc else "not_found"
            except Exception as exc:
                log.warning("openfda %s failed: %s", generic, type(exc).__name__)
                yield f"openfda      {generic}", None, "fetch_error"
    if "pmc" in sources:
        for topic in seeds.parse(seeds.PAPER_TOPICS)[: args.limit]:
            try:
                ids = await search_pmc(
                    fetcher, topic, limit=args.papers_per_topic, since_year=args.since
                )
            except Exception as exc:
                log.warning("pmc search %s failed: %s", topic, type(exc).__name__)
                yield f"pmc          {topic}", None, "fetch_error"
                continue
            for pmcid in ids:
                try:
                    doc, status = await fetch_pmc(fetcher, pmcid, download_pdf=not args.no_pdf)
                    yield f"pmc          {topic} {pmcid}", doc, status.split(":")[0]
                except Exception as exc:
                    log.warning("pmc %s failed: %s", pmcid, type(exc).__name__)
                    yield f"pmc          {topic} {pmcid}", None, "fetch_error"


def _ingestor(container: Container) -> Ingestor:
    return Ingestor(
        container.store,
        container.embedder,
        container.bm25,
        container.sessionmaker,
        corpus_version=container.settings.qdrant_collection,
    )


async def _run(args: argparse.Namespace) -> IngestReport:
    settings = get_settings()
    container = Container(settings)
    await container.startup()
    fetcher = Fetcher(Path(settings.raw_data_dir))
    ingestor = _ingestor(container)
    report = IngestReport()
    try:
        async for label, doc, status in collect_docs(fetcher, args):
            if doc:
                await ingestor.ingest([doc], report)
            else:
                report.rejected[status] += 1
            print(f"{label:<48} {_short(report)}")
    finally:
        await fetcher.aclose()
        await container.shutdown()
    return report


async def _export(args: argparse.Namespace) -> dict[str, object]:
    """Parse cached raw files (downloading only what is missing) into the corpus snapshot."""
    settings = get_settings()
    fetcher = Fetcher(Path(settings.raw_data_dir))
    docs: dict[str, SourceDoc] = {}
    skipped: dict[str, int] = {}
    try:
        async for _label, doc, status in collect_docs(fetcher, args):
            if doc:
                docs.setdefault(doc.doc_id, doc)
            else:
                skipped[status] = skipped.get(status, 0) + 1
    finally:
        await fetcher.aclose()
    out = Path(args.out)
    n = write_corpus(docs.values(), out / "corpus-v1.jsonl", out / "manifest.csv")
    return {"written": n, "skipped": skipped, "dir": args.out}


async def _load(args: argparse.Namespace) -> IngestReport:
    container = Container(get_settings())
    await container.startup()
    try:
        report = IngestReport()
        ingestor = _ingestor(container)
        for doc in read_corpus(Path(args.path)):
            await ingestor.ingest([doc], report)
        return report
    finally:
        await container.shutdown()


async def _pdf(args: argparse.Namespace) -> IngestReport:
    container = Container(get_settings())
    await container.startup()
    try:
        doc = local_pdf_doc(Path(args.path), title=args.title, licence=args.licence)
        return await _ingestor(container).ingest([doc])
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


def _source_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--sources", default="medlineplus_all,openfda,pmc")
    p.add_argument("--limit", type=int, default=1000, help="max seed items per source")
    p.add_argument("--papers-per-topic", type=int, default=3)
    p.add_argument("--since", type=int, default=2016)
    p.add_argument("--no-pdf", action="store_true", help="skip PDF downloads for PMC papers")


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    ap = argparse.ArgumentParser(prog="python -m app.ingest")
    sub = ap.add_subparsers(dest="cmd", required=True)
    _source_args(sub.add_parser("run", help="fetch (cached) and index public sources"))
    export = sub.add_parser("export", help="write the parsed corpus snapshot (JSONL + manifest)")
    _source_args(export)
    export.add_argument("--out", default="../data/corpus")
    load = sub.add_parser("load", help="index a corpus snapshot without network access")
    load.add_argument("path", nargs="?", default="../data/corpus/corpus-v1.jsonl")
    pdf = sub.add_parser("pdf", help="ingest a local PDF (licence must be declared)")
    pdf.add_argument("path")
    pdf.add_argument("--title", required=True)
    pdf.add_argument("--licence", required=True, help="e.g. cc-by, cc0, public-domain")
    sub.add_parser("stats", help="corpus counts")
    args = ap.parse_args()

    runners = {"run": _run, "export": _export, "load": _load, "pdf": _pdf}
    result = asyncio.run(runners[args.cmd](args)) if args.cmd in runners else asyncio.run(_stats())
    print(json.dumps(result.as_dict() if isinstance(result, IngestReport) else result, indent=2))


if __name__ == "__main__":
    main()
