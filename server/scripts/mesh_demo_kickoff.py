"""Kick off and observe the Quietcare @mention mesh handoff.

Assumes the elder and caretaker agents are already running
(python -m app.band_mesh.elder / .caretaker). Acting as the caretaker identity,
this creates a room, adds the elder, and posts an incident @mentioning the elder.
The running elder should reason and @mention the caretaker, which triages back.
Polls the room and prints the conversation as it unfolds.

Run:  python scripts/mesh_demo_kickoff.py
"""
from __future__ import annotations

import asyncio
import os
import sys

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from band.config import load_agent_config

BASE = "https://app.band.ai"
INCIDENT = (
    "Incident for margaret-01: hard fall detected by the wearable, and NO response "
    "during the 6-second voice check-in. Please assess and escalate if needed."
)


async def main() -> None:
    elder_id, _ = load_agent_config("elder")
    ck_id, ck_key = load_agent_config("caretaker")
    h = {"X-API-Key": ck_key, "Content-Type": "application/json"}

    async with httpx.AsyncClient(base_url=BASE, headers=h, timeout=25, follow_redirects=True) as c:
        # 1) caretaker creates the incident room
        r = await c.post("/api/v1/agent/chats", json={"chat": {"title": "Quietcare Incident — margaret-01"}})
        r.raise_for_status()
        chat_id = r.json()["data"]["id"]
        print(f"room created: {chat_id}")

        # 2) add the elder agent as a participant
        r = await c.post(
            f"/api/v1/agent/chats/{chat_id}/participants",
            json={"participant": {"participant_id": elder_id, "role": "member"}},
        )
        print(f"add elder participant -> {r.status_code}")

        # 3) post the incident, @mentioning the elder so its loop fires
        r = await c.post(
            f"/api/v1/agent/chats/{chat_id}/messages",
            json={
                "message": {
                    "content": f"@a.skinderev/elder {INCIDENT}",
                    "mentions": [
                        {"id": elder_id, "handle": "a.skinderev/elder", "name": "elder", "kind": "mention"}
                    ],
                }
            },
        )
        print(f"kickoff message -> {r.status_code} {r.text[:160]}")

        # 4) poll the room context and print the conversation as it grows
        print("\n--- watching room (up to 90s) ---")
        seen: set[str] = set()
        for _ in range(18):
            await asyncio.sleep(5)
            ctx = await c.get(f"/api/v1/agent/chats/{chat_id}/context", params={"limit": 50})
            if ctx.status_code != 200:
                continue
            for m in ctx.json().get("data", []):
                mid = m.get("id")
                if mid in seen:
                    continue
                seen.add(mid)
                who = (m.get("sender") or {}).get("handle") or m.get("sender_id") or "?"
                mtype = m.get("message_type", "text")
                content = (m.get("content") or "").replace("\n", " ")
                print(f"  [{who}] ({mtype}) {content[:200]}")
        print(f"\nRoom: {BASE[8:]}  chat_id={chat_id}")


if __name__ == "__main__":
    asyncio.run(main())
