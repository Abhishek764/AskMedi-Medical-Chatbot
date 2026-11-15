"""Current-user endpoints, provider verification, and admin review."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import ContainerDep, CurrentUser, SessionDep, SettingsDep, require_role
from app.api.v1.auth import REFRESH_COOKIE, user_out
from app.api.v1.schemas import (
    ConsentIn,
    DeleteAccountIn,
    ProviderVerificationIn,
    ProviderVerificationOut,
    ReviewIn,
    UserOut,
)
from app.auth.service import AuthService
from app.core.errors import Conflict, NotFound
from app.db.models import (
    AuditLog,
    Conversation,
    Message,
    ProviderVerification,
    Role,
    User,
    VerificationStatus,
)

router = APIRouter(tags=["users"])


@router.get("/users/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return user_out(user)


@router.post("/users/me/consent", response_model=UserOut)
async def consent(
    body: ConsentIn,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    container: ContainerDep,
) -> UserOut:
    """Age (18+) and disclaimer confirmation; required once for accounts migrated from v1."""
    await AuthService(session, settings, container.mailer).record_consent(user)
    return user_out(user)


@router.delete("/users/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    body: DeleteAccountIn,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
    container: ContainerDep,
    response: Response,
) -> Response:
    await AuthService(session, settings, container.mailer).delete_account(user, body.password)
    response.delete_cookie(REFRESH_COOKIE, path="/v1/auth")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/users/me/export")
async def export_me(user: CurrentUser, session: SessionDep) -> dict[str, object]:
    """Data portability: everything we hold about the user, as JSON."""
    convs = (
        await session.scalars(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .options(selectinload(Conversation.messages).selectinload(Message.citations))
        )
    ).all()
    return {
        "user": user_out(user).model_dump(mode="json"),
        "conversations": [
            {
                "id": str(c.id),
                "title": c.title,
                "created_at": c.created_at.isoformat(),
                "messages": [
                    {
                        "role": m.role,
                        "content": m.content,
                        "status": m.status.value,
                        "created_at": m.created_at.isoformat(),
                        "citations": [cit.title for cit in m.citations],
                    }
                    for m in c.messages
                ],
            }
            for c in convs
        ],
    }


@router.post(
    "/provider-verifications",
    response_model=ProviderVerificationOut,
    status_code=status.HTTP_201_CREATED,
)
async def request_provider(
    body: ProviderVerificationIn, user: CurrentUser, session: SessionDep
) -> ProviderVerification:
    pending = await session.scalar(
        select(ProviderVerification.id).where(
            ProviderVerification.user_id == user.id,
            ProviderVerification.status == VerificationStatus.pending,
        )
    )
    if pending or user.role == Role.provider:
        raise Conflict("A verification request is already open or approved.")
    row = ProviderVerification(user_id=user.id, **body.model_dump())
    session.add(row)
    await session.commit()
    return row


AdminDep = Annotated[User, Depends(require_role(Role.admin))]


@router.get("/admin/provider-verifications", response_model=list[ProviderVerificationOut])
async def list_pending(_: AdminDep, session: SessionDep) -> list[ProviderVerification]:
    rows = await session.scalars(
        select(ProviderVerification)
        .where(ProviderVerification.status == VerificationStatus.pending)
        .order_by(ProviderVerification.created_at)
    )
    return list(rows)


@router.post(
    "/admin/provider-verifications/{verification_id}/review",
    response_model=ProviderVerificationOut,
)
async def review(
    verification_id: uuid.UUID, body: ReviewIn, admin: AdminDep, session: SessionDep
) -> ProviderVerification:
    row = await session.get(ProviderVerification, verification_id)
    if row is None or row.status != VerificationStatus.pending:
        raise NotFound("Verification request not found.")
    target = await session.get(User, row.user_id)
    if target is None:
        raise NotFound("User for this request no longer exists.")
    row.status = VerificationStatus(body.decision)
    row.reviewer_id = admin.id
    row.reviewed_at = datetime.now(UTC)
    if row.status == VerificationStatus.approved:
        target.role = Role.provider
    session.add(
        AuditLog(
            actor_id=admin.id,
            action=f"provider.{body.decision}",
            target=str(row.user_id),
        )
    )
    await session.commit()
    return row
