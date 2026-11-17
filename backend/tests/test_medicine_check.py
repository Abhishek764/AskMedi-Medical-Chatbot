"""End-to-end: symptom question -> 3 questions -> OTC label medicines, through the API."""

import pytest

from app.rag.chunking import chunk_document
from app.rag.types import Section, SourceDoc
from tests.helpers import register
from tests.test_chat import ask, new_conv, parse_sse


def otc(slug: str, name: str, strength: str, directions: str) -> SourceDoc:
    return SourceDoc(
        doc_id=f"openfda-otc:{slug}",
        source="openfda",
        title=f"{name} — OTC Drug Facts",
        licence="cc0",
        doc_type="label",
        url=f"https://dailymed.example/{slug}",
        sections=[
            Section(["Active ingredient"], strength),
            Section(["Uses"], "temporarily relieves minor aches and pains due to headache"),
            Section(
                ["Ask a doctor before use"], "Ask a doctor before use if you have liver disease"
            ),
            Section(
                ["Stop use and ask a doctor"],
                "Stop use and ask a doctor if pain lasts more than 10 days",
            ),
            Section(["Directions"], directions, dosing=True),
        ],
    )


DOCS = [
    otc(
        "acetaminophen",
        "Acetaminophen",
        "Acetaminophen 500 mg",
        "adults and children 12 years and over: take 2 tablets every 6 hours; do not take more than 6 tablets in 24 hours",
    ),
    otc(
        "ibuprofen",
        "Ibuprofen",
        "Ibuprofen 200 mg (NSAID)",
        "adults and children 12 years and over: take 1 tablet every 4 to 6 hours while symptoms persist",
    ),
    SourceDoc(
        doc_id="medlineplus:headache",
        source="medlineplus",
        title="Headache",
        licence="public-domain",
        doc_type="consumer",
        url="https://medlineplus.gov/headache.html",
        sections=[
            Section(
                ["Summary"],
                "Most headaches are tension headaches caused by stress or tight muscles. "
                "Headache causes include lack of sleep, skipped meals and dehydration.",
            )
        ],
    ),
]


@pytest.fixture
async def indexed(app):
    c = app.state.container
    for doc in DOCS:
        parents, chunks = chunk_document(doc)
        dense = await c.embedder.embed_documents([ch.text for ch in chunks])
        await c.store.upsert(
            parents, chunks, dense, [c.bm25.encode_document(ch.text) for ch in chunks]
        )
    return app


async def answer(client, auth, cid, step, choices):
    r = await client.post(
        f"/v1/conversations/{cid}/messages",
        json={"triage": {"step": step, "choices": choices}},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    return parse_sse(r.text)


def first(events, kind):
    return next(d for e, d in events if e == kind)


async def test_full_check_shows_label_dose_and_removes_unsafe_medicine(indexed, client):
    u = await register(client)
    cid = await new_conv(client, u["auth"])
    ev = await ask(client, u["auth"], cid, "I have a headache, what medicine can I take?")
    q1 = first(ev, "triage")
    assert q1["step"] == 1 and q1["total"] == 3 and "3 quick questions" in q1["intro"]
    assert ev[-1][1]["status"] == "triage"

    q2 = first(await answer(client, u["auth"], cid, 1, ["adult"]), "triage")
    assert q2["step"] == 2 and q2["multi"] is True
    assert any(o["id"] == "thunderclap" for o in q2["options"])
    q3 = first(await answer(client, u["auth"], cid, 2, ["none"]), "triage")
    assert q3["step"] == 3

    final = await answer(client, u["auth"], cid, 3, ["thinners"])
    meds = first(final, "medicines")
    assert [m["name"] for m in meds["items"]] == ["Paracetamol (acetaminophen)"]
    assert "take 2 tablets every 6 hours" in meds["items"][0]["directions"]  # verbatim label dose
    assert meds["items"][0]["active_ingredient"] == "Acetaminophen 500 mg"
    assert {"name": "Ibuprofen", "reason": "you take a blood thinner"} in meds["excluded"]
    assert "FDA" in meds["disclaimer"]
    cites = first(final, "citations")["items"]
    assert {c["doc_id"] for c in cites} >= {"openfda-otc:acetaminophen"}
    assert final[-1][1]["status"] == "complete"

    detail = (await client.get(f"/v1/conversations/{cid}", headers=u["auth"])).json()
    user_msgs = [m["content"] for m in detail["messages"] if m["role"] == "user"]
    assert user_msgs[1:] == [
        "Me, an adult (18–64)",
        "None of these",
        "I take a blood thinner (e.g. warfarin)",
    ]

    # The check is over: another answer is rejected as expired.
    late = await answer(client, u["auth"], cid, 3, ["none"])
    assert first(late, "refusal")["reason"] == "triage_expired"


async def test_dose_question_starts_the_check_instead_of_refusing(indexed, client):
    u = await register(client)
    cid = await new_conv(client, u["auth"])
    ev = await ask(client, u["auth"], cid, "How much paracetamol should I take for my headache?")
    assert first(ev, "triage")["step"] == 1


async def test_child_goes_to_pharmacist(indexed, client):
    u = await register(client)
    cid = await new_conv(client, u["auth"])
    await ask(client, u["auth"], cid, "what medicine for fever")
    await answer(client, u["auth"], cid, 1, ["child"])
    await answer(client, u["auth"], cid, 2, ["none"])
    ev = await answer(client, u["auth"], cid, 3, ["none"])
    assert first(ev, "refusal")["reason"] == "ask_pharmacist"
    assert not any(e == "medicines" for e, _ in ev)


async def test_emergency_sign_shows_emergency_card(indexed, client):
    u = await register(client)
    cid = await new_conv(client, u["auth"])
    await ask(client, u["auth"], cid, "I have a headache, what can I take")
    await answer(client, u["auth"], cid, 1, ["adult"])
    await answer(client, u["auth"], cid, 2, ["thunderclap"])
    ev = await answer(client, u["auth"], cid, 3, ["none"])
    assert first(ev, "emergency")["number"] == "112"


async def test_invalid_choice_repeats_the_question(indexed, client):
    u = await register(client)
    cid = await new_conv(client, u["auth"])
    await ask(client, u["auth"], cid, "which medicine is good for headache")
    q = first(await answer(client, u["auth"], cid, 1, ["made-up"]), "triage")
    assert q["step"] == 1 and q["error"]


async def test_no_medicines_after_a_crisis_turn(indexed, client):
    u = await register(client)
    cid = await new_conv(client, u["auth"])
    await ask(client, u["auth"], cid, "I want to end my life")
    ev = await ask(client, u["auth"], cid, "I have a headache, what medicine can I take?")
    assert first(ev, "refusal")["reason"] == "elevated_medicine"
    assert not any(e == "triage" for e, _ in ev)


async def test_answers_do_not_use_daily_quota(indexed, app, client):
    app.state.container.settings.daily_question_quota = 1
    u = await register(client)
    cid = await new_conv(client, u["auth"])
    await ask(client, u["auth"], cid, "I have a headache, what medicine can I take?")
    await answer(client, u["auth"], cid, 1, ["adult"])
    await answer(client, u["auth"], cid, 2, ["none"])
    final = await answer(client, u["auth"], cid, 3, ["none"])
    assert first(final, "medicines")["items"]


async def test_empty_question_without_answer_is_rejected(client):
    u = await register(client)
    cid = await new_conv(client, u["auth"])
    r = await client.post(
        f"/v1/conversations/{cid}/messages", json={"question": "  "}, headers=u["auth"]
    )
    assert r.status_code == 422
