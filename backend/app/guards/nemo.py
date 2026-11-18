"""NeMo Guardrails: an LLM-judged second layer on top of the deterministic guards.

Enabled with GUARDRAILS_PROVIDER=nemo (needs `uv sync --extra rails` and an OpenAI or Gemini
key). Rails and prompts live in backend/guardrails/ (config.yml, prompts.yml):

- input rail  ("self check input"):  runs after app/guards allowed a message, before retrieval.
- output rail ("self check output"): runs on the verified answer, before the user sees it.

The deterministic guards always run first, so crisis and emergency handling never depend on
an LLM. If a rail call fails or exceeds GUARDRAILS_TIMEOUT_SECONDS the message passes
(fail open, counted in askmedi_rail_checks_total{outcome="error"}) unless
GUARDRAILS_FAIL_CLOSED=true.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.metrics import RAIL_CHECKS

logger = logging.getLogger("askmedi.rails")
GEMINI_OPENAI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


@dataclass(frozen=True)
class RailVerdict:
    blocked: bool
    rail: str | None = None
    error: str | None = None


class Rails:
    """Interface the pipeline uses; NemoRails is the real one, tests use fakes."""

    async def check_input(self, text: str) -> RailVerdict:  # pragma: no cover - interface
        raise NotImplementedError

    async def check_output(self, question: str, answer: str) -> RailVerdict:  # pragma: no cover
        raise NotImplementedError


def _judge_llm(settings: Settings) -> Any:
    from langchain_openai import ChatOpenAI

    common: dict[str, Any] = {"temperature": 0, "max_retries": 1, "timeout": 15}
    if settings.openai_api_key:
        model = settings.guardrails_model or settings.openai_model
        return ChatOpenAI(model=model, api_key=settings.openai_api_key, **common)
    if settings.gemini_api_key:
        return ChatOpenAI(
            model=settings.guardrails_model or settings.gemini_model,
            base_url=GEMINI_OPENAI_URL,
            api_key=settings.gemini_api_key,
            **common,
        )
    raise ValueError("GUARDRAILS_PROVIDER=nemo needs OPENAI_API_KEY or GEMINI_API_KEY")


class NemoRails(Rails):
    def __init__(self, settings: Settings) -> None:
        from nemoguardrails import LLMRails, RailsConfig

        config_dir = Path(settings.guardrails_config_dir)
        self._rails = LLMRails(RailsConfig.from_path(str(config_dir)), llm=_judge_llm(settings))
        self._timeout = settings.guardrails_timeout_seconds
        self._fail_closed = settings.guardrails_fail_closed

    async def _check(self, kind: str, messages: list[dict[str, str]]) -> RailVerdict:
        from nemoguardrails.rails.llm.options import RailStatus, RailType

        rail_type = RailType.INPUT if kind == "input" else RailType.OUTPUT
        try:
            res = await asyncio.wait_for(
                self._rails.check_async(messages, rail_types=[rail_type]), self._timeout
            )
        except Exception as exc:  # noqa: BLE001 - timeouts and provider errors alike
            RAIL_CHECKS.labels(kind, "error").inc()
            logger.warning("NeMo %s rail failed: %s", kind, type(exc).__name__)
            return RailVerdict(self._fail_closed, None, type(exc).__name__)
        blocked = res.status == RailStatus.BLOCKED
        RAIL_CHECKS.labels(kind, "blocked" if blocked else "passed").inc()
        return RailVerdict(blocked, res.rail)

    async def check_input(self, text: str) -> RailVerdict:
        return await self._check("input", [{"role": "user", "content": text}])

    async def check_output(self, question: str, answer: str) -> RailVerdict:
        return await self._check(
            "output",
            [{"role": "user", "content": question}, {"role": "assistant", "content": answer}],
        )


def build_rails(settings: Settings) -> Rails | None:
    if settings.guardrails_provider != "nemo":
        return None
    return NemoRails(settings)
