"""Top-level router: health at the root, everything else under /v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth, conversations, health, users

v1 = APIRouter(prefix="/v1")
v1.include_router(auth.router)
v1.include_router(users.router)
v1.include_router(conversations.router)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(v1)
