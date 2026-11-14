"""Small key-value interface used for rate limits, quotas, risk state and cache.

`RedisKV` in staging/prod; `InMemoryKV` for dev and tests (single process only).
"""

from __future__ import annotations

import time
from typing import Protocol


class KV(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None: ...
    async def incr(self, key: str, ttl_seconds: int) -> int:
        """Increment and return the counter; the TTL is set when the key is created."""
        ...
    async def delete(self, key: str) -> None: ...
    async def ping(self) -> bool: ...
    async def close(self) -> None: ...


class InMemoryKV:
    def __init__(self, clock: callable = time.monotonic) -> None:  # type: ignore[valid-type]
        self._data: dict[str, tuple[str, float | None]] = {}
        self._clock = clock

    def _alive(self, key: str) -> tuple[str, float | None] | None:
        item = self._data.get(key)
        if item is None:
            return None
        _, expires = item
        if expires is not None and self._clock() >= expires:
            del self._data[key]
            return None
        return item

    async def get(self, key: str) -> str | None:
        item = self._alive(key)
        return item[0] if item else None

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        expires = self._clock() + ttl_seconds if ttl_seconds else None
        self._data[key] = (value, expires)

    async def incr(self, key: str, ttl_seconds: int) -> int:
        item = self._alive(key)
        if item is None:
            self._data[key] = ("1", self._clock() + ttl_seconds)
            return 1
        value = int(item[0]) + 1
        self._data[key] = (str(value), item[1])
        return value

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        self._data.clear()


class RedisKV:
    def __init__(self, url: str) -> None:
        from redis.asyncio import Redis

        self._r = Redis.from_url(url, decode_responses=True)

    async def get(self, key: str) -> str | None:
        return await self._r.get(key)  # type: ignore[no-any-return]

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        await self._r.set(key, value, ex=ttl_seconds)

    async def incr(self, key: str, ttl_seconds: int) -> int:
        pipe = self._r.pipeline()
        pipe.incr(key)
        pipe.expire(key, ttl_seconds, nx=True)
        value, _ = await pipe.execute()
        return int(value)

    async def delete(self, key: str) -> None:
        await self._r.delete(key)

    async def ping(self) -> bool:
        try:
            return bool(await self._r.ping())
        except Exception:
            return False

    async def close(self) -> None:
        await self._r.aclose()


def build_kv(redis_url: str | None) -> KV:
    return RedisKV(redis_url) if redis_url else InMemoryKV()
