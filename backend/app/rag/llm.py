"""Chat-completion clients behind one interface, plus a fallback wrapper.

- ollama:    free local models (e.g. `ollama pull llama3.1:8b`), no key.
- openai:    needs OPENAI_API_KEY.
- anthropic: needs ANTHROPIC_API_KEY; also the fallback when OpenAI fails.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

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
        try:
            r = await self._client.post(path, json=body)
            r.raise_for_status()
            return r.json()  # type: ignore[no-any-return]
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError(f"{type(self).__name__} failed: {type(exc).__name__}") from exc

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


class FallbackChat:
    """Try the primary model; on failure use the secondary (vendor outage protection)."""

    def __init__(self, primary: ChatModel, secondary: ChatModel) -> None:
        self.primary, self.secondary = primary, secondary
        self.name = primary.name

    async def complete(self, system: str, user: str, *, json_mode: bool = True) -> ChatResult:
        try:
            return await self.primary.complete(system, user, json_mode=json_mode)
        except LLMError:
            logger.warning("primary LLM failed; using fallback %s", self.secondary.name)
            return await self.secondary.complete(system, user, json_mode=json_mode)
