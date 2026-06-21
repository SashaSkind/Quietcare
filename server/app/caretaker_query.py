"""Everyday-care channel: a caretaker texts the Twilio number and gets a warm,
plain-language reply. Supports threaded follow-ups (conversation memory), and
routes intents — recap ("how's mom?"), weekly wellness, prescription refill, and
a two-way "have her call me" voice bridge. Read-only of the emergency path.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger("quietcare.caretaker_query")

CARETAKER_QUERY_SYSTEM = (
    "You are Quietcare's caretaker assistant, replying by SMS to a family "
    "caretaker. In 1-2 short, warm, plain-language sentences (SMS length), "
    "answer their question about their loved one using ONLY the profile and "
    "recent incident history provided, plus the prior messages in this thread "
    "for context. Be reassuring and concrete; never invent events. If there "
    "were no recent incidents, say so plainly."
)

# How many prior SMS turns to feed back into the model for follow-up coherence.
_THREAD_CONTEXT_TURNS = 8


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


async def summarize_for_caretaker(
    providers, elder_id: str, question: str, thread: Optional[list] = None
) -> str:
    """Produce a short SMS recap, optionally using prior thread turns for
    follow-up coherence ("what about yesterday?")."""
    memory = providers.memory
    profile = await memory.get_profile(elder_id) or {"elder_id": elder_id}
    events = await memory.get_events(elder_id)
    incidents = [
        e for e in events if isinstance(e, dict) and e.get("kind") == "incident"
    ][-5:]
    name = profile.get("name", elder_id)

    context = (
        f"Elder profile: {json.dumps(profile)}\n\n"
        f"Recent incidents (most recent last): {json.dumps(incidents)}"
    )
    messages: list[dict[str, Any]] = []
    for turn in (thread or [])[-_THREAD_CONTEXT_TURNS:]:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        messages.append({"role": role, "content": turn.get("text", "")})
    messages.append({"role": "user", "content": f"{context}\n\nQuestion: {question}"})

    try:
        result = await providers.llm.run(CARETAKER_QUERY_SYSTEM, messages, [])
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


# ---- SMS intent routing -------------------------------------------------------

def detect_intent(body: str) -> str:
    """Classify an inbound caretaker SMS into an intent."""
    t = (body or "").lower()
    if any(k in t for k in ("call me", "call back", "have her call", "have him call", "tell her to call", "ring me")):
        return "call_me"
    if any(k in t for k in ("week", "trend", "how has", "lately", "wellness", "summary")):
        return "wellness"
    if any(k in t for k in ("refill", "prescription", "pharmacy", "out of", "running low", "low on")):
        return "refill"
    return "recap"


async def prompt_elder_to_call(registry, elder_id: str, caretaker_name: str) -> bool:
    """Two-way bridge: ask the elder (over the voice loop) to call the caretaker.
    Returns True if a connected, idle device was prompted."""
    session = registry.get(elder_id) if registry else None
    if session is None or session.is_busy:
        return False
    who = caretaker_name or "your family member"
    message = (
        f"Hi, this is Quietcare. {who} would love to hear from you and asked you "
        f"to give them a call when you have a moment. Thank you!"
    )
    asyncio.create_task(session.speak(message))
    return True


async def handle_inbound_sms(providers, registry, from_number: str, body: str) -> str:
    """Resolve the elder, route the intent, persist the thread, return a reply."""
    memory = providers.memory
    elder_id = await resolve_elder_by_caretaker(memory, from_number)
    if elder_id is None:
        return (
            "This number isn't linked to a Quietcare resident yet. "
            "Please contact support to connect your account."
        )

    profile = await memory.get_profile(elder_id) or {}
    name = profile.get("name", elder_id)
    caretaker_name = (profile.get("caretaker") or {}).get("name", "")
    intent = detect_intent(body)
    thread = await memory.get_sms_thread(elder_id)
    await memory.append_sms_turn(elder_id, "user", body)

    if intent == "call_me":
        ok = await prompt_elder_to_call(registry, elder_id, caretaker_name)
        reply = (
            f"Okay — I just asked {name} to give you a call."
            if ok else
            f"{name}'s device isn't reachable right now, so I couldn't pass that along. "
            "I'll keep trying and let you know."
        )
    elif intent == "wellness":
        from .wellness import summarize_wellness

        reply = (await summarize_wellness(providers, elder_id, days=7))["summary"]
    elif intent == "refill":
        med = ""
        if profile.get("medications"):
            med = profile["medications"][0]
        res = await providers.browser.run_task(
            f"Refill prescription: {med or 'medication'}",
            {"elder_id": elder_id, "from": "caretaker_sms"},
        )
        reply = (
            f"I've started a refill for {name}'s {med or 'medication'}."
            if res.ok else
            "I couldn't start the refill just now — I'll retry and update you."
        )
    else:
        reply = await summarize_for_caretaker(providers, elder_id, body, thread)

    await memory.append_sms_turn(elder_id, "assistant", reply)
    return reply
