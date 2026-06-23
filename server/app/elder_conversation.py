from __future__ import annotations

import json
import re
from typing import Any

from .escalation_flow import call_caretaker_with_emergency_fallback
from .providers.factory import Providers

WAKE_RE = re.compile(r"\b(quiet\s*care|quietcare|hey\s+quiet\s*care|hey\s+quietcare)\b", re.I)
HELP_RE = re.compile(
    r"\b(help|emergency|hurt|injured|fallen|fell|can't get up|cannot get up|cant get up|call jack|call caretaker|call someone|call 911)\b",
    re.I,
)

CONVERSATION_SYSTEM = (
    "You are Quietcare, an always-on voice companion for an elderly person. "
    "Reply warmly in one or two short spoken sentences. Use plain language. "
    "If the user sounds confused, gently orient them. If they ask for medical, "
    "safety, or urgent help, tell them you are getting their caretaker and keep "
    "the response calm. Never claim you called 911 directly."
)


def wants_attention(transcript: str) -> bool:
    return bool(WAKE_RE.search(transcript) or HELP_RE.search(transcript))


def is_help_request(transcript: str) -> bool:
    return bool(HELP_RE.search(transcript))


def strip_wake_phrase(transcript: str) -> str:
    cleaned = WAKE_RE.sub("", transcript).strip(" ,.!?")
    return cleaned or transcript.strip()


async def handle_elder_conversation(
    *,
    providers: Providers,
    elder_id: str,
    transcript: str,
    auto_emergency_fallback: bool,
    caretaker_ack_timeout_seconds: int,
) -> dict[str, Any]:
    utterance = strip_wake_phrase(transcript)
    profile = await providers.memory.get_profile(elder_id)
    events = await providers.memory.get_events(elder_id)
    action = "chat"
    escalation = None

    if is_help_request(transcript):
        action = "escalated"
        reply_text = "I hear you. I’m getting your caretaker now. Stay where you are if you can."
        summary = f"Voice help request from {elder_id}: {utterance}"
        await providers.memory.log_event(
            elder_id,
            {
                "kind": "voice_help_request",
                "transcript": transcript,
                "summary": summary,
                "outcome": "escalating",
            },
        )
        await providers.telephony.send_sms(f"Quietcare voice alert for {elder_id}: {utterance}")
        escalation = await call_caretaker_with_emergency_fallback(
            providers=providers,
            elder_id=elder_id,
            summary=summary,
            severity="high",
            trigger_source="voice",
            hard_fall=bool(re.search(r"\b(fell|fallen|can't get up|cannot get up|cant get up)\b", transcript, re.I)),
            auto_emergency_fallback=auto_emergency_fallback,
            caretaker_ack_timeout_seconds=caretaker_ack_timeout_seconds,
        )
    else:
        user_prompt = (
            f"Elder id: {elder_id}\n"
            f"Profile: {json.dumps(profile or {})}\n"
            f"Recent events: {json.dumps(events[-5:])}\n"
            f"The elder said: {utterance}\n"
            "Answer as a brief spoken response."
        )
        result = await providers.llm.run(CONVERSATION_SYSTEM, [{"role": "user", "content": user_prompt}], [])
        reply_text = result.text.strip() or "I’m here with you."
        await providers.memory.log_event(
            elder_id,
            {
                "kind": "voice_conversation",
                "transcript": transcript,
                "reply": reply_text,
            },
        )

    audio_b64 = await providers.voice.synthesize(reply_text)
    return {
        "action": action,
        "transcript": transcript,
        "reply_text": reply_text,
        "audio_b64": audio_b64,
        "escalation": escalation,
    }
