"""Everyday-care channel: a caretaker texts the Twilio number ("how's mom
today?") and gets a warm, plain-language recap built from the elder's profile +
recent incident history. Read-only and entirely off the emergency path.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

logger = logging.getLogger("quietcare.caretaker_query")

CARETAKER_QUERY_SYSTEM = (
    "You are Quietcare's caretaker assistant, replying by SMS to a family "
    "caretaker. In 1-2 short, warm, plain-language sentences (SMS length), "
    "answer their question about their loved one using ONLY the profile and "
    "recent incident history provided. Be reassuring and concrete; never invent "
    "events. If there were no recent incidents, say so plainly."
)


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _phones_match(a: str, b: str) -> bool:
    da, db = _digits(a), _digits(b)
    if not da or not db:
        return False
    short, long = (da, db) if len(da) <= len(db) else (db, da)
    # Match on the last 7+ digits to tolerate country-code / formatting differences.
    return len(short) >= 7 and long.endswith(short)


async def resolve_elder_by_caretaker(memory, from_number: str) -> Optional[str]:
    """Find the elder whose caretaker phone matches the SMS sender."""
    for elder_id in await memory.list_elders():
        profile = await memory.get_profile(elder_id) or {}
        phone = (profile.get("caretaker") or {}).get("phone", "")
        if _phones_match(phone, from_number):
            return elder_id
    return None


async def summarize_for_caretaker(providers, elder_id: str, question: str) -> str:
    """Produce a short SMS recap for the caretaker's question."""
    memory = providers.memory
    profile = await memory.get_profile(elder_id) or {"elder_id": elder_id}
    events = await memory.get_events(elder_id)
    incidents = [
        e for e in events if isinstance(e, dict) and e.get("kind") == "incident"
    ][-5:]
    name = profile.get("name", elder_id)

    user = (
        f"Caretaker question: {question}\n\n"
        f"Elder profile: {json.dumps(profile)}\n\n"
        f"Recent incidents (most recent last): {json.dumps(incidents)}"
    )
    try:
        result = await providers.llm.run(
            CARETAKER_QUERY_SYSTEM, [{"role": "user", "content": user}], []
        )
        text = (result.text or "").strip()
    except Exception as exc:  # pragma: no cover - llm/network
        logger.warning("caretaker query LLM failed (%s)", exc)
        text = ""

    if text:
        return text
    # Deterministic fallback if the LLM is unavailable/empty.
    if not incidents:
        return f"{name} is doing well today — no incidents logged recently."
    last = incidents[-1]
    state = last.get("final_state", "unknown")
    return f"{name}: latest check-in ended '{state}'. No new alerts. I'll text you if anything changes."
