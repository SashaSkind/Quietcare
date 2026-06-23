"""Elder-agent: reasons about an event, runs a voice check-in, decides outcome."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from ..providers.llm import LLM
from .base import run_agent

if TYPE_CHECKING:
    from ..session import ElderSession

logger = logging.getLogger("quietcare.agent.elder")

ELDER_SYSTEM = (
    "You are Quietcare's elder-agent, a calm, caring safety companion for an "
    "elderly person living alone. When a trigger arrives you: (1) pull the "
    "elder's profile and recent events, (2) run a brief spoken check-in using "
    "speak_to_elder then listen_to_elder, and (3) FUSE the signals — the "
    "trigger source, what you hear back, and whether they responded at all — "
    "into a decision. Use get_acoustic_evidence to factor in non-speech sounds "
    "(thud, scream, groan, glass) detected on the trigger clip and check-in. "
    "If they clearly say they're fine and there's no acoustic distress, log the "
    "event and stop. If they don't respond clearly, indicate distress, or the "
    "audio shows a thud/scream with no reassuring reply, call "
    "notify_caretaker_agent with severity and evidence. Never call 911 yourself.\n"
    "Trigger types you may see: 'fall' (impact detected); 'inactivity' (no "
    "expected motion — treat as a possible SILENT emergency like a stroke, do a "
    "check-in, and escalate if there's no clear, coherent response); 'geofence' "
    "(the person appears to have left a safe zone / may be wandering — they are "
    "likely not near the device, so a voice check-in may go unanswered; notify "
    "the caretaker, with HIGHER severity at night)."
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
        "name": "get_acoustic_evidence",
        "description": (
            "Return non-speech audio-scene tags (e.g. Thud, Screaming, Groan) "
            "detected on the trigger clip and the latest check-in response."
        ),
        "input_schema": {"type": "object", "properties": {}},
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

        if name == "get_acoustic_evidence":
            return json.dumps(session.acoustic_evidence or {"note": "no audio analyzed"})

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
            response = await session.await_audio_response(prompt_id)
            audio_b64 = response.get("audio_b64")
            transcript = (response.get("transcript") or "").strip()
            if not transcript:
                transcript = await p.voice.transcribe(audio_b64)
            session.last_transcript = transcript
            # Classify non-speech sounds in the response for the decision fusion.
            scene = await p.audio_scene.classify(audio_b64)
            session.acoustic_evidence["last_checkin"] = scene.to_dict()
            return json.dumps(
                {"transcript": transcript, "acoustic": scene.to_dict()}
            )

        if name == "log_event":
            await p.memory.log_event(elder_id, args.get("event", {}))
            return "event logged"

        if name == "notify_caretaker_agent":
            severity = args.get("severity", "high")
            summary = args.get("summary", "")
            evidence = args.get("evidence", {})
            # Policy gate: an escalation may not fire without sanction (the gate
            # also computes a risk score from these signals).
            decision = await p.policy_gate.sanction(
                "escalation",
                {
                    "elder_id": elder_id,
                    "severity": severity,
                    "summary": summary,
                    "trigger_source": session.trigger_source,
                    "hard_fall": session.hard_fall,
                },
            )
            if not decision.allowed:
                logger.warning(
                    "escalation BLOCKED by policy gate for %s: %s",
                    elder_id,
                    decision.reason,
                )
                return f"BLOCKED by policy gate: {decision.reason}"
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

    context_bits = ""
    if session.trigger_note:
        context_bits += f" Note: {session.trigger_note}."
    if session.trigger_location:
        context_bits += f" Location: {json.dumps(session.trigger_location)}."
    user_prompt = (
        f"A '{session.trigger_source}' trigger just arrived for elder "
        f"'{elder_id}'. Device state: {json.dumps(session.device_state)}."
        f"{context_bits} Assess the situation and run a check-in."
    )
    return await run_agent(
        llm=llm,
        system=ELDER_SYSTEM,
        user_prompt=user_prompt,
        tools=ELDER_TOOLS,
        dispatch=dispatch,
        label="elder-agent",
    )
