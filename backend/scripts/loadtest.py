"""Async load test for the chat endpoint (run against staging, never production).

    uv run python scripts/loadtest.py --base http://localhost:8000 --users 50 --rps 10 --duration 60

Registers throwaway users, then sends questions at a target rate and reports throughput,
p50/p95/p99 latency, time to first SSE event, and error/429 rates.

Sizing reference (.claude/v2-plan.md §7): 50k DAU x 4 questions ≈ 200k answers/day; design for
20 answers/s sustained and 50/s bursts. Raise per-user limits on staging for the test
(RATE_LIMIT_PER_MINUTE, DAILY_QUESTION_QUOTA) so you measure the system, not the limiter.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import secrets
import statistics
import time
from collections import Counter

import httpx

QUESTIONS = [
    "What are the symptoms of dengue?",
    "How is tuberculosis spread?",
    "What are the side effects of metformin?",
    "What causes asthma?",
    "How can malaria be prevented?",
    "What is high blood pressure?",
    "How is anemia treated?",
    "What are the symptoms of migraine?",
    "What is amoxicillin used for?",
    "What causes kidney stones?",
]


async def _user(client: httpx.AsyncClient) -> tuple[dict[str, str], str]:
    email = f"load-{secrets.token_hex(6)}@example.test"
    r = await client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "password": secrets.token_urlsafe(16),
            "age_confirmed": True,
            "accept_disclaimer": True,
        },
    )
    r.raise_for_status()
    auth = {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}
    conv = await client.post("/v1/conversations", json={}, headers=auth)
    conv.raise_for_status()
    return auth, conv.json()["id"]


async def _ask(client, auth, conv_id, lat, ttfb, codes) -> None:
    t0 = time.perf_counter()
    first = None
    try:
        async with client.stream(
            "POST",
            f"/v1/conversations/{conv_id}/messages",
            json={"question": random.choice(QUESTIONS)},
            headers=auth,
        ) as r:  # noqa: S311
            codes[r.status_code] += 1
            async for _ in r.aiter_bytes():
                if first is None:
                    first = time.perf_counter() - t0
        lat.append(time.perf_counter() - t0)
        if first is not None:
            ttfb.append(first)
    except httpx.HTTPError as exc:
        codes[type(exc).__name__] += 1


def _pct(xs: list[float], p: float) -> float:
    return sorted(xs)[min(len(xs) - 1, int(p * len(xs)))] if xs else float("nan")


async def main(a: argparse.Namespace) -> None:
    limits = httpx.Limits(max_connections=a.users * 2)
    async with httpx.AsyncClient(base_url=a.base, timeout=60, limits=limits) as client:
        users = await asyncio.gather(*[_user(client) for _ in range(a.users)])
        lat: list[float] = []
        ttfb: list[float] = []
        codes: Counter[object] = Counter()
        tasks = []
        start = time.perf_counter()
        while time.perf_counter() - start < a.duration:
            auth, conv = random.choice(users)  # noqa: S311
            tasks.append(asyncio.create_task(_ask(client, auth, conv, lat, ttfb, codes)))
            await asyncio.sleep(1 / a.rps)
        await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start
    total = sum(codes.values())
    print(
        f"requests={total} ok={codes[200]} 429={codes[429]} other={total - codes[200] - codes[429]}"
    )
    print(f"throughput={len(lat) / elapsed:.1f}/s over {elapsed:.0f}s")
    print(
        f"latency p50={statistics.median(lat) if lat else float('nan'):.2f}s "
        f"p95={_pct(lat, 0.95):.2f}s p99={_pct(lat, 0.99):.2f}s"
    )
    print(
        f"first-event p50={statistics.median(ttfb) if ttfb else float('nan'):.2f}s p95={_pct(ttfb, 0.95):.2f}s"
    )
    print(f"codes={dict(codes)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--users", type=int, default=20)
    ap.add_argument("--rps", type=float, default=5)
    ap.add_argument("--duration", type=int, default=30)
    asyncio.run(main(ap.parse_args()))
