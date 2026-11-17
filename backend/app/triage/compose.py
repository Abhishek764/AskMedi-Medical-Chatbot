"""Turn a medicine-check step into events for the chat stream.

Questions and outcomes are fixed text. Medicine details are copied from each medicine's OTC
"Drug Facts" label as stored in the index (doc id openfda-otc:<slug>); nothing is generated,
so a dose can only ever be the label's own words.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.guards.resources import emergency_payload
from app.rag.generate import ExtractiveGenerator
from app.rag.query import plan_query
from app.rag.retriever import HybridRetriever
from app.rag.store import VectorStore
from app.triage.engine import (
    TOTAL_STEPS,
    InvalidAnswer,
    Outcome,
    TriageState,
    apply_answer,
    decide,
    medicine_name,
    question_for,
)
from app.triage.symptoms import MEDICINE_INTENT, Symptom, find_symptom

LABEL_DISCLAIMER = (
    "Medicine details are copied from each product's US FDA 'Drug Facts' label. This is not a "
    "prescription. Strengths differ between brands and countries: follow the label on the pack "
    "you buy, and ask a pharmacist if you are unsure."
)

INTRO = (
    "I can suggest common non-prescription medicines for {label}. First, 3 quick questions "
    "so I only show what is safe for you."
)

DOCTOR = (
    "Based on your answers, please see a doctor rather than treating this yourself, "
    "because of: {reasons}. A doctor can find the cause and the right treatment."
)
PHARMACIST = "{reason} Please ask a pharmacist or doctor before taking anything for {label}."
NOT_IN_ELEVATED = (
    "I can't suggest medicines in this conversation. If you're going through a hard time, "
    "please reach out to one of the helplines shown. For medicine questions, a pharmacist can help."
)

LABEL_FIELDS = (
    ("active_ingredient", "Active ingredient"),
    ("uses", "Uses"),
    ("directions", "Directions"),
    ("do_not_use", "Do not use"),
    ("ask_doctor", "Ask a doctor before use"),
    ("ask_pharmacist", "Ask a doctor or pharmacist before use"),
    ("stop_use", "Stop use and ask a doctor"),
    ("pregnancy", "Pregnancy or breast-feeding"),
)


@dataclass
class StepResult:
    events: list[tuple[str, dict[str, object]]]
    status: str  # triage | complete | refused | emergency
    content: str
    reason: str | None = None
    state: TriageState | None = None  # None ends the check
    citations: list[dict[str, object]] | None = None


def detect(text: str) -> Symptom | None:
    """A request for medicine for one of the covered symptoms."""
    return find_symptom(text) if MEDICINE_INTENT.search(text) else None


def start(symptom: Symptom, *, elevated_risk: bool) -> StepResult:
    if elevated_risk:  # no medicines or doses in a conversation flagged for self-harm risk
        return StepResult(
            [("refusal", {"reason": "elevated_medicine", "message": NOT_IN_ELEVATED})],
            "refused",
            NOT_IN_ELEVATED,
            "elevated_medicine",
        )
    state = TriageState(symptom.key)
    intro = INTRO.format(label=symptom.label)
    q = question_for(state)
    return StepResult(
        [("triage", {"intro": intro, **q.as_event()})],
        "triage",
        f"{intro}\n\n{q.text}",
        state=state,
    )


class MedicineCheck:
    def __init__(self, store: VectorStore, retriever: HybridRetriever) -> None:
        self.store = store
        self.retriever = retriever
        self.extractive = ExtractiveGenerator(max_sentences=2)

    async def answer(
        self, state: TriageState, step: int, choices: list[str], country: str
    ) -> StepResult:
        try:
            nxt = apply_answer(state, step, choices)
        except InvalidAnswer as exc:
            q = question_for(state)
            return StepResult(
                [("triage", {"error": str(exc), **q.as_event()})], "triage", q.text, state=state
            )
        if nxt.step <= TOTAL_STEPS:
            q = question_for(nxt)
            return StepResult([("triage", q.as_event())], "triage", q.text, state=nxt)
        return await self.outcome(decide(nxt), country)

    async def outcome(self, out: Outcome, country: str) -> StepResult:
        label = out.symptom.label
        if out.kind == "emergency":
            payload = emergency_payload(country)
            return StepResult(
                [("emergency", payload)], "emergency", str(payload["message"]), "triage_emergency"
            )
        if out.kind == "doctor":
            msg = DOCTOR.format(reasons="; ".join(r.lower() for r in out.reasons))
            return StepResult(
                [("refusal", {"reason": "see_doctor", "message": msg})],
                "refused",
                msg,
                "see_doctor",
            )
        if out.kind == "pharmacist":
            msg = PHARMACIST.format(reason=" ".join(out.reasons), label=label)
            if out.excluded:
                msg += " " + _excluded_text(out.excluded)
            return StepResult(
                [("refusal", {"reason": "ask_pharmacist", "message": msg})],
                "refused",
                msg,
                "ask_pharmacist",
            )
        return await self._medicines(out)

    async def _medicines(self, out: Outcome) -> StepResult:
        citations: list[dict[str, object]] = []
        events: list[tuple[str, dict[str, object]]] = []
        lines: list[str] = []

        # 1. Possible causes, from MedlinePlus (cited; never a diagnosis).
        plan = plan_query(out.symptom.info_query)
        found = await self.retriever.retrieve(plan, allow_dosing=False)
        consumer = [p for p in found.passages if p.payload.get("source") == "medlineplus"][:2]
        if consumer:
            draft = await self.extractive.generate(out.symptom.info_query, consumer, role="public")
            for s in draft.sentences:
                idx = int(s.refs[0][1:]) - 1 if s.refs else -1
                if not 0 <= idx < len(consumer):
                    continue
                pos = _cite(
                    citations, consumer[idx].chunk_id, consumer[idx].doc_id, consumer[idx].payload
                )
                events.append(("sentence", {"text": s.text, "citations": [pos]}))
                lines.append(f"{s.text} [{pos}]")
        for note in out.symptom.notes:
            events.append(("sentence", {"text": note, "citations": []}))
            lines.append(note)

        # 2. Medicine cards, verbatim from OTC labels.
        cards = []
        for slug in out.medicines:
            sections, meta = await self.store.doc_sections(f"openfda-otc:{slug}")
            if not sections or meta is None or "Directions" not in sections:
                continue
            pos = _cite(citations, str(meta["chunk_id"]), f"openfda-otc:{slug}", meta)
            card = {"name": medicine_name(slug), "citation": pos}
            for key, heading in LABEL_FIELDS:
                if sections.get(heading):
                    card[key] = sections[heading]
            cards.append(card)
            lines.append(f"{card['name']} [{pos}]: {card.get('directions', '')}")
        if not cards:
            msg = PHARMACIST.format(
                reason="I couldn't load the medicine labels right now.", label=out.symptom.label
            )
            return StepResult(
                [("refusal", {"reason": "ask_pharmacist", "message": msg})],
                "refused",
                msg,
                "ask_pharmacist",
            )

        excluded = [{"name": medicine_name(m), "reason": r} for m, r in out.excluded]
        events.append(
            (
                "medicines",
                {
                    "symptom": out.symptom.label,
                    "items": cards,
                    "excluded": excluded,
                    "check_interactions": out.check_interactions,
                    "see_doctor_if": f"Your symptoms last more than {out.symptom.max_days} days, get worse, or new symptoms appear.",
                    "disclaimer": LABEL_DISCLAIMER,
                },
            )
        )
        events.append(("citations", {"items": citations, "disclaimer": LABEL_DISCLAIMER}))
        if out.excluded:
            lines.append(_excluded_text(out.excluded))
        if out.check_interactions:
            lines.append(
                "You take other regular medicines: ask a pharmacist to check for interactions first."
            )
        return StepResult(events, "complete", "\n\n".join(lines), citations=citations)


def _cite(
    citations: list[dict[str, object]], chunk_id: str, doc_id: str, payload: dict[str, object]
) -> int:
    for c in citations:
        if c["doc_id"] == doc_id:
            return int(c["position"])  # type: ignore[call-overload]
    pos = len(citations) + 1
    citations.append(
        {
            "position": pos,
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "title": str(payload.get("title", "")),
            "section": payload.get("section"),
            "source": str(payload.get("source", "")),
            "url": payload.get("url"),
            "score": 1.0,
        }
    )
    return pos


def _excluded_text(excluded: tuple[tuple[str, str], ...]) -> str:
    return " ".join(f"{medicine_name(m)} is not shown because {r}." for m, r in excluded)
