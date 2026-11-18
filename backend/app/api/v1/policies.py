"""Insurance policy demo: list policies, compare exclusions, diff a section, ask with page
citations. Signed-in users only; rate limited like chat."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import Field

from app.api.deps import ContainerDep, CurrentUser, SettingsDep
from app.api.v1.schemas import Strict
from app.core.errors import NotFound
from app.core.ratelimit import enforce_limit

router = APIRouter(prefix="/policies", tags=["policies"])
Ids = Annotated[str, Query(max_length=400, description="Comma-separated policy ids; empty = all")]


def _ids(raw: str) -> list[str]:
    return [i.strip() for i in raw.split(",") if i.strip()]


class PolicyAskIn(Strict):
    question: str = Field(min_length=3, max_length=1000)
    policy_ids: list[Annotated[str, Field(max_length=80)]] = Field(
        default_factory=list, max_length=10
    )


@router.get("")
async def list_policies(_: CurrentUser, container: ContainerDep) -> list[dict[str, object]]:
    return container.policies.summaries()


@router.get("/compare")
async def compare(_: CurrentUser, container: ContainerDep, ids: Ids = "") -> dict[str, object]:
    try:
        return container.policies.compare(_ids(ids))
    except KeyError as exc:
        raise NotFound(f"Unknown policy: {exc.args[0]}") from exc


@router.get("/diff")
async def diff(
    _: CurrentUser,
    container: ContainerDep,
    section: Annotated[str, Query(min_length=3, max_length=60)],
    ids: Ids = "",
) -> dict[str, object]:
    try:
        return container.policies.diff(_ids(ids), section)
    except KeyError as exc:
        raise NotFound(f"Unknown policy: {exc.args[0]}") from exc


@router.post("/ask")
async def ask(
    body: PolicyAskIn, user: CurrentUser, container: ContainerDep, settings: SettingsDep
) -> dict[str, object]:
    await enforce_limit(container.kv, f"policy:user:{user.id}", settings.rate_limit_per_minute, 60)
    res = await container.policies.ask(body.question, body.policy_ids)
    return {
        "answer": res.answer,
        "citations": res.citations,
        "refused": res.refused,
        "message": res.message,
    }
