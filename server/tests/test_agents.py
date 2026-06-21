"""End-to-end agent-flow tests with mock providers (no network).

Drives the real handle_trigger orchestration + caretaker bus service using the
deterministic MockLLM, asserting the FSM outcome and telephony side effects for
both the "fine" and "emergency" scenarios. Also verifies the 911 hard gate at
the agent/dispatch layer.

Run with:  python -m unittest discover -s tests
"""

import asyncio
import base64
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.caretaker import run_caretaker_agent
from app.providers.bus import InProcessBus
from app.providers.factory import Providers
from app.providers.llm import LLM, LLMResult, MockLLM, ToolCall
from app.providers.memory import MockMemory
from app.providers.telephony import MockTelephony, TelephonyResult
from app.providers.voice import MockVoice
from app.session import (
    CaretakerService,
    ElderSession,
    SessionRegistry,
    handle_trigger,
)
from app.protocol import TriggerMessage
from app.state_machine import State


def _b64(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


class RecordingTelephony(MockTelephony):
    def __init__(self) -> None:
        super().__init__()
        self.sms: list[str] = []
        self.calls: list[str] = []

    async def send_sms(self, text: str) -> TelephonyResult:
        self.sms.append(text)
        return await super().send_sms(text)

    async def call_voice(self, summary: str) -> TelephonyResult:
        self.calls.append(summary)
        return await super().call_voice(summary)


class AutoRespondWS:
    """Fake websocket that answers each `listen` frame with a fixed transcript
    (encoded as a mock-voice scenario hint), after the session starts awaiting."""

    def __init__(self, transcript: str) -> None:
        self.transcript = transcript
        self.sent: list[dict] = []
        self.session: ElderSession | None = None

    async def send_text(self, text: str) -> None:
        msg = json.loads(text)
        self.sent.append(msg)
        if msg.get("type") == "listen":
            asyncio.create_task(self._respond(msg["prompt_id"]))

    async def _respond(self, prompt_id: str) -> None:
        for _ in range(200):
            if self.session and prompt_id in self.session._pending:
                clip = _b64(f"QC-SCENARIO-TRANSCRIPT: {self.transcript}")
                self.session.on_audio_response(prompt_id, clip)
                return
            await asyncio.sleep(0.005)


def _build(transcript: str):
    telephony = RecordingTelephony()
    providers = Providers(
        llm=MockLLM(),
        voice=MockVoice(),
        memory=MockMemory(),
        telephony=telephony,
        bus=InProcessBus(),
    )
    registry = SessionRegistry()
    caretaker = CaretakerService(providers, registry)
    caretaker.attach()
    ws = AutoRespondWS(transcript)
    session = ElderSession(ws, "margaret-01", providers)
    ws.session = session
    registry.set("margaret-01", session)
    return session, ws, telephony, caretaker


class TestElderFlow(unittest.IsolatedAsyncioTestCase):
    async def test_fine_scenario_resolves_without_telephony(self):
        session, ws, telephony, _ = _build("I'm fine, I just dropped the remote")
        trigger = TriggerMessage(
            type="trigger", elder_id="margaret-01", trigger_source="manual"
        )
        await handle_trigger(session, trigger)
        self.assertEqual(session.fsm.state, State.RESOLVED)
        self.assertEqual(telephony.sms, [])
        self.assertEqual(telephony.calls, [])
        # A check-in actually happened (speak + listen frames were sent).
        types = [m["type"] for m in ws.sent]
        self.assertIn("speak", types)
        self.assertIn("listen", types)

    async def test_emergency_scenario_escalates_and_alerts(self):
        session, ws, telephony, caretaker = _build("[silence]")
        trigger = TriggerMessage(
            type="trigger", elder_id="margaret-01", trigger_source="fall"
        )
        await handle_trigger(session, trigger)
        # Caretaker was notified; SMS + (high severity) call fired.
        self.assertEqual(session.fsm.state, State.CARETAKER_NOTIFIED)
        self.assertEqual(len(telephony.sms), 1)
        self.assertEqual(len(telephony.calls), 1)
        self.assertIsNotNone(caretaker.last_result)


class Scripted911LLM(LLM):
    """An adversarial LLM that tries to call escalate_911 autonomously."""

    name = "scripted-911"

    def __init__(self, human_confirmed: bool) -> None:
        self._human_confirmed = human_confirmed
        self._fired = False

    async def run(self, system, messages, tools):
        if not self._fired:
            self._fired = True
            tc = ToolCall(
                id="t0",
                name="escalate_911",
                input={"reason": "no response", "human_confirmed": self._human_confirmed},
            )
            return LLMResult(
                content=[{"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.input}],
                tool_calls=[tc],
                stop_reason="tool_use",
            )
        return LLMResult(content=[{"type": "text", "text": "done"}], text="done", stop_reason="end_turn")


class Test911Gate(unittest.IsolatedAsyncioTestCase):
    async def _run(self, human_confirmed: bool):
        telephony = RecordingTelephony()
        providers = Providers(
            llm=Scripted911LLM(human_confirmed),
            voice=MockVoice(),
            memory=MockMemory(),
            telephony=telephony,
            bus=InProcessBus(),
        )
        ws = AutoRespondWS("[silence]")
        session = ElderSession(ws, "margaret-01", providers)
        ws.session = session
        # Put the FSM where the caretaker agent runs (post-escalation).
        session.fsm.trigger()
        session.fsm.begin_checkin()
        session.fsm.escalate()
        session.fsm.caretaker_notified()
        msg = {"topic": "caretaker.notify", "elder_id": "margaret-01",
               "severity": "high", "summary": "s", "evidence": {}}
        await run_caretaker_agent(session, providers.llm, msg)
        return session

    async def test_911_blocked_without_human_confirmation(self):
        session = await self._run(human_confirmed=False)
        self.assertNotEqual(session.fsm.state, State.GATED_911)

    async def test_911_allowed_with_human_confirmation(self):
        session = await self._run(human_confirmed=True)
        self.assertEqual(session.fsm.state, State.GATED_911)


if __name__ == "__main__":
    unittest.main()
