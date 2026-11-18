"""Provider selection (auto: OpenAI, Gemini, Claude by available key), Gemini client, the
fallback chain, and the extractive fallback when every model fails."""

import json

import httpx
import pytest

from app.core.config import Settings
from app.core.container import build_generator, llm_chain
from app.rag.generate import Draft, ExtractiveGenerator, ResilientGenerator
from app.rag.llm import ChatResult, FallbackChat, GeminiChat, LLMError
from app.rag.types import Retrieved


def settings(**kw) -> Settings:
    return Settings(_env_file=None, env="test", **kw)


def test_auto_without_keys_is_free_extractive_mode():
    assert isinstance(build_generator(settings()), ExtractiveGenerator)


def test_auto_prefers_openai_then_gemini():
    gem_only = llm_chain(settings(gemini_api_key="g"))
    assert [m.name for m in gem_only] == ["gemini-3.1-flash-lite"]
    both = llm_chain(settings(gemini_api_key="g", openai_api_key="o"))
    assert [m.name for m in both] == ["gpt-4o-mini", "gemini-3.1-flash-lite"]
    assert isinstance(
        build_generator(settings(gemini_api_key="g", openai_api_key="o")), ResilientGenerator
    )


def test_explicit_gemini_goes_first_and_requires_a_key():
    chain = llm_chain(settings(llm_provider="gemini", gemini_api_key="g", openai_api_key="o"))
    assert [m.name for m in chain] == ["gemini-3.1-flash-lite", "gpt-4o-mini"]
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        settings(llm_provider="gemini")


def _gemini(handler) -> GeminiChat:
    chat = GeminiChat("key", "gemini-3.1-flash-lite")
    chat._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://x/v1beta"
    )
    return chat


async def test_gemini_request_and_response_shape():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["path"] = req.url.path
        seen["body"] = json.loads(req.content)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": '{"insufficient": false, "sentences": []}'}]}}
                ],
                "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 7},
            },
        )

    res = await _gemini(handler).complete("system rules", "user question")
    assert seen["path"].endswith("/models/gemini-3.1-flash-lite:generateContent")
    assert seen["body"]["system_instruction"]["parts"][0]["text"] == "system rules"
    assert seen["body"]["contents"][0]["parts"][0]["text"] == "user question"
    assert seen["body"]["generationConfig"]["responseMimeType"] == "application/json"
    assert (res.tokens_in, res.tokens_out) == (12, 7)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(429, json={"error": {"message": "quota"}}),
        httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}),
        httpx.Response(200, json={"candidates": [{"content": {"parts": []}}]}),
    ],
)
async def test_gemini_failures_raise_llm_error(response):
    with pytest.raises(LLMError):
        await _gemini(lambda req: response).complete("s", "u")


class Fake:
    def __init__(self, name, fail=False):
        self.name, self.fail, self.calls = name, fail, 0

    async def complete(self, system, user, *, json_mode=True):
        self.calls += 1
        if self.fail:
            raise LLMError("down")
        return ChatResult("{}", self.name)


async def test_fallback_chain_tries_each_model_in_order():
    a, b, c = Fake("a", fail=True), Fake("b", fail=True), Fake("c")
    assert (await FallbackChat(a, b, c).complete("s", "u")).model == "c"
    assert (a.calls, b.calls, c.calls) == (1, 1, 1)
    with pytest.raises(LLMError):
        await FallbackChat(Fake("x", fail=True)).complete("s", "u")


async def test_all_models_down_falls_back_to_extractive():
    passage = Retrieved(
        "c", "p", "d", "Dengue causes high fever.", 0.9, {}, "Dengue causes high fever and rash."
    )

    class Broken:
        name = "broken"

        async def generate(self, question, passages, *, role):
            return Draft([], "broken", insufficient=True, notes=["llm_error"])

    draft = await ResilientGenerator(Broken(), ExtractiveGenerator()).generate(
        "dengue fever", [passage], role="public"
    )
    assert draft.sentences and "fell_back_to_extractive" in draft.notes


async def test_genuine_no_answer_is_not_overridden():
    class Honest:
        name = "honest"

        async def generate(self, question, passages, *, role):
            return Draft([], "honest", insufficient=True)

    draft = await ResilientGenerator(Honest(), ExtractiveGenerator()).generate(
        "x", [], role="public"
    )
    assert draft.insufficient and draft.model == "honest"
