"""Faithful offline replica of the v1 RAG pipeline.

Same loader (src.helper.load_pdf_file), same splitter (500/20), same embedding
model (all-MiniLM-L6-v2), cosine similarity, k=3 — but the vector index is a
local numpy matrix instead of Pinecone, so retrieval can be measured without
API keys. Page numbers are kept internally for scoring only (v1 itself drops
them, so users never see them).

v2 should expose the same interface:
    build() -> stats dict
    retrieve(question, k) -> list[{"text", "page", "source", "score"}]
    answer(question, history) -> dict  (needs OPENAI_API_KEY)
"""
import hashlib
import time

import numpy as np

from evals.common import CACHE, ROOT, rss_mb

K_DEFAULT = 3  # v1 retriever: search_kwargs={"k": 3}

_state = {}


def _pdf_fingerprint():
    h = hashlib.sha256()
    for p in sorted((ROOT / "data").glob("*.pdf")):
        h.update(p.name.encode())
        h.update(str(p.stat().st_size).encode())
    return h.hexdigest()[:12]


def build():
    """Load PDF, chunk, embed (cached). Returns timing/size stats."""
    if _state:
        return _state["stats"]
    stats = {"rss_mb_before": rss_mb()}

    t0 = time.perf_counter()
    from src.helper import (
        download_hugging_face_embeddings,
        load_pdf_file,
        text_split,
    )

    stats["import_s"] = round(time.perf_counter() - t0, 2)

    t0 = time.perf_counter()
    emb = download_hugging_face_embeddings()
    stats["model_load_s"] = round(time.perf_counter() - t0, 2)
    stats["rss_mb_after_model"] = rss_mb()

    t0 = time.perf_counter()
    pages = load_pdf_file(data=str(ROOT / "data") + "/")
    stats["pdf_load_s"] = round(time.perf_counter() - t0, 2)
    stats["pages"] = len(pages)
    stats["documents"] = len({(p.metadata or {}).get("source") for p in pages})

    t0 = time.perf_counter()
    chunks = text_split(pages)  # metadata (incl. page) is carried through
    stats["split_s"] = round(time.perf_counter() - t0, 2)
    lens = [len(c.page_content) for c in chunks]
    stats["chunks"] = len(chunks)
    stats["chunk_chars_mean"] = round(float(np.mean(lens)), 1)
    stats["chunk_chars_min"] = int(min(lens))
    stats["empty_or_tiny_chunks_lt50"] = int(sum(1 for n in lens if n < 50))

    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE / f"v1_vectors_{_pdf_fingerprint()}_{len(chunks)}.npy"
    t0 = time.perf_counter()
    if cache_file.exists():
        vecs = np.load(cache_file)
        stats["embed_cached"] = True
    else:
        vecs = np.asarray(
            emb.embed_documents([c.page_content for c in chunks]), dtype=np.float32
        )
        np.save(cache_file, vecs)
        stats["embed_cached"] = False
    stats["embed_s"] = round(time.perf_counter() - t0, 2)
    stats["embed_dim"] = int(vecs.shape[1])
    stats["rss_mb_after_index"] = rss_mb()

    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12
    _state.update(emb=emb, chunks=chunks, vecs=vecs, stats=stats)
    return stats


def retrieve(question: str, k: int = K_DEFAULT):
    build()
    q = np.asarray(_state["emb"].embed_query(question), dtype=np.float32)
    q /= np.linalg.norm(q) + 1e-12
    scores = _state["vecs"] @ q
    top = np.argsort(-scores)[:k]
    out = []
    for i in top:
        c = _state["chunks"][int(i)]
        md = c.metadata or {}
        out.append(
            {
                "text": c.page_content,
                "page": md.get("page"),
                "source": md.get("source"),
                "score": float(scores[int(i)]),
            }
        )
    return out


def answer(question: str, history=None, model=None):
    """v1 generation: (optional) history rewrite -> top-3 -> gpt-4o, streamed.

    Mirrors app/chat/rag.py prompts and settings. Returns answer text, the
    contexts used, latency (time-to-first-token, total) and token usage.
    """
    import os

    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    from src.prompt import contextualize_q_prompt, system_prompt

    model = model or os.environ.get("OPENAI_MODEL", "gpt-4o")
    llm = ChatOpenAI(model=model, temperature=0, stream_usage=True)
    history = history or []
    lc_hist = [
        HumanMessage(content=m["content"]) if m["role"] == "user"
        else AIMessage(content=m["content"])
        for m in history
    ]

    t_start = time.perf_counter()
    usage = {"input_tokens": 0, "output_tokens": 0}
    standalone = question
    if lc_hist:  # create_history_aware_retriever only rewrites when history exists
        msg = llm.invoke(
            [SystemMessage(content=contextualize_q_prompt), *lc_hist,
             HumanMessage(content=question)]
        )
        standalone = msg.content
        um = getattr(msg, "usage_metadata", None) or {}
        usage["input_tokens"] += um.get("input_tokens", 0)
        usage["output_tokens"] += um.get("output_tokens", 0)

    ctx = retrieve(standalone, K_DEFAULT)
    context_text = "\n\n".join(c["text"] for c in ctx)
    messages = [
        SystemMessage(content=system_prompt.replace("{context}", context_text)),
        *lc_hist,
        HumanMessage(content=question),
    ]
    ttft = None
    parts = []
    for chunk in llm.stream(messages):
        if chunk.content and ttft is None:
            ttft = time.perf_counter() - t_start
        parts.append(chunk.content or "")
        um = getattr(chunk, "usage_metadata", None)
        if um:
            usage["input_tokens"] += um.get("input_tokens", 0)
            usage["output_tokens"] += um.get("output_tokens", 0)
    total = time.perf_counter() - t_start
    return {
        "answer": "".join(parts).strip(),
        "standalone_question": standalone,
        "contexts": ctx,
        "ttft_s": ttft,
        "total_s": total,
        "usage": usage,
        "model": model,
    }
