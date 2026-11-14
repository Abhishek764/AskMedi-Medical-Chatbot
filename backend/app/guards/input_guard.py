"""Input guard: decides, before any retrieval or LLM call, what happens to a message.

Order matters. Crisis and emergency are checked first and win over everything, including
injection attempts and out-of-scope text, because missing them is the worst failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.guards import rules
from app.guards.pii import redact
from app.guards.text import any_match, variants


class Action(StrEnum):
    allow = "allow"
    crisis = "crisis"
    emergency = "emergency"
    refuse = "refuse"


@dataclass(frozen=True)
class InputDecision:
    action: Action
    reason: str  # refusal key, or the triggering rule family
    redacted_text: str
    pii_kinds: tuple[str, ...] = ()
    flags: frozenset[str] = field(default_factory=frozenset)  # e.g. crisis_topic, dosing

    @property
    def raises_risk(self) -> bool:
        return self.action == Action.crisis


def check_input(text: str, *, role: str = "public", elevated_risk: bool = False) -> InputDecision:
    red = redact(text)
    forms = variants(red.text)
    flags: set[str] = set()

    def decide(action: Action, reason: str) -> InputDecision:
        return InputDecision(action, reason, red.text, red.kinds, frozenset(flags))

    # 1. Crisis: means/lethality always; first-person risk; fiction-framed risk.
    method = any_match(rules.CRISIS_METHOD, forms)
    first_person = any_match(rules.CRISIS_FIRST_PERSON, forms)
    topic = any_match(rules.CRISIS_TOPIC, forms)
    fiction = any_match(rules.FICTION_FRAMING, forms)
    if method or first_person or (topic and fiction):
        return decide(Action.crisis, "crisis_method" if method else "crisis")
    if topic:
        flags.add("crisis_topic")
        if elevated_risk:
            return decide(Action.crisis, "crisis_followup")

    # 2. Medical emergency happening now.
    if any_match(rules.EMERGENCY, forms):
        return decide(Action.emergency, "emergency")
    if any_match(rules.EMERGENCY_TOPIC, forms):
        flags.add("emergency_topic")

    # 3. Manipulation of the assistant.
    if any_match(rules.INJECTION, forms):
        return decide(Action.refuse, "injection")
    if any_match(rules.PERSONA, forms):
        return decide(Action.refuse, "persona")

    # 4. Physical-harm advice.
    if any_match(rules.HARMFUL_SUBSTANCE, forms):
        return decide(Action.refuse, "harmful_substance")

    # 5. Scope: must look medical.
    plain = forms[0]
    if any_match(rules.GREETING, [plain]):
        return decide(Action.refuse, "greeting")
    medical = any_match(rules.MEDICAL_TERMS, forms)
    if not medical or (any_match(rules.OFF_TOPIC, forms) and not _strongly_medical(forms)):
        return decide(Action.refuse, "out_of_scope")

    # 6. Personal diagnosis and dosing.
    if any_match(rules.DIAGNOSIS, forms):
        return decide(Action.refuse, "diagnosis")
    if any_match(rules.DOSING, forms):
        flags.add("dosing")
        if role not in ("provider", "admin"):
            return decide(Action.refuse, "dosing")

    if elevated_risk:
        flags.add("elevated_risk")
    return decide(Action.allow, "ok")


def _strongly_medical(forms: list[str]) -> bool:
    hits = sum(1 for p in rules.MEDICAL_TERMS for t in forms[:1] if p.search(t))
    return hits >= 2
