"""Chat-completion clients behind one interface, plus a fallback wrapper.

- ollama:    free local models (e.g. `ollama pull llama3.1:8b`), no key.
- openai:    needs OPENAI_API_KEY.
- anthropic: needs ANTHROPIC_API_KEY; also the fallback when OpenAI fails.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.metrics import LLM_CALLS, LLM_LATENCY

logger = logging.getLogger("askmedi.llm")


@dataclass
class ChatResult:
    text: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0


class LLMError(RuntimeError):
    pass


class ChatModel(Protocol):
    name: str

    async def complete(self, system: str, user: str, *, json_mode: bool = True) -> ChatResult: ...


class _HTTPChat:
    def __init__(self, base_url: str, headers: dict[str, str], timeout: float) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, headers=headers, timeout=timeout)

    async def _post(self, path: str, body: dict[str, object]) -> dict[str, object]:
        model = str(getattr(self, "name", type(self).__name__))
        t = time.perf_counter()
        try:
            r = await self._client.post(path, json=body)
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            LLM_CALLS.labels(
                model, "rate_limited" if code == 429 else f"http_{code // 100}xx"
            ).inc()
            raise LLMError(f"{type(self).__name__} failed: HTTP {code}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            LLM_CALLS.labels(model, "error").inc()
            raise LLMError(f"{type(self).__name__} failed: {type(exc).__name__}") from exc
        finally:
            LLM_LATENCY.labels(model).observe(time.perf_counter() - t)
        LLM_CALLS.labels(model, "ok").inc()
        return data  # type: ignore[no-any-return]

    async def aclose(self) -> None:
        await self._client.aclose()


def _shape_error(exc: Exception) -> LLMError:
    return LLMError(f"unexpected LLM response shape: {type(exc).__name__}")


class OpenAIChat(_HTTPChat):
    def __init__(self, api_key: str, model: str, timeout: float = 30) -> None:
        super().__init__(
            "https://api.openai.com/v1", {"Authorization": f"Bearer {api_key}"}, timeout
        )
        self.name = model

    async def complete(self, system: str, user: str, *, json_mode: bool = True) -> ChatResult:
        body: dict[str, object] = {
            "model": self.name,
            "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        data = await self._post("/chat/completions", body)
        try:
            usage = data.get("usage") or {}
            return ChatResult(
                str(data["choices"][0]["message"]["content"]),  # type: ignore[index]
                self.name,
                int(usage.get("prompt_tokens", 0)),  # type: ignore[union-attr]
                int(usage.get("completion_tokens", 0)),  # type: ignore[union-attr]
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise _shape_error(exc) from exc


class AnthropicChat(_HTTPChat):
    def __init__(self, api_key: str, model: str = "claude-haiku-5-5", timeout: float = 30) -> None:
        super().__init__(
            "https://api.anthropic.com/v1",
            {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            timeout,
        )
        self.name = model

    async def complete(self, system: str, user: str, *, json_mode: bool = True) -> ChatResult:
        data = await self._post(
            "/messages",
            {
                "model": self.name,
                "max_tokens": 1024,
                "temperature": 0,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )
        try:
            blocks = data.get("content") or []
            text = "".join(str(b.get("text", "")) for b in blocks if isinstance(b, dict))  # type: ignore[union-attr]
            usage = data.get("usage") or {}
            return ChatResult(
                text,
                self.name,
                int(usage.get("input_tokens", 0)),  # type: ignore[union-attr]
                int(usage.get("output_tokens", 0)),  # type: ignore[union-attr]
            )
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise _shape_error(exc) from exc


class OllamaChat(_HTTPChat):
    def __init__(self, base_url: str, model: str, timeout: float = 120) -> None:
        super().__init__(base_url, {}, timeout)
        self.name = model

    async def complete(self, system: str, user: str, *, json_mode: bool = True) -> ChatResult:
        body: dict[str, object] = {
            "model": self.name,
            "stream": False,
            "options": {"temperature": 0},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if json_mode:
            body["format"] = "json"
        data = await self._post("/api/chat", body)
        try:
            return ChatResult(
                str(data["message"]["content"]),  # type: ignore[index]
                self.name,
                int(data.get("prompt_eval_count", 0)),  # type: ignore[arg-type]
                int(data.get("eval_count", 0)),  # type: ignore[arg-type]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise _shape_error(exc) from exc


class GeminiChat(_HTTPChat):
    """Google Gemini via the Generative Language API (works with a free AI Studio key).

    Free-tier note: Google may use free-tier prompts to improve its products, so use it for
    testing with sample questions, not with real patients' messages.
    """

    def __init__(
        self, api_key: str, model: str = "gemini-3.1-flash-lite", timeout: float = 30
    ) -> None:
        super().__init__(
            "https://generativelanguage.googleapis.com/v1beta", {"x-goog-api-key": api_key}, timeout
        )
        self.name = model

    async def complete(self, system: str, user: str, *, json_mode: bool = True) -> ChatResult:
        config: dict[str, object] = {"temperature": 0, "maxOutputTokens": 1024}
        if json_mode:
            config["responseMimeType"] = "application/json"
        data = await self._post(
            f"/models/{self.name}:generateContent",
            {
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": config,
            },
        )
        try:
            candidates = data.get("candidates") or []
            if not candidates:  # blocked by the provider's safety filter, or empty
                reason = (data.get("promptFeedback") or {}).get("blockReason", "no candidates")  # type: ignore[union-attr]
                raise LLMError(f"Gemini returned no answer: {reason}")
            parts = candidates[0].get("content", {}).get("parts") or []  # type: ignore[union-attr]
            text = "".join(str(p.get("text", "")) for p in parts if isinstance(p, dict))
            if not text:
                raise LLMError("Gemini returned an empty answer")
            usage = data.get("usageMetadata") or {}
            return ChatResult(
                text,
                self.name,
                int(usage.get("promptTokenCount", 0)),  # type: ignore[union-attr]
                int(usage.get("candidatesTokenCount", 0)),  # type: ignore[union-attr]
            )
        except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
            raise _shape_error(exc) from exc


class FallbackChat:
    """Try each model in order; move to the next on failure (outage or rate limit)."""

    def __init__(self, *models: ChatModel) -> None:
        if not models:
            raise ValueError("FallbackChat needs at least one model")
        self.models = models
        self.name = models[0].name

    @property
    def primary(self) -> ChatModel:
        return self.models[0]

    async def complete(self, system: str, user: str, *, json_mode: bool = True) -> ChatResult:
        last: LLMError | None = None
        for model in self.models:
            try:
                return await model.complete(system, user, json_mode=json_mode)
            except LLMError as exc:
                logger.warning("LLM %s failed (%s); trying the next one", model.name, exc)
                last = exc
        raise last or LLMError("no model available")

    async def aclose(self) -> None:
        for model in self.models:
            close = getattr(model, "aclose", None)
            if close is not None:
                await close()
