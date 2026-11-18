"""Conversations, the streaming chat endpoint (SSE), and feedback.

Every query is scoped by the current user's id (no BOLA): other users' ids return 404.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import ContainerDep, CurrentUser, SessionDep, SettingsDep
from app.api.v1.schemas import (
    AskIn,
    ConversationDetailOut,
    ConversationIn,
    ConversationOut,
    FeedbackIn,
)
from app.core.errors import AppError, NotFound
from app.core.logging import log_event
from app.core.metrics import record_answer
from app.core.ratelimit import enforce_daily_quota, enforce_limit
from app.db.models import (
    Citation,
    Conversation,
    Feedback,
    GuardEvent,
    Message,
    MessageStatus,
    RiskLevel,
    User,
)
from app.guards.pii import redact
from app.guards.resources import REFUSALS
from app.rag.pipeline import AnswerRecord, UserContext
from app.triage.engine import TriageState, question_for

router = APIRouter(tags=["conversations"])
logger = logging.getLogger("askmedi.chat")


async def _owned(session, user: User, conversation_id: uuid.UUID, *, load: bool = False):
    q = select(Conversation).where(
        Conversation.id == conversation_id, Conversation.user_id == user.id
    )
    if load:
        q = q.options(selectinload(Conversation.messages).selectinload(Message.citations))
    conv = await session.scalar(q)
    if conv is None:
        raise NotFound("Conversation not found.")
    return conv


@router.post("/conversations", response_model=ConversationOut, status_code=201)
async def create_conversation(body: ConversationIn, user: CurrentUser, session: SessionDep):
    conv = Conversation(user_id=user.id, title=(body.title or "New chat")[:200])
    session.add(conv)
    await session.commit()
    return conv


@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    user: CurrentUser,
    session: SessionDep,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    rows = await session.scalars(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailOut)
async def get_conversation(conversation_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    return await _owned(session, user, conversation_id, load=True)


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
async def rename_conversation(
    conversation_id: uuid.UUID, body: ConversationIn, user: CurrentUser, session: SessionDep
):
    conv = await _owned(session, user, conversation_id)
    if body.title:
        conv.title = body.title[:200]
    await session.commit()
    return conv


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Response:
    conv = await _owned(session, user, conversation_id)
    await session.delete(conv)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _sse(event: str, data: dict[str, object]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n".encode()


@router.post("/conversations/{conversation_id}/messages")
async def ask(
    conversation_id: uuid.UUID,
    body: AskIn,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    container: ContainerDep,
) -> StreamingResponse:
    if len(body.question) > settings.max_question_chars:
        raise AppError(
            f"Please keep questions under {settings.max_question_chars} characters.",
            code="question_too_long",
        )
    await enforce_limit(container.kv, f"chat:user:{user.id}", settings.rate_limit_per_minute, 60)
    if user.age_attested_at is None or user.disclaimer_accepted_at is None:
        raise AppError(
            "Please confirm you are 18 or older and accept the medical disclaimer first.",
            code="consent_required",
            status_code=403,
        )
    conv = await _owned(session, user, conversation_id, load=True)
    turns = sum(1 for m in conv.messages if m.role == "user")
    if turns >= settings.max_turns_per_conversation:
        raise AppError(REFUSALS["conversation_limit"], code="conversation_limit")

    triage_key = f"triage:{conv.id}"
    stored = await container.kv.get(triage_key)
    triage_state = json.loads(stored) if stored else None
    if body.triage is None:
        # A new question counts toward the daily quota; answering a check question doesn't.
        await enforce_daily_quota(container.kv, str(user.id), settings.daily_question_quota)
        shown = body.question
    else:
        shown = _answer_labels(triage_state, body.triage.step, body.triage.choices)

    history = [m.content for m in conv.messages if m.role == "user" and m.content][-3:]
    if not conv.messages:
        conv.title = redact(shown).text[:60]
    user_msg = Message(conversation_id=conv.id, role="user", content=shown)
    session.add(user_msg)
    await session.commit()

    ctx = UserContext(
        role=user.role.value,
        elevated_risk=conv.risk_level == RiskLevel.elevated,
        country=settings.crisis_country,
        triage=triage_state,
        triage_answer=(body.triage.step, body.triage.choices) if body.triage else None,
    )
    pipeline = container.pipeline
    sessionmaker = container.sessionmaker
    kv = container.kv
    conv_id, user_id = conv.id, user.id

    async def stream() -> AsyncIterator[bytes]:
        record: AnswerRecord | None = None
        try:
            async for ev in pipeline.answer_stream(body.question, history, ctx):
                if ev.type == "result":
                    record = ev.data["record"]  # type: ignore[assignment]
                    continue
                yield _sse(ev.type, ev.data)
        except Exception:
            record = AnswerRecord("error", "Something went wrong. Please try again.", "error")
            yield _sse("error", {"message": record.content})
        assert record is not None
        if record.triage_state is not None:
            await kv.set(triage_key, json.dumps(record.triage_state), ttl_seconds=3600)
        else:  # any other answer ends a medicine check in progress
            await kv.delete(triage_key)
        message_id = await _persist(sessionmaker, conv_id, user_id, record)
        yield _sse("done", {"message_id": str(message_id), "status": record.status})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _answer_labels(state: dict[str, object] | None, step: int, choices: list[str]) -> str:
    """The option labels the person picked, as their message text (ids are validated later)."""
    parsed = TriageState.from_dict(state) if state else None
    if parsed is None or parsed.step != step:
        return ", ".join(choices)
    labels = {o.id: o.label for o in question_for(parsed).options}
    return ", ".join(labels.get(c, c) for c in choices)


async def _persist(sessionmaker, conv_id: uuid.UUID, user_id: uuid.UUID, rec: AnswerRecord):
    async with sessionmaker() as s:
        msg = Message(
            conversation_id=conv_id,
            role="assistant",
            content=rec.content,
            status=MessageStatus(rec.status),
            refusal_reason=rec.refusal_reason,
            model=rec.model,
            tokens_in=rec.tokens_in,
            tokens_out=rec.tokens_out,
            latency_ms=rec.latency_ms,
        )
        s.add(msg)
        await s.flush()
        for c in rec.citations:
            s.add(
                Citation(
                    message_id=msg.id,
                    position=c.position,
                    chunk_id=c.chunk_id,
                    doc_id=c.doc_id,
                    title=c.title[:500],
                    section=(c.section or None),
                    source=c.source,
                    url=c.url,
                    score=c.score,
                )
            )
        if rec.guard_kind:
            s.add(
                GuardEvent(
                    user_id=user_id,
                    conversation_id=conv_id,
                    kind=rec.guard_kind,
                    action=rec.status,
                )
            )
        conv = await s.get(Conversation, conv_id)
        if conv is not None:
            if rec.raise_risk:
                conv.risk_level = RiskLevel.elevated
            conv.updated_at = func.now()
        await s.commit()
        record_answer(
            rec.status,
            rec.refusal_reason,
            rec.latency_ms,
            model=rec.model,
            tokens_in=rec.tokens_in,
            tokens_out=rec.tokens_out,
            guard_kind=rec.guard_kind,
            cached=rec.cached,
        )
        log_event(
            logger,
            "answer",
            status=rec.status,
            reason=rec.refusal_reason,
            latency_ms=rec.latency_ms,
            model=rec.model,
            tokens_in=rec.tokens_in,
            tokens_out=rec.tokens_out,
            citations=len(rec.citations),
            cached=rec.cached,
        )
        return msg.id


@router.post("/messages/{message_id}/feedback", status_code=204)
async def feedback(
    message_id: uuid.UUID, body: FeedbackIn, user: CurrentUser, session: SessionDep
) -> Response:
    msg = await session.scalar(
        select(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Message.id == message_id,
            Conversation.user_id == user.id,
            Message.role == "assistant",
        )
    )
    if msg is None:
        raise NotFound("Message not found.")
    existing = await session.scalar(
        select(Feedback).where(Feedback.message_id == msg.id, Feedback.user_id == user.id)
    )
    if existing:
        existing.rating, existing.reason = body.rating, body.reason
    else:
        session.add(
            Feedback(message_id=msg.id, user_id=user.id, rating=body.rating, reason=body.reason)
        )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
