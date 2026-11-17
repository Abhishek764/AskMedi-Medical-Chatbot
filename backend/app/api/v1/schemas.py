"""Request/response models for the public API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class Strict(BaseModel):
    # Reject unknown fields: blocks mass-assignment such as {"role": "admin"}.
    model_config = ConfigDict(extra="forbid")


# -- auth ---------------------------------------------------------------------
class RegisterIn(Strict):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    age_confirmed: Literal[True] = Field(description="User confirms they are 18 or older")
    accept_disclaimer: Literal[True] = Field(
        description="User accepts that AskMedi gives general information, not medical advice"
    )


class LoginIn(Strict):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class RefreshIn(Strict):
    refresh_token: str | None = Field(default=None, max_length=200)


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_in: int


class VerifyEmailIn(Strict):
    token: str = Field(max_length=200)


class ResetRequestIn(Strict):
    email: EmailStr


class ResetPasswordIn(Strict):
    token: str = Field(max_length=200)
    new_password: str = Field(min_length=1, max_length=256)


class ConsentIn(Strict):
    age_confirmed: Literal[True]
    accept_disclaimer: Literal[True]


class DeleteAccountIn(Strict):
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: str
    email_verified: bool
    consent_required: bool = False
    created_at: datetime


class AuthOut(BaseModel):
    user: UserOut
    tokens: TokenOut


class ProviderVerificationIn(Strict):
    profession: Literal["doctor", "pharmacist", "nurse"]
    registration_number: str = Field(min_length=3, max_length=80)
    council: str = Field(min_length=2, max_length=120)


class ProviderVerificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    profession: str
    registration_number: str
    council: str
    status: str
    created_at: datetime


class ReviewIn(Strict):
    decision: Literal["approved", "rejected"]


# -- conversations ------------------------------------------------------------
class ConversationIn(Strict):
    title: str | None = Field(default=None, max_length=200)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    risk_level: str
    created_at: datetime
    updated_at: datetime


class CitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position: int
    chunk_id: str
    doc_id: str
    title: str
    section: str | None
    source: str
    url: str | None
    score: float


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    status: str
    refusal_reason: str | None
    created_at: datetime
    citations: list[CitationOut] = []


class ConversationDetailOut(ConversationOut):
    messages: list[MessageOut]


class TriageAnswerIn(Strict):
    step: int = Field(ge=1, le=3)
    choices: list[Annotated[str, Field(min_length=1, max_length=40)]] = Field(
        min_length=1, max_length=10
    )


class AskIn(Strict):
    question: str = Field(default="", max_length=4000)
    triage: TriageAnswerIn | None = None  # an answer to a medicine-check question

    @model_validator(mode="after")
    def _question_or_answer(self) -> AskIn:
        if self.triage is None and not self.question.strip():
            raise ValueError("question is required")
        return self


class FeedbackIn(Strict):
    rating: Literal[1, -1]
    reason: str | None = Field(default=None, max_length=500)
