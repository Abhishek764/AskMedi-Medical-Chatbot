"""Live product metrics for admins: how the assistant behaves with real users.

Counts come straight from the database (assistant messages, feedback, guard events, users),
so nothing extra is collected. No message text is read or returned.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.deps import SessionDep, require_role
from app.db.models import Document, Feedback, GuardEvent, Message, Role, User

router = APIRouter(tags=["admin"])
AdminDep = Annotated[User, Depends(require_role(Role.admin))]


def _pct(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


@router.get("/admin/metrics")
async def metrics(
    _: AdminDep, session: SessionDep, days: int = Query(7, ge=1, le=365)
) -> dict[str, object]:
    since = datetime.now(UTC) - timedelta(days=days)
    assistant = (Message.role == "assistant") & (Message.created_at >= since)

    by_status = dict(
        (
            await session.execute(
                select(Message.status, func.count()).where(assistant).group_by(Message.status)
            )
        ).all()
    )
    answers = sum(by_status.values())
    complete = by_status.get("complete", 0)
    by_reason = dict(
        (
            await session.execute(
                select(Message.refusal_reason, func.count())
                .where(assistant, Message.status == "refused")
                .group_by(Message.refusal_reason)
            )
        ).all()
    )
    latencies = sorted(
        (
            await session.scalars(
                select(Message.latency_ms).where(assistant, Message.latency_ms.is_not(None))
            )
        ).all()
    )
    tokens = (
        await session.execute(
            select(
                func.coalesce(func.sum(Message.tokens_in), 0),
                func.coalesce(func.sum(Message.tokens_out), 0),
            ).where(assistant)
        )
    ).one()
    ratings = dict(
        (
            await session.execute(
                select(Feedback.rating, func.count())
                .where(Feedback.created_at >= since)
                .group_by(Feedback.rating)
            )
        ).all()
    )
    guard = dict(
        (
            await session.execute(
                select(GuardEvent.kind, func.count())
                .where(GuardEvent.created_at >= since)
                .group_by(GuardEvent.kind)
            )
        ).all()
    )
    users_total = await session.scalar(select(func.count()).select_from(User)) or 0
    new_users = (
        await session.scalar(select(func.count()).select_from(User).where(User.created_at >= since))
        or 0
    )
    active = (
        await session.scalar(
            select(func.count(func.distinct(Message.conversation_id))).where(
                Message.created_at >= since
            )
        )
        or 0
    )
    docs = dict(
        (
            await session.execute(select(Document.source, func.count()).group_by(Document.source))
        ).all()
    )

    def pctl(p: float) -> int | None:
        return latencies[min(len(latencies) - 1, int(p * len(latencies)))] if latencies else None

    up, down = ratings.get(1, 0), ratings.get(-1, 0)
    return {
        "window_days": days,
        "usage": {
            "answers": answers,
            "active_conversations": active,
            "users_total": users_total,
            "new_users": new_users,
        },
        "answers_by_status": {str(k): v for k, v in by_status.items()},
        "answer_rate": _pct(complete, answers),
        "refusals_by_reason": {str(k): v for k, v in by_reason.items()},
        "safety_events": {str(k): v for k, v in guard.items()},
        "latency_ms": {
            "p50": pctl(0.5),
            "p95": pctl(0.95),
            "max": latencies[-1] if latencies else None,
        },
        "tokens": {"in": int(tokens[0]), "out": int(tokens[1])},
        "feedback": {
            "up": up,
            "down": down,
            "helpful_rate": _pct(up, up + down),
            "coverage": _pct(up + down, complete),
        },
        "corpus": {
            "documents_by_source": {str(k): v for k, v in docs.items()},
            "documents": sum(docs.values()),
        },
    }
