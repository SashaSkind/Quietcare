"""Verify the app-as-elder escalation hook drives the BAND mesh.

Builds BandBus exactly as the app does (app's own BAND identity), with the elder
handle as the @mention target, then publishes an `escalation` — the same call the
caretaker service makes. The running elder daemon should react and @mention the
caretaker daemon. Polls the room and prints the conversation.

Prereq: both daemons running (python -m app.band_mesh.elder / .caretaker).
Run:    python scripts/verify_app_hook.py <elder_handle>
"""
from __future__ import annotations

import asyncio
import os
import sys

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.providers.bus import BandBus

ELDER_HANDLE = sys.argv[1] if len(sys.argv) > 1 else "a.skinderev/elder"


async def main() -> None:
    import time

    bus = BandBus(
        settings.band_api_key,
        settings.band_rest_url,
        room_title=f"Quietcare Incident {int(time.time())}",
        mention_handle=ELDER_HANDLE,
    )
    msg = {
        "topic": "caretaker.notify",  # the real topic the app's escalation tool emits
        "elder_id": "margaret-01",
        "severity": "high",
        "summary": "hard fall detected by the wearable; NO response during the 6-second voice check-in",
        "evidence": {"trigger": "fall", "responded": False, "transcript": "(silence)"},
    }
    print(f"publishing escalation -> @{ELDER_HANDLE}")
    await bus.publish(msg)
    chat_id = bus._chat_id
    print(f"room: {chat_id}")

    h = {"X-API-Key": settings.band_api_key}
    async with httpx.AsyncClient(base_url=(settings.band_rest_url or "https://app.band.ai").rstrip("/"), headers=h, timeout=20, follow_redirects=True) as c:
        print("\n--- watching room (up to 90s) ---")
        seen: set[str] = set()
        for _ in range(18):
            await asyncio.sleep(5)
            r = await c.get(f"/api/v1/agent/chats/{chat_id}/context", params={"limit": 50})
            if r.status_code != 200:
                continue
            for m in r.json().get("data", []):
                mid = m.get("id")
                if mid in seen:
                    continue
                seen.add(mid)
                who = (m.get("sender") or {}).get("handle") or m.get("sender_id") or "?"
                mtype = m.get("message_type", "text")
                content = (m.get("content") or "").replace("\n", " ")
                print(f"  [{who}] ({mtype}) {content[:200]}")
    await bus._client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
