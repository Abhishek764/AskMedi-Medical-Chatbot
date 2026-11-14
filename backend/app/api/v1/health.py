"""Liveness and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.db.session import ping as db_ping

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request) -> JSONResponse:
    container = getattr(request.app.state, "container", None)
    if container is None:
        return JSONResponse({"status": "starting", "checks": {}}, status_code=503)
    checks = {
        "database": await db_ping(container.engine),
        "kv": await container.kv.ping(),
    }
    ok = all(checks.values())
    return JSONResponse(
        {"status": "ok" if ok else "degraded", "checks": checks}, status_code=200 if ok else 503
    )
