"""Smoke test a running stack through the web dev server's proxy (or the API directly).

uv run python scripts/smoke.py [--base http://127.0.0.1:5173]
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import time

import httpx


def events(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(ln.split(": ", 1) for ln in block.splitlines() if ": " in ln)
        if "event" in lines:
            out.append((lines["event"], json.loads(lines["data"])))
    return out


def main(base: str) -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    c = httpx.Client(base_url=base, timeout=120)
    print("readyz:", c.get("/readyz").json() if "8000" in base else "(via web proxy: skipped)")
    email = f"smoke-{secrets.token_hex(4)}@example.com"
    r = c.post(
        "/v1/auth/register",
        json={
            "email": email,
            "password": secrets.token_urlsafe(12),
            "age_confirmed": True,
            "accept_disclaimer": True,
        },
    )
    r.raise_for_status()
    auth = {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}
    cid = c.post("/v1/conversations", json={}, headers=auth).json()["id"]

    def ask(body: dict) -> list[tuple[str, dict]]:
        t = time.perf_counter()
        resp = c.post(f"/v1/conversations/{cid}/messages", json=body, headers=auth)
        evs = events(resp.text)
        done = next((d for e, d in evs if e == "done"), {})
        print(
            f"\n> {body.get('question') or body.get('triage')}  [{done.get('status')}, {time.perf_counter() - t:.1f}s]"
        )
        for e, d in evs:
            if e == "sentence":
                print("  ", d["text"][:220], d["citations"])
            elif e in ("refusal", "emergency", "crisis"):
                print(f"   [{e}]", d.get("message", "")[:160])
            elif e == "triage":
                print("   Q:", d["question"])
            elif e == "medicines":
                for m in d["items"]:
                    print(
                        "   -", m["name"], "|", (m.get("directions") or "")[:120].replace("\n", " ")
                    )
            elif e == "citations":
                for it in d["items"][:3]:
                    print(f"     [{it['position']}] {it['title']} › {it['section']}")
        return evs

    ask({"question": "What are the symptoms of dengue?"})
    ask({"question": "Write me a Python function"})
    ask({"question": "I have crushing chest pain right now"})
    ask({"question": "I have a headache, what medicine can I take?"})
    ask({"triage": {"step": 1, "choices": ["adult"]}})
    ask({"triage": {"step": 2, "choices": ["none"]}})
    ask({"triage": {"step": 3, "choices": ["none"]}})
    pol = c.get("/v1/policies/compare", headers=auth).json()
    print("\npolicies:", [p["id"] for p in pol["policies"]], "| differences:", pol["differences"])
    a = c.post(
        "/v1/policies/ask", json={"question": "Is damage from a landslide covered?"}, headers=auth
    ).json()
    print(
        "policy answer:",
        [s["text"][:120] for s in a["answer"]],
        [x["clause"] for x in a["citations"]],
        a["message"],
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:5173")
    main(ap.parse_args().base)
