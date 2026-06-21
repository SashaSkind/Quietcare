"""Medication reminders + adherence.

A scheduled, spoken reminder ("Margaret, time for your 2pm blood-pressure pill")
that listens for a confirmation. A confirmed dose and a missed dose are both
logged as soft events (kind="medication") — no emergency escalation. This makes
the device useful every day, not only in emergencies.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("quietcare.medications")

_CONFIRM_WORDS = ("yes", "yeah", "yep", "took", "taken", "done", "did", "ok", "okay", "sure")
_DENY_WORDS = ("no", "not yet", "later", "haven't", "havent", "skip", "forgot")


def parse_hhmm(value: str) -> Optional[tuple[int, int]]:
    try:
        h, m = value.strip().split(":")
        h, m = int(h), int(m)
        if 0 <= h < 24 and 0 <= m < 60:
            return h, m
    except Exception:
        pass
    return None


def due_medications(
    meds: list[dict[str, Any]], now: datetime, already_fired: set[str]
) -> list[dict[str, Any]]:
    """Return meds scheduled for the current minute that haven't fired today.

    ``already_fired`` holds dedup keys "name@HH:MM@YYYY-MM-DD".
    """
    due: list[dict[str, Any]] = []
    date = now.strftime("%Y-%m-%d")
    for med in meds:
        hhmm = parse_hhmm(str(med.get("time", "")))
        if hhmm is None:
            continue
        h, m = hhmm
        if now.hour == h and now.minute == m:
            key = f"{med.get('name')}@{med['time']}@{date}"
            if key not in already_fired:
                due.append(med)
    return due


def fired_key(med: dict[str, Any], now: datetime) -> str:
    return f"{med.get('name')}@{med.get('time')}@{now.strftime('%Y-%m-%d')}"


def confirmation_from_transcript(transcript: str) -> Optional[bool]:
    """True=confirmed, False=denied, None=unclear/silence."""
    t = (transcript or "").lower()
    if not t.strip():
        return None
    if any(w in t for w in _DENY_WORDS):
        return False
    if any(w in t for w in _CONFIRM_WORDS):
        return True
    return None


def adherence_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate medication events into confirmed/missed counts + rate."""
    med_events = [e for e in events if isinstance(e, dict) and e.get("kind") == "medication"]
    confirmed = sum(1 for e in med_events if e.get("status") == "confirmed")
    missed = sum(1 for e in med_events if e.get("status") == "missed")
    total = confirmed + missed
    return {
        "confirmed": confirmed,
        "missed": missed,
        "total": total,
        "adherence_rate": round(confirmed / total, 2) if total else None,
    }


async def run_medication_reminder(
    session: Any, med: dict[str, Any], confirm_window_ms: int = 8000
) -> dict[str, Any]:
    """Speak a reminder, listen for confirmation, and log an adherence event."""
    name = med.get("name", "your medication")
    dose = med.get("dose")
    dose_str = f" ({dose})" if dose else ""
    prompt = (
        f"Hi, this is your Quietcare reminder. It's time for {name}{dose_str}. "
        "Have you taken it? Please say yes or no."
    )
    try:
        transcript = await session.speak_and_listen(prompt, confirm_window_ms)
    except Exception as exc:  # pragma: no cover - transport
        logger.warning("med reminder transport failed (%s)", exc)
        transcript = ""

    confirmed = confirmation_from_transcript(transcript)
    status = "confirmed" if confirmed else "missed"
    event = {
        "kind": "medication",
        "ts": datetime.now(timezone.utc).isoformat(),
        "medication": name,
        "scheduled_time": med.get("time"),
        "status": status,
        "transcript": transcript,
    }
    await session.providers.memory.log_event(session.elder_id, event)
    logger.info("medication reminder %s -> %s (%r)", name, status, transcript)
    return event


class MedicationService:
    """Background scheduler that fires due medication reminders for connected
    elders. Dedups by (med, time, date) so a reminder fires once per day."""

    def __init__(self, providers: Any, registry: Any, settings: Any) -> None:
        self.providers = providers
        self.registry = registry
        self.settings = settings
        self._fired: set[str] = set()

    async def tick(self, now: Optional[datetime] = None) -> list[dict[str, Any]]:
        now = now or datetime.now()
        results: list[dict[str, Any]] = []
        for elder_id in await self.providers.memory.list_elders():
            meds = await self.providers.memory.get_medications(elder_id)
            for med in due_medications(meds, now, self._fired):
                self._fired.add(fired_key(med, now))
                session = self.registry.get(elder_id)
                if session is None or session.is_busy:
                    # No connected device (or mid-incident) -> log a missed dose.
                    event = {
                        "kind": "medication",
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "medication": med.get("name"),
                        "scheduled_time": med.get("time"),
                        "status": "missed",
                        "transcript": "",
                        "note": "device offline or busy",
                    }
                    await self.providers.memory.log_event(elder_id, event)
                    results.append(event)
                    continue
                results.append(
                    await run_medication_reminder(
                        session, med, self.settings.med_confirm_window_ms
                    )
                )
        return results

    async def run_forever(self) -> None:  # pragma: no cover - timing loop
        import asyncio

        interval = max(15, int(self.settings.med_tick_seconds))
        logger.info("medication scheduler started (tick=%ss)", interval)
        while True:
            try:
                await self.tick()
            except Exception as exc:
                logger.warning("medication tick failed (%s)", exc)
            await asyncio.sleep(interval)
