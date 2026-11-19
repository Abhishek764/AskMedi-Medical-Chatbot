"""Step tracing for each answer, sent to Pydantic Logfire and/or LangSmith.

One trace per assistant turn, with a child per pipeline step:

    answer
    ├── input_guard        crisis / emergency / injection / scope rules
    ├── medicine_check     (medicine questions only)
    ├── retrieve           hybrid dense + BM25, rerank          -> top score, doc ids
    ├── generate           answer writer                        -> model, tokens
    │   └── llm <model>    each provider call (fallbacks show as extra calls)
    └── verify             citation + support checks            -> ok / reason

Both backends are off unless configured, so this costs nothing by default:
- Logfire:   LOGFIRE_TOKEN (also instruments FastAPI, httpx and SQLAlchemy).
- LangSmith: LANGSMITH_API_KEY (+ LANGSMITH_PROJECT).

Privacy: by default only metadata leaves the server (lengths, ids, scores, statuses, models).
Set TRACE_CONTENT=true to also send the (PII-redacted) question and answer text. Never turn
that on with real patients' data unless the tracing vendor is covered by your privacy terms.

Context handling is explicit (no span stays "current" across an SSE yield): the root span is
never attached; each step attaches its own context only while it runs, inside a block that
contains no `yield`.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from opentelemetry import context as otel_context
from opentelemetry import trace as otel_trace

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine

    from app.core.config import Settings

logger = logging.getLogger("askmedi.tracing")
_tracer = otel_trace.get_tracer("askmedi")


@dataclass
class _State:
    logfire: bool = False
    langsmith: Any = None  # langsmith.Client when enabled
    project: str = "askmedi"
    content: bool = False


_state = _State()
_current_step: ContextVar[Step | None] = ContextVar("askmedi_step", default=None)


def configure(settings: Settings, app: FastAPI | None = None) -> None:
    """Turn on whichever backends have credentials. Safe to call more than once."""
    _state.content = settings.trace_content
    if settings.logfire_token and not _state.logfire:
        import logfire

        logfire.configure(
            token=settings.logfire_token,
            service_name="askmedi-api",
            environment=settings.env,
            console=False,
            send_to_logfire="if-token-present",
        )
        _state.logfire = True
    if _state.logfire and app is not None:
        import logfire

        # Endpoint arguments include the question body: never record them.
        logfire.instrument_fastapi(
            app,
            capture_headers=False,
            request_attributes_mapper=lambda _r, _a: None,
            excluded_urls="/healthz,/readyz,/metrics",
        )
        logfire.instrument_httpx(capture_headers=False)
    if settings.langsmith_api_key and _state.langsmith is None:
        from langsmith import Client

        _state.langsmith = Client(api_key=settings.langsmith_api_key)
        _state.project = settings.langsmith_project


def instrument_engine(engine: AsyncEngine) -> None:
    """SQL spans (statements only, never parameter values). Call once the engine exists."""
    if _state.logfire:
        import logfire

        try:
            logfire.instrument_sqlalchemy(engine=engine.sync_engine)
        except Exception:  # noqa: BLE001 - never fail startup over telemetry
            # e.g. instrumentation pins sqlalchemy < 2.1 while 2.1.x is installed
            logger.warning("Logfire SQLAlchemy instrumentation skipped", exc_info=True)


def shutdown() -> None:
    if _state.langsmith is not None:
        try:
            _state.langsmith.flush()
        except Exception:  # noqa: BLE001 - never fail shutdown over telemetry
            logger.warning("LangSmith flush failed", exc_info=True)


def enabled() -> bool:
    return _state.logfire or _state.langsmith is not None


def text(value: str) -> str | dict[str, int]:
    """The text itself when TRACE_CONTENT=true, otherwise only its length."""
    return value if _state.content else {"chars": len(value)}


def _otel_attrs(prefix: str, data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, (str, bool, int, float)):
            out[f"{prefix}.{k}"] = v
        elif isinstance(v, (list, tuple)) and all(isinstance(x, (str, int, float)) for x in v):
            out[f"{prefix}.{k}"] = list(v)
        elif v is not None:
            out[f"{prefix}.{k}"] = str(v)
    return out


@dataclass
class Step:
    name: str
    span: Any = None
    run: Any = None
    outputs: dict[str, Any] = field(default_factory=dict)

    def set(self, **outputs: Any) -> None:
        self.outputs.update(outputs)


class AnswerTrace:
    """Root of one answer's trace. Create with `start_answer`; always call `end`."""

    def __init__(self, inputs: dict[str, Any], metadata: dict[str, Any]) -> None:
        self.root_span = None
        self.root_run = None
        self._ended = False
        if _state.logfire:
            self.root_span = _tracer.start_span(
                "answer", attributes=_otel_attrs("input", {**inputs, **metadata})
            )
        if _state.langsmith is not None:
            from langsmith.run_trees import RunTree

            self.root_run = RunTree(
                name="answer",
                run_type="chain",
                inputs=inputs,
                extra={"metadata": metadata},
                project_name=_state.project,
                ls_client=_state.langsmith,
            )

    @contextmanager
    def step(self, name: str, run_type: str = "chain", **inputs: Any) -> Iterator[Step]:
        """Trace one step. The body must not `yield` to an SSE stream."""
        st = Step(name)
        token = None
        if self.root_span is not None:
            parent = otel_trace.set_span_in_context(self.root_span)
            st.span = _tracer.start_span(
                name, context=parent, attributes=_otel_attrs("input", inputs)
            )
            token = otel_context.attach(otel_trace.set_span_in_context(st.span))
        if self.root_run is not None:
            st.run = self.root_run.create_child(name, run_type, inputs=inputs)  # type: ignore[arg-type]
        step_token = _current_step.set(st)
        error: str | None = None
        try:
            yield st
        except BaseException as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            _current_step.reset(step_token)
            if st.span is not None:
                st.span.set_attributes(_otel_attrs("output", st.outputs))
                if error:
                    st.span.set_status(otel_trace.Status(otel_trace.StatusCode.ERROR, error))
                st.span.end()
            if token is not None:
                otel_context.detach(token)
            if st.run is not None:
                st.run.end(outputs=st.outputs, error=error)

    def end(self, **outputs: Any) -> None:
        if self._ended:
            return
        self._ended = True
        if self.root_span is not None:
            self.root_span.set_attributes(_otel_attrs("output", outputs))
            self.root_span.end()
        if self.root_run is not None:
            try:
                self.root_run.end(outputs=outputs)
                self.root_run.post(exclude_child_runs=False)
            except Exception:  # noqa: BLE001 - telemetry must never break an answer
                logger.warning("LangSmith post failed", exc_info=True)


class _NoTrace(AnswerTrace):
    def __init__(self) -> None:  # noqa: D107 - no backends, no work
        self.root_span = None
        self.root_run = None
        self._ended = False


def start_answer(inputs: dict[str, Any], metadata: dict[str, Any]) -> AnswerTrace:
    return AnswerTrace(inputs, metadata) if enabled() else _NoTrace()


@contextmanager
def llm_call(model: str) -> Iterator[dict[str, Any]]:
    """Wrap one provider call: an OTel span under the current step and a LangSmith `llm` child.

    The caller fills the yielded dict (outcome, tokens_in, tokens_out)."""
    info: dict[str, Any] = {"model": model}
    if not enabled():
        yield info
        return
    started = datetime.now(UTC)
    t = time.perf_counter()
    span = _tracer.start_span(f"llm {model}") if _state.logfire else None
    try:
        yield info
    finally:
        info["latency_ms"] = int((time.perf_counter() - t) * 1000)
        if span is not None:
            span.set_attributes(_otel_attrs("llm", info))
            span.end()
        step = _current_step.get()
        if step is not None and step.run is not None:
            child = step.run.create_child(
                f"llm {model}",
                "llm",
                inputs={"model": model},
                start_time=started,
                extra={"metadata": {"ls_model_name": model}},
            )
            usage = {
                "prompt_tokens": info.get("tokens_in", 0),
                "completion_tokens": info.get("tokens_out", 0),
            }
            child.end(
                outputs={"outcome": info.get("outcome"), "usage_metadata": usage},
                error=None if info.get("outcome") == "ok" else str(info.get("outcome")),
            )
