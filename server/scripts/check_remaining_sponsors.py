"""Live check for sponsors not covered by check_keys.py: Browserbase, ArmorIQ, Arize.

Run:  python scripts/check_remaining_sponsors.py
Makes the cheapest authenticated call per provider; secrets never printed.
"""
from __future__ import annotations

import asyncio
import os
import sys

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings as s


async def main() -> None:
    print("=== capability flags ===")
    for f in [
        "has_palebluedot", "has_anthropic", "has_deepgram", "has_redis",
        "has_twilio", "has_band", "has_browserbase", "has_armoriq",
        "has_arize", "has_sentry", "has_yamnet",
    ]:
        print(f"  {f:18} {getattr(s, f)}")

    print("\n=== Browserbase (browser) ===")
    if s.has_browserbase:
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.post(
                    "https://api.browserbase.com/v1/sessions",
                    headers={"X-BB-API-Key": s.browserbase_api_key, "Content-Type": "application/json"},
                    json={"projectId": s.browserbase_project_id},
                )
            ok = r.status_code in (200, 201)
            print(f"  session create -> {r.status_code} {'OK' if ok else r.text[:120]}")
        except Exception as e:
            print("  ERROR", repr(e)[:120])
    else:
        print("  SKIPPED (not configured)")

    print("\n=== ArmorIQ (security scan) ===")
    if s.has_armoriq:
        base = s.armoriq_base_url.rstrip("/")
        try:
            async with httpx.AsyncClient(
                timeout=25, headers={"Authorization": f"Bearer {s.armoriq_api_key}"}, follow_redirects=True
            ) as c:
                r = await c.post(base + "/scan", json={"url": "https://example.com"})
            print(f"  POST /scan -> {r.status_code}")
            print("  body:", r.text[:240].replace("\n", " "))
        except Exception as e:
            print("  ERROR", repr(e)[:120])
    else:
        print("  SKIPPED (not configured)")

    print("\n=== Arize (observability) ===")
    print(f"  has_arize: {s.has_arize} | project: {s.arize_project_name}")


if __name__ == "__main__":
    asyncio.run(main())
