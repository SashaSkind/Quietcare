"""Elder-agent: reasons about an event, runs a voice check-in, decides outcome."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from ..providers.llm import LLM
from .base import run_agent

if TYPE_CHECKING:
    from ..session import ElderSession

ELDER_SYSTEM = (
    "You are Quietcare's elder-agent, a calm, caring safety companion for an "
    "elderly person living alone. When a trigger arrives you: (1) pull the "
    "elder's profile and recent events, (2) run a brief spoken check-in using "
    "speak_to_elder then listen_to_elder, and (3) FUSE the signals — the "
    "trigger source, what you hear back, and whether they responded at all — "
    "into a decision. If they clearly say they're fine, log the event and stop. "
    "If they don't respond clearly or indicate distress, call "
    "notify_caretaker_agent with severity and evidence. Never call 911 yourself."
)

ELDER_TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_elder_profile",
        "description": "Fetch the elder's stored profile (age, meds, history).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_recent_events",
        "description": "Fetch recent logged events for this elder.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "speak_to_elder",
        "description": "Synthesize speech (TTS) and play it on the device.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "listen_to_elder",
        "description": (
            "Record the elder for duration_ms and return the transcript "
            "(empty string means silence / no response)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"duration_ms": {"type": "integer"}},
            "required": ["duration_ms"],
        },
    },
    {
        "name": "log_event",
        "description": "Persist a structured event to the elder's memory.",
        "input_schema": {
            "type": "object",
            "properties": {"event": {"type": "object"}},
            "required": ["event"],
        },
    },
    {
        "name": "notify_caretaker_agent",
        "description": (
            "Publish an escalation to the caretaker-agent over the bus."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                "summary": {"type": "string"},
                "evidence": {"type": "object"},
            },
            "required": ["severity", "summary"],
        },
    },
]


async def run_elder_agent(session: "ElderSession", llm: LLM) -> str:
    p = session.providers
    elder_id = session.elder_id

    async def dispatch(name: str, args: dict[str, Any]) -> str:
        if name == "get_elder_profile":
            profile = await p.memory.get_profile(elder_id)
            return json.dumps(profile or {"elder_id": elder_id, "note": "no profile"})

        if name == "get_recent_events":
            events = await p.memory.get_events(elder_id)
            return json.dumps(events)

        if name == "speak_to_elder":
            text = args["text"]
            await session.begin_checkin_once()
            audio_b64 = await p.voice.synthesize(text)
            prompt_id = session.new_prompt_id()
            await session.send_speak(prompt_id, audio_b64, text)
            return f"spoke to elder (prompt {prompt_id}): {text}"

        if name == "listen_to_elder":
            duration_ms = int(args.get("duration_ms", 6000))
            prompt_id = session.current_prompt_id or session.new_prompt_id()
            await session.send_listen(prompt_id, duration_ms)
            audio_b64 = await session.await_audio_response(prompt_id)
            transcript = await p.voice.transcribe(audio_b64)
            session.last_transcript = transcript
            return transcript

        if name == "log_event":
            await p.memory.log_event(elder_id, args.get("event", {}))
            return "event logged"

        if name == "notify_caretaker_agent":
            severity = args.get("severity", "high")
            summary = args.get("summary", "")
            evidence = args.get("evidence", {})
            await session.escalate(hard_fall=session.hard_fall)
            await p.bus.publish(
                {
                    "topic": "caretaker.notify",
                    "elder_id": elder_id,
                    "severity": severity,
                    "summary": summary,
                    "evidence": evidence,
                }
            )
            return "caretaker agent notified over bus"

        return f"unknown tool: {name}"

    user_prompt = (
        f"A '{session.trigger_source}' trigger just arrived for elder "
        f"'{elder_id}'. Device state: {json.dumps(session.device_state)}. "
        "Assess the situation and run a check-in."
    )
    return await run_agent(
        llm=llm,
        system=ELDER_SYSTEM,
        user_prompt=user_prompt,
        tools=ELDER_TOOLS,
        dispatch=dispatch,
        label="elder-agent",
    )
