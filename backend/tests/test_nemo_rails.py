"""NeMo Guardrails layer: pipeline wiring (fake rails) and the real NemoRails wrapper."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.guards.nemo import NemoRails, Rails, RailVerdict
from tests.helpers import register
from tests.test_chat import ask, indexed, new_conv  # noqa: F401 - fixture reused


class FakeRails(Rails):
    def __init__(self, block_input: bool = False, block_output: bool = False) -> None:
        self.block_input, self.block_output = block_input, block_output
        self.seen: list[str] = []

    async def check_input(self, text: str) -> RailVerdict:
        self.seen.append(f"in:{text}")
        return RailVerdict(self.block_input, "self check input" if self.block_input else None)

    async def check_output(self, question: str, answer: str) -> RailVerdict:
        self.seen.append(f"out:{answer[:20]}")
        return RailVerdict(self.block_output, "self check output" if self.block_output else None)


async def _ask(app, client, question: str, rails: Rails):
    app.state.container.pipeline.rails = rails
    app.state.container.pipeline.kv = None
    u = await register(client)
    cid = await new_conv(client, u["auth"])
    return await ask(client, u["auth"], cid, question)


async def test_rails_pass_clean_answers(app, client, indexed):  # noqa: F811
    rails = FakeRails()
    events = await _ask(app, client, "What are the symptoms of dengue?", rails)
    assert events[-1][1]["status"] == "complete"
    assert rails.seen[0] == "in:What are the symptoms of dengue?"
    assert rails.seen[1].startswith("out:")


async def test_input_rail_blocks_before_retrieval(app, client, indexed):  # noqa: F811
    rails = FakeRails(block_input=True)
    events = await _ask(app, client, "What are the symptoms of dengue?", rails)
    assert ("refusal", "rail_input") in [(e, d.get("reason")) for e, d in events]
    assert "status" not in [e for e, _ in events]  # never reached retrieval
    assert len(rails.seen) == 1


async def test_output_rail_withholds_answer(app, client, indexed):  # noqa: F811
    events = await _ask(
        app, client, "What are the symptoms of dengue?", FakeRails(block_output=True)
    )
    types = [e for e, _ in events]
    assert ("refusal", "rail_output") in [(e, d.get("reason")) for e, d in events]
    assert "sentence" not in types and "citations" not in types


async def test_deterministic_guards_run_before_rails(app, client, indexed):  # noqa: F811
    rails = FakeRails()
    events = await _ask(app, client, "I want to kill myself", rails)
    assert events[-1][1]["status"] == "crisis"
    assert rails.seen == []  # crisis never waits on an LLM


def _wrapper(check, *, fail_closed: bool = False, timeout: float = 1.0) -> NemoRails:
    pytest.importorskip("nemoguardrails")
    r = object.__new__(NemoRails)
    r._rails = SimpleNamespace(check_async=check)
    r._timeout, r._fail_closed = timeout, fail_closed
    return r


async def test_nemo_wrapper_maps_status():
    pytest.importorskip("nemoguardrails")
    from nemoguardrails.rails.llm.options import RailsResult, RailStatus

    async def blocked(messages, rail_types):
        return RailsResult(status=RailStatus.BLOCKED, content="", rail="self check input")

    v = await _wrapper(blocked).check_input("x")
    assert v == RailVerdict(True, "self check input")


@pytest.mark.parametrize(("fail_closed", "expect_blocked"), [(False, False), (True, True)])
async def test_nemo_wrapper_failures(fail_closed, expect_blocked):
    async def slow(messages, rail_types):
        await asyncio.sleep(5)

    v = await _wrapper(slow, fail_closed=fail_closed, timeout=0.05).check_output("q", "a")
    assert v.blocked is expect_blocked and v.error == "TimeoutError"


def test_guardrails_config_loads():
    pytest.importorskip("nemoguardrails")
    from pathlib import Path

    from nemoguardrails import RailsConfig

    cfg = RailsConfig.from_path(str(Path(__file__).resolve().parents[1] / "guardrails"))
    assert cfg.rails.input.flows == ["self check input"]
    assert cfg.rails.output.flows == ["self check output"]
    tasks = {p.task for p in cfg.prompts}
    assert {"self_check_input", "self_check_output"} <= tasks
