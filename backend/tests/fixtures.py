"""Tiny corpus for retrieval and pipeline tests (text paraphrased from public-domain
MedlinePlus-style summaries)."""

from app.rag.types import Section, SourceDoc

DOCS = [
    SourceDoc(
        doc_id="medlineplus:asthma",
        source="medlineplus",
        title="Asthma",
        licence="public-domain",
        doc_type="consumer",
        url="https://medlineplus.gov/asthma.html",
        sections=[
            Section(
                ["Summary"],
                "Asthma is a chronic disease that affects the airways in the lungs. "
                "During an asthma attack the airways swell and narrow, making breathing hard.",
            ),
            Section(
                ["Symptoms"],
                "Symptoms of asthma include wheezing, coughing, chest tightness "
                "and shortness of breath. Symptoms often get worse at night or during exercise.",
            ),
            Section(
                ["Treatment"],
                "Asthma is treated with quick-relief inhalers for attacks and "
                "long-term control medicines such as inhaled corticosteroids. An asthma action "
                "plan helps people manage symptoms.",
            ),
        ],
    ),
    SourceDoc(
        doc_id="medlineplus:dengue",
        source="medlineplus",
        title="Dengue",
        licence="public-domain",
        doc_type="consumer",
        url="https://medlineplus.gov/dengue.html",
        sections=[
            Section(
                ["Summary"],
                "Dengue is an infection caused by a virus spread by Aedes mosquitoes. "
                "It is common in tropical areas including India.",
            ),
            Section(
                ["Symptoms"],
                "Symptoms of dengue include high fever, severe headache, pain behind "
                "the eyes, joint and muscle pain, nausea and a rash. Warning signs of severe "
                "dengue include belly pain, persistent vomiting and bleeding gums.",
            ),
        ],
    ),
    SourceDoc(
        doc_id="fda:metformin",
        source="openfda",
        title="Metformin hydrochloride tablets",
        licence="cc0",
        doc_type="label",
        url="https://api.fda.gov/drug/label.json?search=set_id:x",
        sections=[
            Section(
                ["Indications and Usage"],
                "Metformin is indicated as an adjunct to diet and "
                "exercise to improve glycemic control in adults with type 2 diabetes mellitus.",
            ),
            Section(
                ["Adverse Reactions"],
                "The most common adverse reactions of metformin are "
                "diarrhea, nausea, vomiting, flatulence and abdominal discomfort.",
            ),
            Section(
                ["Dosage and Administration"],
                "The usual starting dose of metformin is 500 mg orally twice a day with meals.",
                dosing=True,
            ),
        ],
    ),
    SourceDoc(
        doc_id="bad:nc",
        source="local",
        title="Non-commercial asthma notes",
        licence="cc-by-nc",
        doc_type="consumer",
        sections=[
            Section(["Summary"], "Asthma wheezing coughing notes that must never be served.")
        ],
    ),
]
