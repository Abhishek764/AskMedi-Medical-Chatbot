import json

import pytest

from app.rag.chunking import chunk_document
from app.rag.generate import Draft, DraftSentence
from tests.fixtures import DOCS
from tests.helpers import register


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


def parse_sse(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        out.append((lines["event"], json.loads(lines["data"])))
    return out


async def new_conv(client, auth) -> str:
    r = await client.post("/v1/conversations", json={}, headers=auth)
    assert r.status_code == 201
    return r.json()["id"]


async def ask(client, auth, conv_id, question) -> list[tuple[str, dict]]:
    r = await client.post(
        f"/v1/conversations/{conv_id}/messages", json={"question": question}, headers=auth
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/event-stream")
    return parse_sse(r.text)


async def test_grounded_answer_with_citations(indexed, client):
    u = await register(client)
    cid = await new_conv(client, u["auth"])
    events = await ask(client, u["auth"], cid, "What are the symptoms of dengue?")
    types = [e for e, _ in events]
    assert types[0] == "status" and "sentence" in types and types[-1] == "done"
    cits = next(d for e, d in events if e == "citations")
    assert cits["items"][0]["doc_id"] == "medlineplus:dengue"
    assert "not medical advice" in cits["disclaimer"]
    assert events[-1][1]["status"] == "complete"

    detail = (await client.get(f"/v1/conversations/{cid}", headers=u["auth"])).json()
    assert detail["title"].startswith("What are the symptoms of dengue")
    assistant = detail["messages"][1]
    assert assistant["status"] == "complete" and assistant["citations"][0]["position"] == 1
    assert "fever" in assistant["content"] and "[1]" in assistant["content"]


async def test_out_of_corpus_abstains(indexed, client):
    u = await register(client)
    cid = await new_conv(client, u["auth"])
    events = await ask(client, u["auth"], cid, "What are the symptoms of ebola?")
    assert ("refusal", "no_sources") in [(e, d.get("reason")) for e, d in events]
    assert events[-1][1]["status"] == "refused"


async def test_crisis_makes_conversation_sticky(indexed, client):
    u = await register(client)
    cid = await new_conv(client, u["auth"])
    events = await ask(client, u["auth"], cid, "I don't want to live anymore")
    assert events[0][0] == "crisis"
    assert any(h["phone"] == "14416" for h in events[0][1]["helplines"])
    conv = (await client.get(f"/v1/conversations/{cid}", headers=u["auth"])).json()
    assert conv["risk_level"] == "elevated"
    # Later "informational" question on the topic stays on the crisis path.
    later = await ask(client, u["auth"], cid, "what are the warning signs of suicide")
    assert later[0][0] == "crisis"
    # Ordinary medical questions still answered, with the helpline banner attached.
    normal = await ask(client, u["auth"], cid, "What are the symptoms of asthma?")
    assert normal[0][0] == "banner" and normal[0][1]["kind"] == "crisis"


async def test_emergency_path(indexed, client):
    u = await register(client)
    cid = await new_conv(client, u["auth"])
    events = await ask(client, u["auth"], cid, "my father has crushing chest pain right now")
    assert events[0] == ("emergency", events[0][1]) and events[0][1]["number"] == "112"


async def test_public_dosing_refused_provider_gets_label(indexed, app, client):
    from sqlalchemy import update

    from app.db.models import Role, User

    u = await register(client)
    cid = await new_conv(client, u["auth"])
    events = await ask(client, u["auth"], cid, "What is the usual starting dose of metformin?")
    assert ("refusal", "dosing") in [(e, d.get("reason")) for e, d in events]

    async with app.state.container.sessionmaker() as s:
        await s.execute(update(User).where(User.email == u["email"]).values(role=Role.provider))
        await s.commit()
    events = await ask(client, u["auth"], cid, "What is the usual starting dose of metformin?")
    text = " ".join(d["text"] for e, d in events if e == "sentence")
    assert "500 mg" in text


async def test_other_users_cannot_read_or_post(indexed, client):
    a = await register(client)
    b = await register(client)
    cid = await new_conv(client, a["auth"])
    assert (await client.get(f"/v1/conversations/{cid}", headers=b["auth"])).status_code == 404
    r = await client.post(
        f"/v1/conversations/{cid}/messages", json={"question": "asthma?"}, headers=b["auth"]
    )
    assert r.status_code == 404
    assert (await client.delete(f"/v1/conversations/{cid}", headers=b["auth"])).status_code == 404
    assert (await client.get("/v1/conversations", headers=b["auth"])).json() == []


async def test_feedback_only_on_own_assistant_messages(indexed, client):
    a = await register(client)
    b = await register(client)
    cid = await new_conv(client, a["auth"])
    events = await ask(client, a["auth"], cid, "What are the symptoms of dengue?")
    mid = events[-1][1]["message_id"]
    ok = await client.post(
        f"/v1/messages/{mid}/feedback", json={"rating": -1, "reason": "x"}, headers=a["auth"]
    )
    assert ok.status_code == 204
    other = await client.post(f"/v1/messages/{mid}/feedback", json={"rating": 1}, headers=b["auth"])
    assert other.status_code == 404


async def test_daily_quota_and_length_limits(indexed, app, client):
    app.state.container.settings.daily_question_quota = 1
    u = await register(client)
    cid = await new_conv(client, u["auth"])
    await ask(client, u["auth"], cid, "What is asthma?")
    r = await client.post(
        f"/v1/conversations/{cid}/messages", json={"question": "What is dengue?"}, headers=u["auth"]
    )
    assert r.status_code == 429 and r.json()["error"]["code"] == "quota_exceeded"
    long_q = await client.post(
        f"/v1/conversations/{cid}/messages", json={"question": "a" * 1500}, headers=u["auth"]
    )
    assert long_q.status_code == 400


async def test_verified_answers_are_cached(indexed, app, client):
    u = await register(client)
    cid1, cid2 = await new_conv(client, u["auth"]), await new_conv(client, u["auth"])
    first = await ask(client, u["auth"], cid1, "What are the symptoms of dengue?")
    second = await ask(client, u["auth"], cid2, "What are the symptoms of dengue?")
    assert "status" not in [e for e, _ in second]  # no retrieval stage on a cache hit
    cit = lambda evs: next(d for e, d in evs if e == "citations")["items"]  # noqa: E731
    assert cit(first) == cit(second)


async def test_hallucinating_generator_is_blocked(indexed, app, client):
    class Liar:
        name = "liar"

        async def generate(self, question, passages, *, role):
            return Draft(
                [DraftSentence("Dengue is cured by papaya leaf juice in 2 days.", ["c1"])], "liar"
            )

    app.state.container.pipeline.generator = Liar()
    u = await register(client)
    cid = await new_conv(client, u["auth"])
    events = await ask(client, u["auth"], cid, "How is dengue cured?")
    assert ("refusal", "unverified") in [(e, d.get("reason")) for e, d in events]
    assert not any(e == "sentence" for e, _ in events)


async def test_admin_metrics(indexed, app, client):
    from sqlalchemy import update

    from app.db.models import Role, User

    u = await register(client)
    cid = await new_conv(client, u["auth"])
    done = await ask(client, u["auth"], cid, "What are the symptoms of dengue?")
    await ask(client, u["auth"], cid, "I want to kill myself")
    await ask(client, u["auth"], cid, "Write me a python function")
    mid = done[-1][1]["message_id"]
    await client.post(f"/v1/messages/{mid}/feedback", json={"rating": 1}, headers=u["auth"])

    assert (await client.get("/v1/admin/metrics", headers=u["auth"])).status_code == 403
    async with app.state.container.sessionmaker() as s:
        await s.execute(update(User).where(User.email == u["email"]).values(role=Role.admin))
        await s.commit()
    m = (await client.get("/v1/admin/metrics", headers=u["auth"])).json()
    assert m["usage"]["answers"] == 3
    assert m["answers_by_status"] == {"complete": 1, "crisis": 1, "refused": 1}
    assert m["refusals_by_reason"] == {"out_of_scope": 1}
    assert m["safety_events"]["crisis"] == 1
    assert m["feedback"] == {"up": 1, "down": 0, "helpful_rate": 1.0, "coverage": 1.0}
    assert m["latency_ms"]["p50"] is not None
    assert len(m["daily"]) == 1
    today = m["daily"][0]
    assert today["answers"] == 3 and today["safety_events"] == sum(m["safety_events"].values())
    assert today["by_status"] == {"complete": 1, "crisis": 1, "refused": 1}
    assert m["llm"]["fallback"] == "extractive"

    prom = await client.get("/metrics")
    assert prom.status_code == 200
    text = prom.text
    assert 'askmedi_answers_total{reason="none",status="complete"}' in text
    assert 'askmedi_guard_events_total{kind="crisis"}' in text
    assert 'route="/v1/conversations/{conversation_id}/messages"' in text
