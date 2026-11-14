"""The answer pipeline: the single boundary between the web layer and the AI.

    answer_stream(question, history, ctx) -> async iterator of Event

Order: input guard → query plan → hybrid retrieval → abstain gate → generate → verify →
stream. The final event is always `result`, which the API layer persists and then turns
into `done`. Nothing here touches HTTP or the database, so it is tested with fakes.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field

from app.core.kv import KV
from app.guards.input_guard import Action, check_input
from app.guards.resources import DISCLAIMER, REFUSALS, crisis_payload, emergency_payload
from app.rag.generate import Generator
from app.rag.query import plan_query
from app.rag.retriever import HybridRetriever
from app.rag.verify import verify

logger = logging.getLogger("askmedi.pipeline")


@dataclass
class Event:
    type: str
    data: dict[str, object]


@dataclass
class UserContext:
    role: str = "public"
    elevated_risk: bool = False
    country: str = "IN"


@dataclass
class CitationRecord:
    position: int
    chunk_id: str
    doc_id: str
    title: str
    section: str | None
    source: str
    url: str | None
    score: float


@dataclass
class AnswerRecord:
    status: str  # complete | refused | crisis | emergency | error
    content: str
    refusal_reason: str | None = None
    citations: list[CitationRecord] = field(default_factory=list)
    model: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    raise_risk: bool = False
    guard_kind: str | None = None
    cached: bool = False


class AnswerPipeline:
    def __init__(
        self,
        retriever: HybridRetriever,
        generator: Generator,
        *,
        abstain_threshold: float,
        groundedness_threshold: float = 0.5,
        kv: KV | None = None,
        cache_ttl_seconds: int = 86400,
        corpus_tag: str = "corpus-v1",
    ) -> None:
        self.retriever = retriever
        self.generator = generator
        self.abstain_threshold = abstain_threshold
        self.groundedness_threshold = groundedness_threshold
        self.kv = kv
        self.cache_ttl = cache_ttl_seconds
        self.corpus_tag = corpus_tag

    async def answer_stream(
        self, question: str, history: list[str], ctx: UserContext
    ) -> AsyncIterator[Event]:
        t0 = time.perf_counter()

        def done(rec: AnswerRecord) -> Event:
            rec.latency_ms = int((time.perf_counter() - t0) * 1000)
            return Event("result", {"record": rec})

        decision = check_input(question, role=ctx.role, elevated_risk=ctx.elevated_risk)

        if decision.action == Action.crisis:
            payload = crisis_payload(ctx.country)
            yield Event("crisis", payload)
            yield done(
                AnswerRecord(
                    "crisis",
                    str(payload["message"]),
                    decision.reason,
                    raise_risk=True,
                    guard_kind=decision.reason,
                )
            )
            return
        if decision.action == Action.emergency:
            payload = emergency_payload(ctx.country)
            yield Event("emergency", payload)
            yield done(
                AnswerRecord(
                    "emergency", str(payload["message"]), decision.reason, guard_kind="emergency"
                )
            )
            return
        if decision.action == Action.refuse:
            reason = decision.reason
            if ctx.elevated_risk and reason in ("harmful_substance", "dosing"):
                reason = "elevated_method"
            msg = REFUSALS[reason]
            yield Event("refusal", {"reason": reason, "message": msg})
            yield done(AnswerRecord("refused", msg, reason, guard_kind=reason))
            return

        banners: list[Event] = []
        if "crisis_topic" in decision.flags or ctx.elevated_risk:
            banners.append(Event("banner", {"kind": "crisis", **crisis_payload(ctx.country)}))
        if "emergency_topic" in decision.flags:
            banners.append(Event("banner", {"kind": "emergency", **emergency_payload(ctx.country)}))
        for b in banners:
            yield b

        plan = plan_query(decision.redacted_text, history)

        cache_key = self._cache_key(plan.normalised, ctx.role) if not history else None
        if cache_key and self.kv is not None:
            cached = await self.kv.get(cache_key)
            if cached:
                rec = _record_from_cache(cached)
                for ev in _answer_events(rec):
                    yield ev
                yield done(rec)
                return

        yield Event("status", {"stage": "retrieving"})
        allow_dosing = ctx.role in ("provider", "admin")
        result = await self.retriever.retrieve(plan, allow_dosing=allow_dosing)
        if not result.passages or result.top_score < self.abstain_threshold:
            msg = REFUSALS["no_sources"]
            yield Event("refusal", {"reason": "no_sources", "message": msg})
            yield done(AnswerRecord("refused", msg, "no_sources"))
            return

        yield Event("status", {"stage": "checking sources"})
        draft = await self.generator.generate(plan.standalone, result.passages, role=ctx.role)
        checked = verify(
            draft, result.passages, role=ctx.role, threshold=self.groundedness_threshold
        )
        if not checked.ok:
            reason = checked.reason or "unverified"
            msg = REFUSALS.get(reason, REFUSALS["unverified"])
            logger.info(
                "answer withheld",
                extra={
                    "extra_fields": {
                        "reason": reason,
                        "dropped": checked.dropped,
                        "model": draft.model,
                    }
                },
            )
            yield Event("refusal", {"reason": reason, "message": msg})
            yield done(
                AnswerRecord(
                    "refused",
                    msg,
                    reason,
                    model=draft.model,
                    tokens_in=draft.tokens_in,
                    tokens_out=draft.tokens_out,
                )
            )
            return

        # Renumber citations to the passages actually used, in order of first use.
        used: dict[int, int] = {}
        for s in checked.sentences:
            for c in s.citations:
                used.setdefault(c, len(used) + 1)
        citations = [
            CitationRecord(
                position=pos,
                chunk_id=result.passages[idx].chunk_id,
                doc_id=result.passages[idx].doc_id,
                title=str(result.passages[idx].payload.get("title", "")),
                section=_opt(result.passages[idx].payload.get("section")),
                source=str(result.passages[idx].payload.get("source", "")),
                url=_opt(result.passages[idx].payload.get("url")),
                score=round(result.passages[idx].score, 4),
            )
            for idx, pos in used.items()
        ]
        content = (
            " ".join(
                f"{s.text} " + "".join(f"[{used[c]}]" for c in s.citations)
                for s in checked.sentences
            )
            .replace("  ", " ")
            .strip()
        )
        rec = AnswerRecord(
            "complete",
            content,
            citations=citations,
            model=draft.model,
            tokens_in=draft.tokens_in,
            tokens_out=draft.tokens_out,
        )
        for ev in _answer_events(
            rec, [(s.text, [used[c] for c in s.citations]) for s in checked.sentences]
        ):
            yield ev
        if cache_key and self.kv is not None and ctx.role == "public":
            await self.kv.set(cache_key, _record_to_cache(rec), self.cache_ttl)
        yield done(rec)

    def _cache_key(self, normalised: str, role: str) -> str:
        h = hashlib.sha256(f"{self.corpus_tag}|{role}|{normalised}".encode()).hexdigest()
        return f"ans:{h}"


def _opt(v: object) -> str | None:
    return None if v is None else str(v)


def _answer_events(rec: AnswerRecord, sentences: list[tuple[str, list[int]]] | None = None):
    if sentences is None:
        sentences = [(rec.content, [c.position for c in rec.citations])]
    for text, cites in sentences:
        yield Event("sentence", {"text": text, "citations": cites})
    yield Event(
        "citations", {"items": [asdict(c) for c in rec.citations], "disclaimer": DISCLAIMER}
    )


def _record_to_cache(rec: AnswerRecord) -> str:
    return json.dumps(
        {
            "content": rec.content,
            "model": rec.model,
            "citations": [asdict(c) for c in rec.citations],
        }
    )


def _record_from_cache(raw: str) -> AnswerRecord:
    data = json.loads(raw)
    return AnswerRecord(
        "complete",
        data["content"],
        citations=[CitationRecord(**c) for c in data["citations"]],
        model=data.get("model"),
        cached=True,
    )
