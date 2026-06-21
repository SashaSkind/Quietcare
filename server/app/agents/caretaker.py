"""Caretaker-agent: triages a bus escalation and alerts the human via Twilio."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Optional

from ..providers.llm import LLM
from .base import run_agent

if TYPE_CHECKING:
    from ..confirmations import ConfirmationRegistry
    from ..session import ElderSession

CARETAKER_SYSTEM = (
    "You are Quietcare's caretaker-agent. You receive escalations from the "
    "elder-agent over a message bus. Pull the elder's profile, triage the "
    "severity, and on a real emergency notify the human caretaker via SMS "
    "(send_caretaker_sms) and, for high severity, a voice call "
    "(call_caretaker_voice). You may book a follow-up task. If the situation "
    "appears life-threatening and may warrant emergency services, call "
    "request_911_confirmation — this alerts a human to AUTHORIZE the call; it "
    "does NOT dial emergency services itself. You must NEVER call escalate_911 "
    "autonomously — it is hard-gated and requires explicit human confirmation "
    "delivered out-of-band."
)

CARETAKER_TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_elder_profile",
        "description": "Fetch the elder's stored profile.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "send_caretaker_sms",
        "description": "Send an SMS to the human caretaker (Twilio).",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "call_caretaker_voice",
        "description": "Place a voice call to the human caretaker (Twilio).",
        "input_schema": {
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
    },
    {
        "name": "book_task",
        "description": "Book a follow-up task for the caretaker (stub).",
        "input_schema": {
            "type": "object",
            "properties": {"task": {"type": "object"}},
            "required": ["task"],
        },
    },
    {
        "name": "refill_medication",
        "description": (
            "Hand off an everyday-care errand (e.g. a prescription refill) to a "
            "cloud browser via Browserbase. Off the emergency critical path."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "medication": {"type": "string"},
                "pharmacy_url": {"type": "string"},
            },
            "required": ["medication"],
        },
    },
    {
        "name": "request_911_confirmation",
        "description": (
            "Request human authorization to call emergency services. Alerts the "
            "caretaker with a one-time confirmation link/token. Does NOT dial "
            "911 itself — a human must approve out-of-band."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"],
        },
    },
    {
        "name": "escalate_911",
        "description": (
            "GATED. Initiate a 911 escalation. Requires human_confirmed=true; "
            "never call this autonomously."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
                "human_confirmed": {"type": "boolean"},
            },
            "required": ["reason"],
        },
    },
]


async def run_caretaker_agent(
    session: "ElderSession",
    llm: LLM,
    msg: dict[str, Any],
    confirmations: "Optional[ConfirmationRegistry]" = None,
) -> str:
    p = session.providers
    elder_id = session.elder_id

    async def dispatch(name: str, args: dict[str, Any]) -> str:
        if name == "get_elder_profile":
            profile = await p.memory.get_profile(elder_id)
            return json.dumps(profile or {"elder_id": elder_id})

        if name == "send_caretaker_sms":
            session.caretaker_notified_once()
            res = await p.telephony.send_sms(args["text"])
            return f"sms: ok={res.ok} mocked={res.mocked} ({res.detail})"

        if name == "call_caretaker_voice":
            session.caretaker_notified_once()
            res = await p.telephony.call_voice(args["summary"])
            return f"call: ok={res.ok} mocked={res.mocked} ({res.detail})"

        if name == "book_task":
            return f"task booked (stub): {json.dumps(args.get('task', {}))}"

        if name == "refill_medication":
            medication = args.get("medication", "")
            task = f"Refill prescription: {medication}"
            res = await p.browser.run_task(
                task, {"elder_id": elder_id, "pharmacy_url": args.get("pharmacy_url")}
            )
            return (
                f"refill handoff: ok={res.ok} mocked={res.mocked} ({res.detail})"
                + (f" replay={res.replay_url}" if res.replay_url else "")
            )

        if name == "request_911_confirmation":
            reason = args.get("reason", "")
            if confirmations is None:
                return "confirmation channel unavailable; cannot request 911"
            summary = msg.get("summary", "")
            # Ensure the FSM is in the notified state so a later human approval
            # can legally transition to the gated 911 state.
            session.caretaker_notified_once()
            pc = confirmations.create(elder_id, reason, summary)
            await p.telephony.send_sms(
                f"URGENT: Quietcare may need emergency services for {elder_id}. "
                f"Reason: {reason}. To AUTHORIZE, confirm at "
                f"/incidents/{elder_id}/confirm_911 with token {pc.token}."
            )
            return (
                "human authorization requested (pending). Emergency services will "
                "NOT be contacted until a human approves."
            )

        if name == "escalate_911":
            # Hard gate enforced in the state machine.
            human_confirmed = bool(args.get("human_confirmed", False))
            try:
                session.fsm.gate_911(human_confirmed=human_confirmed)
            except Exception as exc:
                return f"BLOCKED: {exc}"
            return "911 path entered (human confirmed)"

        return f"unknown tool: {name}"

    user_prompt = (
        "Escalation received over the bus:\n"
        f"severity={msg.get('severity')}\n"
        f"summary={msg.get('summary')}\n"
        f"evidence={json.dumps(msg.get('evidence', {}))}\n"
        "Triage and notify the human caretaker appropriately."
    )
    return await run_agent(
        llm=llm,
        system=CARETAKER_SYSTEM,
        user_prompt=user_prompt,
        tools=CARETAKER_TOOLS,
        dispatch=dispatch,
        label="caretaker-agent",
    )
