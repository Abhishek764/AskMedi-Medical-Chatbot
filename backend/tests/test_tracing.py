"""Step tracing: the trace tree each answer produces, and that content stays off by default."""

from __future__ import annotations

import json

import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.core import tracing
from app.rag.llm import GeminiChat
from tests.helpers import register
from tests.test_chat import ask, indexed, new_conv  # noqa: F401 - fixture reused

QUESTION = "What are the symptoms of dengue?"

_exporter = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(_exporter))
otel_trace.set_tracer_provider(_provider)


class FakeLangSmith:
    """Records what RunTree.post would send to LangSmith."""

    def __init__(self) -> None:
        self.runs: list[dict] = []

    def create_run(self, **kw):  # noqa: ANN003, ANN201
        self.runs.append(kw)

    def update_run(self, *a, **kw):  # noqa: ANN002, ANN003, ANN201
        pass

    def flush(self) -> None:
        pass


@pytest.fixture
def traced(monkeypatch):
    fake = FakeLangSmith()
    monkeypatch.setattr(tracing, "_state", tracing._State(logfire=True, langsmith=fake))
    _exporter.clear()
    return fake


async def test_answer_trace_has_every_step_and_no_text(indexed, client, traced):  # noqa: F811
    u = await register(client)
    cid = await new_conv(client, u["auth"])
    events = await ask(client, u["auth"], cid, QUESTION)
    assert events[-1][1]["status"] == "complete"

    names = [r["name"] for r in traced.runs]
    assert names[0] == "answer"
    assert {"input_guard", "retrieve", "generate", "verify"} <= set(names)
    root = traced.runs[0]
    assert root["outputs"]["status"] == "complete"
    retrieve = next(r for r in traced.runs if r["name"] == "retrieve")
    assert retrieve["run_type"] == "retriever"
    assert "medlineplus:dengue" in retrieve["outputs"]["doc_ids"]
    # Content is off by default: neither the question nor the answer text is sent.
    blob = json.dumps(traced.runs, default=str)
    assert "dengue?" not in blob and "fever" not in blob

    spans = {s.name: s for s in _exporter.get_finished_spans()}
    assert {"answer", "input_guard", "retrieve", "generate", "verify"} <= set(spans)
    root_id = spans["answer"].context.span_id
    assert spans["retrieve"].parent.span_id == root_id
    assert spans["retrieve"].attributes["output.abstain"] is False


async def test_trace_content_flag_sends_redacted_text(indexed, client, traced):  # noqa: F811
    tracing._state.content = True
    u = await register(client)
    cid = await new_conv(client, u["auth"])
    await ask(client, u["auth"], cid, QUESTION)
    assert traced.runs[0]["inputs"]["question"] == QUESTION


async def test_crisis_turn_traces_guard_only(indexed, client, traced):  # noqa: F811
    u = await register(client)
    cid = await new_conv(client, u["auth"])
    await ask(client, u["auth"], cid, "I want to kill myself")
    names = [r["name"] for r in traced.runs]
    assert names == ["answer", "input_guard"]
    assert traced.runs[1]["outputs"]["action"] == "crisis"


async def test_llm_call_is_a_child_of_the_step(traced, monkeypatch):
    import httpx

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "{}"}]}}],
                "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 3},
            },
        )

    chat = GeminiChat("k", "gemini-test")
    chat._client = httpx.AsyncClient(
        base_url="https://x", transport=httpx.MockTransport(handler)
    )
    tr = tracing.start_answer({"q": 1}, {})
    with tr.step("generate"):
        await chat.complete("s", "u")
    tr.end(status="complete")
    root = traced.runs[0]
    generate = next(c for c in traced.runs if c["name"] == "generate")
    llm = next(c for c in traced.runs if c["name"] == "llm gemini-test")
    assert llm["run_type"] == "llm" and llm["parent_run_id"] == generate["id"]
    assert generate["parent_run_id"] == root["id"]
    assert llm["outputs"]["usage_metadata"] == {"prompt_tokens": 11, "completion_tokens": 3}
    spans = {s.name: s for s in _exporter.get_finished_spans()}
    assert spans["llm gemini-test"].parent.span_id == spans["generate"].context.span_id


def test_disabled_tracing_is_a_no_op(monkeypatch):
    monkeypatch.setattr(tracing, "_state", tracing._State())
    tr = tracing.start_answer({"q": 1}, {})
    with tr.step("x") as st:
        st.set(a=1)
    tr.end()
    assert tr.root_run is None and tr.root_span is None
