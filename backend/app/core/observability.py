"""Optional Sentry error tracking. Off unless SENTRY_DSN is set; never sends PII or bodies."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings

_SENSITIVE_KEYS = {"authorization", "cookie", "set-cookie", "x-api-key"}


def _scrub(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any] | None:
    request = event.get("request") or {}
    request.pop("data", None)  # questions, passwords: never leave the server
    request.pop("cookies", None)
    request.pop("query_string", None)
    headers = request.get("headers") or {}
    for key in list(headers):
        if key.lower() in _SENSITIVE_KEYS:
            headers[key] = "[scrubbed]"
    event.pop("user", None)
    return event


def init_sentry(settings: Settings) -> bool:
    if not settings.sentry_dsn:
        return False
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.env,
        send_default_pii=False,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        max_request_body_size="never",
        before_send=_scrub,  # type: ignore[arg-type]
    )
    return True
