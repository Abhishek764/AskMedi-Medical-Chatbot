"""Fixed, reviewed copy for refusals and crisis/emergency cards.

The LLM never writes this text. Helpline numbers must be re-verified by a clinician before
launch and every quarter (see .claude/security-analysis.md, crisis protocol).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

COPY_VERSION = "2026-11-14.1"


@dataclass(frozen=True)
class Helpline:
    name: str
    phone: str
    note: str


CRISIS_LINES: dict[str, list[Helpline]] = {
    "IN": [
        Helpline("Tele-MANAS (mental health, 24x7, free)", "14416", "Also 1-800-891-4416"),
        Helpline("Emergency services", "112", "If you are in immediate danger"),
    ],
    "US": [
        Helpline("988 Suicide & Crisis Lifeline", "988", "Call or text, 24/7"),
        Helpline("Emergency services", "911", "If you are in immediate danger"),
    ],
    "GB": [
        Helpline("Samaritans", "116 123", "24/7, free"),
        Helpline("Emergency services", "999", "If you are in immediate danger"),
    ],
}

EMERGENCY_NUMBERS: dict[str, str] = {"IN": "112", "US": "911", "GB": "999"}

FALLBACK_DIRECTORY = "https://findahelpline.com"


def crisis_payload(country: str) -> dict[str, object]:
    lines = CRISIS_LINES.get(country.upper(), [])
    return {
        "message": (
            "I'm really sorry you're going through this. You deserve support right now, and "
            "I'm not able to give it the way a person can. Please reach out to one of these "
            "free helplines, or to someone you trust. If you might act on these thoughts, "
            "call emergency services now."
        ),
        "helplines": [asdict(h) for h in lines],
        "directory": FALLBACK_DIRECTORY,
        "copy_version": COPY_VERSION,
    }


def emergency_payload(country: str) -> dict[str, object]:
    return {
        "message": (
            "This could be a medical emergency. Call your local emergency number now or go to "
            "the nearest emergency department. Don't wait for an online answer."
        ),
        "number": EMERGENCY_NUMBERS.get(country.upper(), "112"),
        "copy_version": COPY_VERSION,
    }


REFUSALS: dict[str, str] = {
    "out_of_scope": (
        "I can only help with health and medicine questions. Try asking about a condition, "
        'a symptom, or a medicine, for example: "What are the symptoms of dengue?"'
    ),
    "greeting": (
        "Hi! I'm AskMedi. I answer general health and medicine questions using trusted "
        "sources, with citations. What would you like to know?"
    ),
    "injection": "I can't do that. I can help with health and medicine questions.",
    "persona": (
        "I can't take on that role. I'm an information tool, not a therapist, doctor or "
        "companion. If you're struggling, talking to a professional or someone you trust can "
        "really help. I'm happy to answer health questions."
    ),
    "harmful_substance": (
        "I can't advise on that because it could cause serious harm. Please talk to a doctor "
        "or pharmacist before swallowing any non-food chemical, replacing food or medicine, or "
        "stopping a prescribed medicine. If someone has already swallowed something harmful, "
        "call emergency services or a poison centre now."
    ),
    "dosing": (
        "I can't recommend a dose for you or someone else, because the right dose depends on "
        "age, weight, other conditions and medicines. A pharmacist or doctor can tell you "
        "safely. I can explain what a medicine is used for and its common side effects."
    ),
    "diagnosis": (
        "I can't tell whether you have a condition; only a clinician who examines you can. "
        'I can explain a condition in general, for example: "What are the symptoms of '
        'type 2 diabetes?" If symptoms are severe or getting worse, see a doctor soon.'
    ),
    "no_sources": (
        "I don't have reliable information on that in my sources, so I won't guess. "
        "A doctor or pharmacist is the best person to ask."
    ),
    "unverified": (
        "I couldn't verify an answer against my sources, so I won't risk giving you wrong "
        "medical information. A doctor or pharmacist is the best person to ask."
    ),
    "conversation_limit": (
        "This conversation has reached its length limit. Please start a new chat."
    ),
    "elevated_method": (
        "I can't help with that. If you're having thoughts of harming yourself, please contact "
        "one of the helplines shown. You don't have to go through this alone."
    ),
}

DISCLAIMER = (
    "AskMedi gives general health information from cited sources. It is not medical advice, "
    "a diagnosis or a prescription. Always consult a qualified clinician."
)
