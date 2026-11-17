"""Medicine check: three fixed questions, then a rule-based outcome.

Nothing here calls a model. The questions, red flags and exclusions are reviewable code; the
doses shown afterwards are read verbatim from OTC labels (see app/triage/compose.py).

Outcomes, checked in this order:
1. Any emergency warning sign  -> emergency card.
2. A child, or pregnant / breastfeeding -> ask a pharmacist or doctor (no medicine shown).
3. Any other warning sign, or symptoms past the self-care window -> see a doctor.
4. Otherwise -> the symptom's medicines minus those excluded by the answers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.triage.symptoms import (
    ACETAMINOPHEN,
    BY_KEY,
    LONG,
    MEDICINE_NAMES,
    NSAIDS,
    PSEUDOEPHEDRINE,
    Symptom,
)

TOTAL_STEPS = 3
NONE = "none"


@dataclass(frozen=True)
class Option:
    id: str
    label: str


@dataclass(frozen=True)
class Question:
    step: int
    text: str
    options: tuple[Option, ...]
    multi: bool

    def as_event(self) -> dict[str, object]:
        return {
            "step": self.step,
            "total": TOTAL_STEPS,
            "question": self.text,
            "options": [{"id": o.id, "label": o.label} for o in self.options],
            "multi": self.multi,
        }


WHO = Question(
    1,
    "Who is this for?",
    (
        Option("adult", "Me, an adult (18–64)"),
        Option("older", "Me, 65 or older"),
        Option("pregnant", "Me, and I'm pregnant or breastfeeding"),
        Option("child", "A child (under 18)"),
    ),
    multi=False,
)

CONDITIONS = (
    Option("liver", "Liver disease, or 3+ alcoholic drinks a day"),
    Option("kidney", "Kidney disease"),
    Option("stomach", "Stomach ulcer or bleeding problems"),
    Option("heart", "Heart disease or high blood pressure"),
    Option("asthma", "Asthma"),
    Option("thinners", "I take a blood thinner (e.g. warfarin)"),
    Option("other_meds", "I take other regular medicines"),
    Option("allergy", "Allergy to a pain reliever"),
    Option(NONE, "None of these"),
)
HEALTH = Question(3, "Do any of these apply to you?", CONDITIONS, multi=True)

# Answer id -> medicines that must not be shown, with the reason shown instead.
EXCLUSIONS: dict[str, tuple[frozenset[str], str]] = {
    "liver": (frozenset({ACETAMINOPHEN}), "you have liver disease or drink alcohol daily"),
    "kidney": (NSAIDS, "you have kidney disease"),
    "stomach": (NSAIDS, "you have a stomach ulcer or bleeding problem"),
    "heart": (NSAIDS | {PSEUDOEPHEDRINE}, "you have heart disease or high blood pressure"),
    "asthma": (NSAIDS, "you have asthma"),
    "thinners": (NSAIDS, "you take a blood thinner"),
    "allergy": (NSAIDS | {ACETAMINOPHEN}, "you are allergic to a pain reliever"),
    "older": (NSAIDS, "people 65 and older have a higher risk of stomach bleeding"),
}


def red_flag_question(symptom: Symptom) -> Question:
    opts = [Option(f.id, f.label) for f in symptom.red_flags]
    opts.append(Option(LONG.id, LONG.label.format(days=symptom.max_days)))
    opts.append(Option(NONE, "None of these"))
    return Question(2, "Do you have any of these?", tuple(opts), multi=True)


@dataclass
class TriageState:
    symptom: str
    step: int = 1  # the question currently waiting for an answer
    answers: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {"symptom": self.symptom, "step": self.step, "answers": self.answers}

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> TriageState | None:
        try:
            symptom = str(data["symptom"])
            step = int(data["step"])  # type: ignore[call-overload]
            answers = {str(k): [str(x) for x in v] for k, v in dict(data["answers"]).items()}  # type: ignore[call-overload]
        except (KeyError, TypeError, ValueError):
            return None
        if symptom not in BY_KEY or not 1 <= step <= TOTAL_STEPS:
            return None
        return cls(symptom, step, answers)


def question_for(state: TriageState) -> Question:
    if state.step == 1:
        return WHO
    if state.step == 2:
        return red_flag_question(BY_KEY[state.symptom])
    return HEALTH


class InvalidAnswer(ValueError):
    pass


def apply_answer(state: TriageState, step: int, choices: list[str]) -> TriageState:
    """Validate choices against the question's own option ids; advance one step."""
    if step != state.step:
        raise InvalidAnswer("That question has already been answered.")
    q = question_for(state)
    valid = {o.id for o in q.options}
    picked = list(dict.fromkeys(choices))
    if not picked or any(c not in valid for c in picked):
        raise InvalidAnswer("Please choose one of the options.")
    if not q.multi and len(picked) != 1:
        raise InvalidAnswer("Please choose one option.")
    if NONE in picked and len(picked) > 1:
        picked = [c for c in picked if c != NONE]
    answers = {**state.answers, str(step): picked}
    return TriageState(state.symptom, step + 1, answers)


@dataclass(frozen=True)
class Outcome:
    kind: str  # emergency | pharmacist | doctor | medicines
    symptom: Symptom
    medicines: tuple[str, ...] = ()
    excluded: tuple[tuple[str, str], ...] = ()  # (medicine, reason)
    reasons: tuple[str, ...] = ()
    check_interactions: bool = False


def decide(state: TriageState) -> Outcome:
    symptom = BY_KEY[state.symptom]
    who = (state.answers.get("1") or [""])[0]
    flags = [f for f in state.answers.get("2", []) if f != NONE]
    health = [h for h in state.answers.get("3", []) if h != NONE]

    flag_by_id = {f.id: f for f in symptom.red_flags}
    emergency = [
        flag_by_id[f].label for f in flags if f in flag_by_id and flag_by_id[f].level == "emergency"
    ]
    if emergency:
        return Outcome("emergency", symptom, reasons=tuple(emergency))
    if who in ("child", "pregnant"):
        why = "for a child" if who == "child" else "during pregnancy or breastfeeding"
        return Outcome(
            "pharmacist",
            symptom,
            reasons=(f"Medicine choice and dose {why} need a pharmacist or doctor.",),
        )
    doctor = [
        flag_by_id[f].label if f in flag_by_id else LONG.label.format(days=symptom.max_days)
        for f in flags
    ]
    if doctor:
        return Outcome("doctor", symptom, reasons=tuple(doctor))

    excluded: dict[str, str] = {}
    for key in [*health, who]:
        if key in EXCLUSIONS:
            meds, reason = EXCLUSIONS[key]
            for m in meds:
                excluded.setdefault(m, reason)
    allowed = tuple(m for m in symptom.medicines if m not in excluded)
    shown_excluded = tuple((m, excluded[m]) for m in symptom.medicines if m in excluded)
    if not allowed:
        return Outcome(
            "pharmacist",
            symptom,
            excluded=shown_excluded,
            reasons=(
                "None of the usual non-prescription options is safe to suggest with your answers.",
            ),
        )
    return Outcome(
        "medicines",
        symptom,
        medicines=allowed,
        excluded=shown_excluded,
        check_interactions="other_meds" in health,
    )


def medicine_name(slug: str) -> str:
    return MEDICINE_NAMES.get(slug, slug)
