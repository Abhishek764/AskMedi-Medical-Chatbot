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

from app.core import tracing
from app.core.kv import KV
from app.core.metrics import timed
from app.guards.input_guard import Action, check_input
from app.guards.nemo import Rails
from app.guards.resources import DISCLAIMER, REFUSALS, crisis_payload, emergency_payload
from app.rag.generate import Generator
from app.rag.query import plan_query
from app.rag.retriever import HybridRetriever
from app.rag.verify import verify
from app.triage.compose import MedicineCheck, StepResult, detect, start
from app.triage.engine import TriageState

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
    triage: dict[str, object] | None = None  # medicine-check state stored for this conversation
    triage_answer: tuple[int, list[str]] | None = None  # (step, option ids) when answering it


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
    triage_state: dict[str, object] | None = None  # None ends any medicine check in progress


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
        medicine: MedicineCheck | None = None,
        rails: Rails | None = None,
    ) -> None:
        self.medicine = medicine
        self.rails = rails  # NeMo Guardrails (optional second layer)
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
        """Run one turn, traced (Logfire / LangSmith) when tracing is configured."""
        tr = tracing.start_answer(
            {
                "question": tracing.text(question)
                if ctx.triage_answer is None
                else "(medicine check)"
            },
            {"role": ctx.role, "history_turns": len(history), "elevated_risk": ctx.elevated_risk},
        )
        rec: AnswerRecord | None = None
        try:
            async for ev in self._answer_stream(question, history, ctx, tr):
                if ev.type == "result":
                    rec = ev.data["record"]  # type: ignore[assignment]
                yield ev
        finally:
            if rec is None:
                tr.end(status="aborted")
            else:
                tr.end(
                    status=rec.status,
                    reason=rec.refusal_reason,
                    model=rec.model,
                    citations=len(rec.citations),
                    latency_ms=rec.latency_ms,
                    cached=rec.cached,
                    answer=tracing.text(rec.content),
                )

    async def _answer_stream(
        self, question: str, history: list[str], ctx: UserContext, tr: tracing.AnswerTrace
    ) -> AsyncIterator[Event]:
        t0 = time.perf_counter()

        def done(rec: AnswerRecord) -> Event:
            rec.latency_ms = int((time.perf_counter() - t0) * 1000)
            return Event("result", {"record": rec})

        if ctx.triage_answer is not None:
            state = TriageState.from_dict(ctx.triage) if ctx.triage else None
            if state is None or self.medicine is None:
                msg = "That medicine check has expired. Please ask your question again."
                yield Event("refusal", {"reason": "triage_expired", "message": msg})
                yield done(AnswerRecord("refused", msg, "triage_expired"))
                return
            if ctx.elevated_risk:
                res = start(_symptom(state), elevated_risk=True)
            else:
                step, choices = ctx.triage_answer
                with tr.step("medicine_check", step=step, choices=list(choices)) as st:
                    res = await self.medicine.answer(state, step, choices, ctx.country)
                    st.set(status=res.status)
            for ev in _step_events(res):
                yield ev
            yield done(_step_record(res))
            return

        with tr.step("input_guard") as st:
            decision = check_input(question, role=ctx.role, elevated_risk=ctx.elevated_risk)
            st.set(
                action=decision.action.value,
                reason=decision.reason,
                flags=sorted(decision.flags),
                pii=list(decision.pii_kinds),
            )

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
        symptom = detect(decision.redacted_text) if self.medicine is not None else None
        if symptom is not None and (
            decision.action == Action.allow
            or decision.reason in ("dosing", "diagnosis", "prescription")
        ):
            res = start(symptom, elevated_risk=ctx.elevated_risk)
            for ev in _step_events(res):
                yield ev
            yield done(_step_record(res))
            return

        if decision.action == Action.refuse:
            reason = decision.reason
            if ctx.elevated_risk and reason in ("harmful_substance", "dosing"):
                reason = "elevated_method"
            msg = REFUSALS[reason]
            yield Event("refusal", {"reason": reason, "message": msg})
            yield done(AnswerRecord("refused", msg, reason, guard_kind=reason))
            return

        if self.rails is not None:
            with tr.step("nemo_input_rail") as st:
                verdict = await self.rails.check_input(decision.redacted_text)
                st.set(blocked=verdict.blocked, rail=verdict.rail, error=verdict.error)
            if verdict.blocked:
                msg = REFUSALS["rail_input"]
                yield Event("refusal", {"reason": "rail_input", "message": msg})
                yield done(AnswerRecord("refused", msg, "rail_input", guard_kind="rail_input"))
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
        with timed("retrieve"), tr.step("retrieve", run_type="retriever") as st:
            result = await self.retriever.retrieve(plan, allow_dosing=allow_dosing)
            st.set(
                top_score=round(result.top_score, 4),
                candidates=result.candidates,
                doc_ids=[p.doc_id for p in result.passages],
                abstain=not result.passages or result.top_score < self.abstain_threshold,
            )
        if not result.passages or result.top_score < self.abstain_threshold:
            msg = REFUSALS["no_sources"]
            yield Event("refusal", {"reason": "no_sources", "message": msg})
            yield done(AnswerRecord("refused", msg, "no_sources"))
            return

        yield Event("status", {"stage": "checking sources"})
        with timed("generate"), tr.step("generate", passages=len(result.passages)) as st:
            draft = await self.generator.generate(plan.standalone, result.passages, role=ctx.role)
            st.set(
                model=draft.model,
                sentences=len(draft.sentences),
                insufficient=draft.insufficient,
                notes=list(draft.notes),
                tokens_in=draft.tokens_in,
                tokens_out=draft.tokens_out,
            )
        with timed("verify"), tr.step("verify") as st:
            checked = verify(
                draft, result.passages, role=ctx.role, threshold=self.groundedness_threshold
            )
            st.set(ok=checked.ok, reason=checked.reason, dropped=checked.dropped)
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
        if self.rails is not None:
            with tr.step("nemo_output_rail") as st:
                verdict = await self.rails.check_output(decision.redacted_text, content)
                st.set(blocked=verdict.blocked, rail=verdict.rail, error=verdict.error)
            if verdict.blocked:
                msg = REFUSALS["rail_output"]
                yield Event("refusal", {"reason": "rail_output", "message": msg})
                yield done(
                    AnswerRecord(
                        "refused",
                        msg,
                        "rail_output",
                        model=draft.model,
                        tokens_in=draft.tokens_in,
                        tokens_out=draft.tokens_out,
                        guard_kind="rail_output",
                    )
                )
                return

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


def _symptom(state: TriageState):  # noqa: ANN202
    from app.triage.symptoms import BY_KEY

    return BY_KEY[state.symptom]


def _step_events(res: StepResult) -> list[Event]:
    return [Event(t, d) for t, d in res.events]


def _step_record(res: StepResult) -> AnswerRecord:
    return AnswerRecord(
        res.status,
        res.content,
        res.reason,
        citations=[CitationRecord(**c) for c in (res.citations or [])],  # type: ignore[arg-type]
        model="medicine-check" if res.status in ("triage", "complete") else None,
        guard_kind="emergency" if res.status == "emergency" else None,
        triage_state=res.state.to_dict() if res.state else None,
    )


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
