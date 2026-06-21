"""LLM provider: Anthropic Messages API tool-use loop + a deterministic mock.

The agent loop (see app/agents/base.py) is provider-agnostic. It calls
``LLM.run(system, messages, tools)`` once per turn; the provider returns the
assistant turn as Anthropic-style content blocks plus a parsed list of tool
calls. The mock implements a scripted, data-driven policy so the full system
runs end-to-end with no API key.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class LLMResult:
    content: list[dict[str, Any]]  # assistant content blocks (Anthropic shape)
    tool_calls: list[ToolCall] = field(default_factory=list)
    text: str = ""
    stop_reason: str = "end_turn"


class LLM(ABC):
    name: str = "llm"

    @abstractmethod
    async def run(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResult:
        ...


# --------------------------------------------------------------------------- #
# Real Anthropic implementation
# --------------------------------------------------------------------------- #
class AnthropicLLM(LLM):
    name = "anthropic"

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        from anthropic import AsyncAnthropic  # lazy import

        self._client = AsyncAnthropic(api_key=api_key, base_url=base_url)
        self._model = model

    async def run(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResult:
        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=messages,
            tools=tools,
        )
        content: list[dict[str, Any]] = []
        tool_calls: list[ToolCall] = []
        text_parts: list[str] = []
        for block in resp.content:
            if block.type == "text":
                content.append({"type": "text", "text": block.text})
                text_parts.append(block.text)
            elif block.type == "tool_use":
                content.append(
                    {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, input=dict(block.input))
                )
        return LLMResult(
            content=content,
            tool_calls=tool_calls,
            text="".join(text_parts),
            stop_reason=resp.stop_reason or "end_turn",
        )


# --------------------------------------------------------------------------- #
# Deterministic mock implementation
# --------------------------------------------------------------------------- #
def _called_tool_names(messages: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for m in messages:
        if m.get("role") != "assistant":
            continue
        content = m.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    names.append(block["name"])
    return names


def _last_tool_result_for(
    messages: list[dict[str, Any]], tool_name: str
) -> str | None:
    """Return the textual tool_result content for the most recent call of
    ``tool_name`` (matched via tool_use_id)."""
    # Map tool_use_id -> tool name from assistant turns.
    id_to_name: dict[str, str] = {}
    for m in messages:
        if m.get("role") == "assistant" and isinstance(m.get("content"), list):
            for block in m["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    id_to_name[block["id"]] = block["name"]
    result: str | None = None
    for m in messages:
        if m.get("role") == "user" and isinstance(m.get("content"), list):
            for block in m["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    if id_to_name.get(block.get("tool_use_id")) == tool_name:
                        c = block.get("content")
                        result = c if isinstance(c, str) else json.dumps(c)
    return result


def _initial_user_text(messages: list[dict[str, Any]]) -> str:
    for m in messages:
        if m.get("role") == "user":
            c = m.get("content")
            if isinstance(c, str):
                return c
            if isinstance(c, list):
                for block in c:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return block.get("text", "")
    return ""


_FINE_HINTS = ("fine", "okay", "i'm ok", "im ok", "dropped", "all good", "no problem")
_EMERGENCY_HINTS = ("can't get up", "cant get up", "help", "hurt", "fell")


def _uid(prefix: str, n: int) -> str:
    return f"{prefix}_{n}"


class MockLLM(LLM):
    """Scripted policy that emulates the two agents' decision-making.

    It detects which agent it is from the available tool names and advances the
    plan based on which tools have already been called and on the transcript
    returned by ``listen_to_elder`` — so behavior is driven by data, not by a
    hard-coded scenario flag.
    """

    name = "mock"

    async def run(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMResult:
        tool_names = {t["name"] for t in tools}
        if "speak_to_elder" in tool_names:
            return self._elder_step(messages)
        if "send_caretaker_sms" in tool_names:
            return self._caretaker_step(messages)
        # No tools: just answer.
        return LLMResult(content=[{"type": "text", "text": "ok"}], text="ok")

    # ---- elder agent policy ----
    def _elder_step(self, messages: list[dict[str, Any]]) -> LLMResult:
        called = _called_tool_names(messages)
        n = len(called)

        if "get_elder_profile" not in called:
            return self._tools(
                [
                    ("get_elder_profile", {}, _uid("t", n)),
                    ("get_recent_events", {}, _uid("t", n + 1)),
                ]
            )

        if "speak_to_elder" not in called:
            return self._tools(
                [
                    (
                        "speak_to_elder",
                        {
                            "text": "Margaret, this is Quietcare. I noticed "
                            "something just now — are you okay?"
                        },
                        _uid("t", n),
                    )
                ]
            )

        if "listen_to_elder" not in called:
            return self._tools(
                [("listen_to_elder", {"duration_ms": 6000}, _uid("t", n))]
            )

        # We have a transcript now; decide.
        transcript = (_last_tool_result_for(messages, "listen_to_elder") or "").lower()
        is_fine = any(h in transcript for h in _FINE_HINTS) and transcript.strip() != ""

        if is_fine:
            if "log_event" not in called:
                return self._tools(
                    [
                        (
                            "log_event",
                            {
                                "event": {
                                    "kind": "checkin_resolved",
                                    "transcript": transcript,
                                    "outcome": "resolved",
                                }
                            },
                            _uid("t", n),
                        )
                    ]
                )
            return LLMResult(
                content=[
                    {
                        "type": "text",
                        "text": "Resolved: Margaret responded and is fine.",
                    }
                ],
                text="Resolved: Margaret responded and is fine.",
            )

        # Not fine -> escalate.
        if "notify_caretaker_agent" not in called:
            return self._tools(
                [
                    (
                        "notify_caretaker_agent",
                        {
                            "severity": "high",
                            "summary": "Possible fall; elder did not give a "
                            "clear 'I'm okay' during voice check-in.",
                            "evidence": {
                                "transcript": transcript or "[silence]",
                                "responded": bool(transcript.strip()),
                            },
                        },
                        _uid("t", n),
                    )
                ]
            )
        if "log_event" not in called:
            return self._tools(
                [
                    (
                        "log_event",
                        {
                            "event": {
                                "kind": "checkin_escalated",
                                "transcript": transcript or "[silence]",
                                "outcome": "escalating",
                            }
                        },
                        _uid("t", n),
                    )
                ]
            )
        return LLMResult(
            content=[
                {"type": "text", "text": "Escalated: notified caretaker agent."}
            ],
            text="Escalated: notified caretaker agent.",
        )

    # ---- caretaker agent policy ----
    def _caretaker_step(self, messages: list[dict[str, Any]]) -> LLMResult:
        called = _called_tool_names(messages)
        n = len(called)
        intro = _initial_user_text(messages).lower()
        high = "high" in intro

        if "get_elder_profile" not in called:
            return self._tools([("get_elder_profile", {}, _uid("c", n))])

        if "send_caretaker_sms" not in called:
            return self._tools(
                [
                    (
                        "send_caretaker_sms",
                        {
                            "text": "Quietcare alert for Margaret: possible fall, "
                            "no clear response during check-in. Please check on "
                            "her now."
                        },
                        _uid("c", n),
                    )
                ]
            )

        if high and "call_caretaker_voice" not in called:
            return self._tools(
                [
                    (
                        "call_caretaker_voice",
                        {
                            "summary": "Possible fall for Margaret with no clear "
                            "response. Placing a voice call to the caretaker."
                        },
                        _uid("c", n),
                    )
                ]
            )

        return LLMResult(
            content=[
                {"type": "text", "text": "Caretaker notified via Twilio."}
            ],
            text="Caretaker notified via Twilio.",
        )

    # ---- helper ----
    @staticmethod
    def _tools(calls: list[tuple[str, dict[str, Any], str]]) -> LLMResult:
        content: list[dict[str, Any]] = []
        tool_calls: list[ToolCall] = []
        for name, inp, cid in calls:
            content.append(
                {"type": "tool_use", "id": cid, "name": name, "input": inp}
            )
            tool_calls.append(ToolCall(id=cid, name=name, input=inp))
        return LLMResult(content=content, tool_calls=tool_calls, stop_reason="tool_use")
