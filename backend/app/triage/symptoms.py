"""Symptoms the medicine check covers, the warning signs that stop it, and which
non-prescription medicines it may show.

Clinical review required before launch: every red flag, exclusion and mapping here is a
safety rule. Change them only with a clinician, and add a test row for each change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Medicines are keyed by OTC label slug (openfda-otc:<slug>, see app/ingest/seeds.py).
ACETAMINOPHEN = "acetaminophen"
IBUPROFEN = "ibuprofen"
NAPROXEN = "naproxen-sodium"
CETIRIZINE = "cetirizine-hydrochloride"
LORATADINE = "loratadine"
FEXOFENADINE = "fexofenadine-hydrochloride"
FAMOTIDINE = "famotidine"
OMEPRAZOLE = "omeprazole-magnesium"
CALCIUM_CARBONATE = "calcium-carbonate"
LOPERAMIDE = "loperamide-hydrochloride"
PEG = "polyethylene-glycol-3350"
DOCUSATE = "docusate-sodium"
SENNA = "sennosides"
DEXTROMETHORPHAN = "dextromethorphan-hydrobromide"
GUAIFENESIN = "guaifenesin"
PSEUDOEPHEDRINE = "pseudoephedrine-hydrochloride"

NSAIDS = frozenset({IBUPROFEN, NAPROXEN})

MEDICINE_NAMES: dict[str, str] = {
    ACETAMINOPHEN: "Paracetamol (acetaminophen)",
    IBUPROFEN: "Ibuprofen",
    NAPROXEN: "Naproxen sodium",
    CETIRIZINE: "Cetirizine",
    LORATADINE: "Loratadine",
    FEXOFENADINE: "Fexofenadine",
    FAMOTIDINE: "Famotidine",
    OMEPRAZOLE: "Omeprazole",
    CALCIUM_CARBONATE: "Calcium carbonate (antacid)",
    LOPERAMIDE: "Loperamide",
    PEG: "Polyethylene glycol 3350",
    DOCUSATE: "Docusate sodium",
    SENNA: "Senna (sennosides)",
    DEXTROMETHORPHAN: "Dextromethorphan",
    GUAIFENESIN: "Guaifenesin",
    PSEUDOEPHEDRINE: "Pseudoephedrine",
}


@dataclass(frozen=True)
class RedFlag:
    id: str
    label: str
    level: str  # "emergency": call now · "doctor": see a doctor soon


@dataclass(frozen=True)
class Symptom:
    key: str
    label: str
    pattern: re.Pattern[str]
    medicines: tuple[str, ...]
    red_flags: tuple[RedFlag, ...]
    info_query: str  # what to look up in MedlinePlus for "what might be causing it"
    max_days: int  # self-care window before seeing a doctor
    notes: tuple[str, ...] = field(default_factory=tuple)


def _p(words: str) -> re.Pattern[str]:
    return re.compile(rf"\b({words})\b", re.I)


LONG = RedFlag("long", "Symptoms for more than {days} days, or getting worse", "doctor")

SYMPTOMS: tuple[Symptom, ...] = (
    Symptom(
        "headache",
        "headache",
        _p(r"headaches?|head ?ache|head is (hurting|aching|pounding)|migraines?|sir ?dard"),
        (ACETAMINOPHEN, IBUPROFEN, NAPROXEN),
        (
            RedFlag("thunderclap", "Sudden, very severe headache (the worst ever)", "emergency"),
            RedFlag(
                "neuro", "Weakness, numbness, confusion, trouble speaking or seeing", "emergency"
            ),
            RedFlag(
                "stiff_neck", "Fever with a stiff neck or a rash that doesn't fade", "emergency"
            ),
            RedFlag("injury", "Headache after a head injury", "doctor"),
        ),
        "headache causes",
        3,
    ),
    Symptom(
        "fever",
        "fever",
        _p(r"fever|feverish|high temperature|bukhar"),
        (ACETAMINOPHEN, IBUPROFEN),
        (
            RedFlag("breathing", "Trouble breathing or chest pain", "emergency"),
            RedFlag(
                "stiff_neck", "Stiff neck, a rash that doesn't fade, or confusion", "emergency"
            ),
            RedFlag("very_high", "Temperature of 39.4°C (103°F) or higher", "doctor"),
            RedFlag("travel", "Recent travel to an area with malaria or dengue", "doctor"),
        ),
        "fever",
        3,
    ),
    Symptom(
        "pain",
        "body, muscle or back pain",
        _p(
            r"body ?(aches?|pain)|muscle (aches?|pain|cramps?)|back ?(ache|pain)|toothache|joint pain|sprain"
        ),
        (ACETAMINOPHEN, IBUPROFEN, NAPROXEN),
        (
            RedFlag("chest", "Pain in the chest, arm or jaw", "emergency"),
            RedFlag(
                "numb",
                "Back pain with numbness in the legs or loss of bladder or bowel control",
                "emergency",
            ),
            RedFlag(
                "injury",
                "Pain after a fall or injury, or a joint that is red, hot and swollen",
                "doctor",
            ),
        ),
        "back pain",
        10,
    ),
    Symptom(
        "period_pain",
        "period pain",
        _p(r"period (pain|cramps?)|menstrual (pain|cramps?)|cramps during (my )?period"),
        (IBUPROFEN, NAPROXEN, ACETAMINOPHEN),
        (
            RedFlag(
                "heavy", "Very heavy bleeding (soaking a pad every hour) or fainting", "emergency"
            ),
            RedFlag("new_severe", "New or severe pelvic pain, or pain with fever", "doctor"),
        ),
        "menstruation",
        3,
    ),
    Symptom(
        "sore_throat",
        "sore throat",
        _p(r"sore throat|throat (pain|is sore)|painful (to )?swallow"),
        (ACETAMINOPHEN, IBUPROFEN),
        (
            RedFlag("airway", "Trouble breathing, drooling or can't swallow saliva", "emergency"),
            RedFlag("high_fever", "High fever or white patches on the tonsils", "doctor"),
        ),
        "sore throat",
        7,
    ),
    Symptom(
        "cold",
        "cold or blocked nose",
        _p(
            r"common cold|a cold|blocked nose|stuffy nose|nasal congestion|runny nose|sinus (pressure|congestion)|zukam"
        ),
        (ACETAMINOPHEN, PSEUDOEPHEDRINE),
        (
            RedFlag("breathing", "Trouble breathing or chest pain", "emergency"),
            RedFlag("high_fever", "Fever above 38.5°C (101.3°F) or face pain with fever", "doctor"),
        ),
        "common cold",
        10,
    ),
    Symptom(
        "cough",
        "cough",
        _p(r"cough(ing)?|khansi"),
        (DEXTROMETHORPHAN, GUAIFENESIN),
        (
            RedFlag("blood", "Coughing up blood", "emergency"),
            RedFlag("breathing", "Trouble breathing, wheezing or chest pain", "emergency"),
            RedFlag("tb", "Cough for 3 weeks or more, weight loss or night sweats", "doctor"),
        ),
        "cough",
        7,
    ),
    Symptom(
        "heartburn",
        "heartburn or acidity",
        _p(r"heartburn|acidity|acid reflux|indigestion|gas ?tric|burning in (my )?(chest|stomach)"),
        (FAMOTIDINE, CALCIUM_CARBONATE, OMEPRAZOLE),
        (
            RedFlag(
                "chest",
                "Chest pain spreading to the arm, neck or jaw, or with sweating",
                "emergency",
            ),
            RedFlag("bleed", "Vomiting blood or black, tarry stools", "emergency"),
            RedFlag("swallow", "Trouble swallowing or unexplained weight loss", "doctor"),
        ),
        "heartburn",
        14,
    ),
    Symptom(
        "allergy",
        "allergy symptoms (sneezing, itchy eyes)",
        _p(r"allerg(y|ies|ic rhinitis)|hay ?fever|sneez(e|ing)|itchy (eyes|nose)|watery eyes"),
        (CETIRIZINE, LORATADINE, FEXOFENADINE),
        (
            RedFlag(
                "anaphylaxis",
                "Swelling of the lips, tongue or throat, or trouble breathing",
                "emergency",
            ),
            RedFlag("hives_spread", "Hives spreading over the body", "doctor"),
        ),
        "hay fever",
        14,
    ),
    Symptom(
        "diarrhea",
        "diarrhoea",
        _p(r"diarrh(o)?ea|loose motions?|loose stools?|dast"),
        (LOPERAMIDE,),
        (
            RedFlag(
                "dehydration",
                "Very little urine, dizziness when standing, or very dry mouth",
                "emergency",
            ),
            RedFlag("blood", "Blood or black colour in the stool", "doctor"),
            RedFlag("fever", "Fever or severe belly pain", "doctor"),
        ),
        "diarrhea",
        2,
        ("Drink plenty of fluids; oral rehydration salts help replace what is lost.",),
    ),
    Symptom(
        "constipation",
        "constipation",
        _p(r"constipat(ed|ion)|can'?t poop|hard stools?|no bowel movement"),
        (PEG, DOCUSATE, SENNA),
        (
            RedFlag(
                "obstruction", "Severe belly pain, vomiting, or unable to pass gas", "emergency"
            ),
            RedFlag("blood", "Blood in the stool or unexplained weight loss", "doctor"),
        ),
        "constipation",
        7,
    ),
)

BY_KEY = {s.key: s for s in SYMPTOMS}

# Asking for something to take, or describing one's own symptom.
MEDICINE_INTENT = re.compile(
    r"\b(what|which|any|best|good)\b.{0,30}\b(medicine|medication|tablet|pill|drug|remedy|treatment|syrup)s?\b"
    r"|\b(medicine|medication|tablet|pill|remedy|something|anything)\b.{0,15}\bfor\b"
    r"|\b(can|should|could) i take\b|\bwhat (can|should) i (take|use)\b|\bwhat helps\b|\bhow (do|can) i (treat|get rid of|relieve|cure)\b"
    r"|\b(i have|i've got|i am having|i'm having|suffering from|i got)\b"
    r"|\bdawai\b|\bkya (lu|lena|le)\b",
    re.I,
)


def find_symptom(text: str) -> Symptom | None:
    for s in SYMPTOMS:
        if s.pattern.search(text):
            return s
    return None
