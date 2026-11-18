"""Hand-written hard retrieval questions: lay words, abbreviations, Indian brand names and
symptom descriptions that never use the document's title. Templated questions repeat the
title, which makes dense search look perfect; these show what hybrid search and query
normalisation are for.

    uv run python scripts/build_hard_golden.py     # -> ../evals/golden/v2_hard.jsonl

Drug questions accept any label of that drug (Rx label or OTC Drug Facts).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data" / "corpus" / "manifest.csv"
OUT = ROOT / "evals" / "golden" / "v2_hard.jsonl"

CONSUMER = [
    ("what causes high bp", ["high-blood-pressure"]),
    ("signs of sugar disease in adults", ["diabetes-type-2", "diabetes"]),
    ("warning signs of a heart attack in women", ["heart-attack"]),
    ("why does acid come up my throat at night", ["gerd", "heartburn"]),
    ("sneezing and runny nose every spring", ["hay-fever"]),
    ("how is TB spread", ["tuberculosis"]),
    ("breakbone fever symptoms", ["dengue"]),
    ("mosquito disease with chills and shivering", ["malaria"]),
    ("burning when peeing and need to pee often", ["urinary-tract-infections"]),
    ("sharp pain in my side from stones", ["kidney-stones"]),
    ("wear and tear arthritis in the knees", ["osteoarthritis"]),
    ("underactive thyroid tiredness and weight gain", ["hypothyroidism"]),
    ("low hemoglobin causes", ["anemia", "iron"]),
    ("one-sided throbbing headache with nausea and light sensitivity", ["migraine"]),
    ("wheezing and tight chest triggered by dust", ["asthma"]),
    ("smoker's lung disease that makes you breathless", ["copd"]),
    (
        "stomach cramps with loose motions some days and constipation on others",
        ["irritable-bowel-syndrome"],
    ),
    ("red scaly patches on elbows and knees", ["psoriasis"]),
    ("lung infection with fever and cough with phlegm", ["pneumonia"]),
    ("face drooping and arm weakness suddenly", ["stroke"]),
    ("irregular heartbeat afib", ["atrial-fibrillation"]),
    ("sunshine vitamin deficiency", ["vitamin-d"]),
    ("itchy blisters all over a child's body", ["chickenpox"]),
    ("painful band of rash on one side of the body", ["shingles"]),
    ("big toe joint suddenly red, hot and swollen at night", ["gout"]),
    ("blocked nose and pain around the cheeks and forehead", ["sinusitis"]),
    ("hep B how do you get it", ["hepatitis-b"]),
    ("feeling low and lost interest in everything for weeks", ["depression"]),
    ("can't fall asleep at night", ["insomnia"]),
    ("pimples on the face in teenagers", ["acne"]),
    ("runny nose, sore throat and sneezing from a virus", ["common-cold"]),
    ("who should get the seasonal influenza shot", ["flu"]),
    (
        "irregular periods, extra facial hair and cysts on the ovaries",
        ["polycystic-ovary-syndrome"],
    ),
    ("health risks of a BMI over 30", ["obesity"]),
    ("swollen ankles and breathless lying flat, weak heart pumping", ["heart-failure"]),
]

DRUGS = [
    ("side effects of crocin", "acetaminophen"),
    ("is dolo 650 safe with alcohol", "acetaminophen"),
    ("glycomet stomach upset", "metformin"),
    ("lipitor muscle pain", "atorvastatin"),
    ("bp tablet amlodipine ankle swelling", "amlodipine"),
    ("omez how long can I take it", "omeprazole"),
    ("brufen should it be taken with food", "ibuprofen"),
    ("asthalin inhaler makes my hands shake", "albuterol"),
    ("thyronorm should I take it on an empty stomach", "levothyroxine"),
    ("augmentin causing loose motions", "amoxicillin and clavulanate"),
    ("does zyrtec make you drowsy", "cetirizine"),
    ("losar side effects dizziness", "losartan"),
]


def main() -> None:
    with MANIFEST.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    ids = {r["doc_id"] for r in rows}
    out = []
    for q, slugs in CONSUMER:
        docs = [f"medlineplus:{s}" for s in slugs if f"medlineplus:{s}" in ids]
        if docs:
            out.append({"question": q, "expect_docs": docs, "slice": "consumer_hard"})
    for q, generic in DRUGS:
        docs = [
            r["doc_id"]
            for r in rows
            if r["source"] == "openfda" and r["title"].lower().startswith(generic)
        ]
        if docs:
            out.append({"question": q, "expect_docs": docs, "slice": "drug_hard"})
    with OUT.open("w", encoding="utf-8", newline="\n") as f:
        for i, r in enumerate(out, 1):
            f.write(
                json.dumps({"id": f"v2h{i:03d}", **r, "source": "handwritten", "reviewed": False})
                + "\n"
            )
    print(f"wrote {len(out)} rows to {OUT}")


if __name__ == "__main__":
    main()
