"""Live connectivity check for every configured provider credential.

Run:  python scripts/check_keys.py

For each provider it makes the cheapest possible authenticated call and reports
OK / FAIL / SKIPPED (no key). Secrets are never printed. Exit code is non-zero
if any *configured* provider fails its check.
"""

from __future__ import annotations

import asyncio
import os
import sys

import httpx

# Ensure the server/ root (which contains the `app` package) is importable
# regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings


class Check:
    def __init__(self, name: str) -> None:
        self.name = name
        self.status = "SKIPPED"
        self.detail = "not configured"

    def ok(self, detail: str) -> "Check":
        self.status, self.detail = "OK", detail
        return self

    def fail(self, detail: str) -> "Check":
        self.status, self.detail = "FAIL", detail
        return self


async def check_palebluedot() -> Check:
    c = Check("PaleBlueDot (Claude)")
    if not settings.has_palebluedot:
        return c
    base = settings.palebluedot_base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{base}/models",
                headers={
                    "Authorization": f"Bearer {settings.palebluedot_api_key}",
                    "x-api-key": settings.palebluedot_api_key,
                },
            )
        if r.status_code == 200:
            data = r.json()
            ids = [m.get("id") or m.get("name") for m in data.get("data", [])]
            return c.ok(f"{len(ids)} model(s): {', '.join(ids) or 'n/a'}")
        return c.fail(f"HTTP {r.status_code}")
    except Exception as exc:
        return c.fail(repr(exc)[:120])


async def check_redis() -> Check:
    c = Check("Redis (memory)")
    if not settings.has_redis:
        return c
    try:
        import redis.asyncio as redis

        r = redis.from_url(settings.redis_url, decode_responses=True)
        pong = await r.ping()
        await r.aclose()
        return c.ok(f"PING -> {pong}")
    except Exception as exc:
        return c.fail(repr(exc)[:120])


async def check_twilio() -> Check:
    c = Check("Twilio (telephony)")
    if not settings.has_twilio:
        return c
    sid = settings.twilio_account_sid
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json",
                auth=(sid, settings.twilio_auth_token),
            )
        if r.status_code == 200:
            name = r.json().get("friendly_name", "account")
            return c.ok(f"account '{name}' reachable")
        return c.fail(f"HTTP {r.status_code}")
    except Exception as exc:
        return c.fail(repr(exc)[:120])


async def check_deepgram() -> Check:
    c = Check("Deepgram (voice)")
    if not settings.has_deepgram:
        return c
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://api.deepgram.com/v1/projects",
                headers={"Authorization": f"Token {settings.deepgram_api_key}"},
            )
        if r.status_code == 200:
            n = len(r.json().get("projects", []))
            return c.ok(f"{n} project(s) reachable")
        return c.fail(f"HTTP {r.status_code}")
    except Exception as exc:
        return c.fail(repr(exc)[:120])


async def check_band() -> Check:
    c = Check("BAND (message bus)")
    if not settings.has_band:
        return c
    base = (settings.band_rest_url or "https://app.band.ai").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(
                f"{base}/api/v1/agent/me",
                headers={"X-API-Key": settings.band_api_key},
            )
        if r.status_code == 200:
            handle = r.json().get("data", {}).get("handle", "?")
            return c.ok(f"authenticated as {handle}")
        return c.fail(f"auth failed (HTTP {r.status_code})")
    except Exception as exc:
        return c.fail(repr(exc)[:120])


async def check_sentry() -> Check:
    c = Check("Sentry (errors)")
    if not settings.has_sentry:
        return c
    try:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.0)
        eid = sentry_sdk.capture_message("Quietcare check_keys connectivity test")
        sentry_sdk.flush(timeout=10)
        return c.ok(f"event sent (id={eid})")
    except Exception as exc:
        return c.fail(repr(exc)[:120])


async def main() -> int:
    checks = await asyncio.gather(
        check_palebluedot(),
        check_redis(),
        check_twilio(),
        check_deepgram(),
        check_band(),
        check_sentry(),
    )
    width = max(len(c.name) for c in checks)
    print("\n=== Quietcare provider key check ===")
    for c in checks:
        mark = {"OK": "✅", "FAIL": "❌", "SKIPPED": "⚪"}[c.status]
        print(f"{mark} {c.name.ljust(width)}  {c.status:<7} {c.detail}")
    failed = [c for c in checks if c.status == "FAIL"]
    print(f"\n{len(failed)} failed, "
          f"{sum(c.status == 'OK' for c in checks)} ok, "
          f"{sum(c.status == 'SKIPPED' for c in checks)} skipped.\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
