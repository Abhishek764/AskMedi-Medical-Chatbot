"""Fixed-window rate limits and daily quotas on top of the KV store."""

from __future__ import annotations

import time

from app.core.errors import RateLimited
from app.core.kv import KV


async def enforce_limit(kv: KV, bucket: str, limit: int, window_seconds: int) -> None:
    window = int(time.time() // window_seconds)
    count = await kv.incr(f"rl:{bucket}:{window}", ttl_seconds=window_seconds + 5)
    if count > limit:
        raise RateLimited("Too many requests. Please wait and try again.")


async def enforce_daily_quota(kv: KV, user_id: str, quota: int) -> None:
    day = time.strftime("%Y-%m-%d", time.gmtime())
    count = await kv.incr(f"quota:{user_id}:{day}", ttl_seconds=26 * 3600)
    if count > quota:
        raise RateLimited(
            "You have reached today's question limit. It resets at midnight UTC.",
            code="quota_exceeded",
        )
