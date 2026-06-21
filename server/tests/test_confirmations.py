"""Tests for the human-in-the-loop gated 911 confirmation flow.

Covers the ConfirmationRegistry, the caretaker-agent's request_911_confirmation
tool, and the confirm_911 resolution (approve/reject/bad-token) including the
FSM gate + emergency dispatch.

Run with:  python -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.caretaker import run_caretaker_agent
from app.confirmations import ConfirmationRegistry
from app.providers.bus import InProcessBus
from app.providers.factory import Providers
from app.providers.llm import LLM, LLMResult, ToolCall
from app.providers.memory import MockMemory
from app.providers.telephony import MockTelephony, TelephonyResult
from app.providers.voice import MockVoice
from app.session import ElderSession, SessionRegistry, confirm_911
from app.state_machine import State


class FakeWS:
    async def send_text(self, text: str) -> None:
        pass


class RecordingTelephony(MockTelephony):
    def __init__(self) -> None:
        super().__init__()
        self.sms: list[str] = []
        self.emergencies: list[str] = []

    async def send_sms(self, text: str) -> TelephonyResult:
        self.sms.append(text)
        return await super().send_sms(text)

    async def dispatch_emergency(self, summary: str) -> TelephonyResult:
        self.emergencies.append(summary)
        return await super().dispatch_emergency(summary)


class RequestsConfirmationLLM(LLM):
    """Scripted caretaker LLM that calls request_911_confirmation once."""

    name = "scripted-confirm"

    def __init__(self) -> None:
        self._fired = False

    async def run(self, system, messages, tools):
        if not self._fired:
            self._fired = True
            tc = ToolCall(id="t0", name="request_911_confirmation",
                          input={"reason": "unconscious, no response"})
            return LLMResult(
                content=[{"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.input}],
                tool_calls=[tc],
                stop_reason="tool_use",
            )
        return LLMResult(content=[{"type": "text", "text": "done"}], text="done",
                         stop_reason="end_turn")


def _setup():
    telephony = RecordingTelephony()
    providers = Providers(
        llm=RequestsConfirmationLLM(),
        voice=MockVoice(),
        memory=MockMemory(),
        telephony=telephony,
        bus=InProcessBus(),
    )
    registry = SessionRegistry()
    confirmations = ConfirmationRegistry()
    session = ElderSession(FakeWS(), "margaret-01", providers)
    # Drive the FSM to the escalating state (pre-caretaker).
    session.fsm.trigger()
    session.fsm.begin_checkin()
    session.fsm.escalate()
    registry.set("margaret-01", session)
    return providers, registry, confirmations, session, telephony


class TestConfirmationRegistry(unittest.TestCase):
    def test_create_get_resolve(self):
        reg = ConfirmationRegistry()
        pc = reg.create("e1", "reason", "summary")
        self.assertEqual(reg.get("e1").status, "pending")
        resolved = reg.resolve("e1", pc.token, approve=True)
        self.assertEqual(resolved.status, "confirmed")

    def test_bad_token_rejected(self):
        reg = ConfirmationRegistry()
        reg.create("e1", "r", "s")
        with self.assertRaises(PermissionError):
            reg.resolve("e1", "wrong-token", approve=True)

    def test_missing_request_raises(self):
        reg = ConfirmationRegistry()
        with self.assertRaises(KeyError):
            reg.resolve("nope", "t", approve=True)

    def test_double_resolve_raises(self):
        reg = ConfirmationRegistry()
        pc = reg.create("e1", "r", "s")
        reg.resolve("e1", pc.token, approve=True)
        with self.assertRaises(ValueError):
            reg.resolve("e1", pc.token, approve=False)


class TestRequest911Flow(unittest.IsolatedAsyncioTestCase):
    async def test_agent_requests_confirmation_without_dialing(self):
        providers, registry, confirmations, session, telephony = _setup()
        msg = {"topic": "caretaker.notify", "elder_id": "margaret-01",
               "severity": "high", "summary": "fall, unresponsive", "evidence": {}}
        await run_caretaker_agent(session, providers.llm, msg, confirmations)
        # A pending confirmation exists; SMS sent; NO emergency dispatched yet.
        pc = confirmations.get("margaret-01")
        self.assertIsNotNone(pc)
        self.assertEqual(pc.status, "pending")
        self.assertEqual(len(telephony.sms), 1)
        self.assertEqual(telephony.emergencies, [])
        self.assertEqual(session.fsm.state, State.CARETAKER_NOTIFIED)

    async def test_human_approval_gates_and_dispatches(self):
        providers, registry, confirmations, session, telephony = _setup()
        msg = {"topic": "caretaker.notify", "elder_id": "margaret-01",
               "severity": "high", "summary": "fall, unresponsive", "evidence": {}}
        await run_caretaker_agent(session, providers.llm, msg, confirmations)
        token = confirmations.get("margaret-01").token

        result = await confirm_911(
            registry=registry, confirmations=confirmations, providers=providers,
            elder_id="margaret-01", token=token, approve=True,
        )
        self.assertEqual(result["status"], "confirmed")
        self.assertEqual(session.fsm.state, State.GATED_911)
        self.assertEqual(len(telephony.emergencies), 1)

    async def test_human_rejection_does_not_dispatch(self):
        providers, registry, confirmations, session, telephony = _setup()
        msg = {"topic": "caretaker.notify", "elder_id": "margaret-01",
               "severity": "high", "summary": "fall", "evidence": {}}
        await run_caretaker_agent(session, providers.llm, msg, confirmations)
        token = confirmations.get("margaret-01").token

        result = await confirm_911(
            registry=registry, confirmations=confirmations, providers=providers,
            elder_id="margaret-01", token=token, approve=False,
        )
        self.assertEqual(result["status"], "rejected")
        self.assertNotEqual(session.fsm.state, State.GATED_911)
        self.assertEqual(telephony.emergencies, [])

    async def test_bad_token_blocks_dispatch(self):
        providers, registry, confirmations, session, telephony = _setup()
        msg = {"topic": "caretaker.notify", "elder_id": "margaret-01",
               "severity": "high", "summary": "fall", "evidence": {}}
        await run_caretaker_agent(session, providers.llm, msg, confirmations)
        with self.assertRaises(PermissionError):
            await confirm_911(
                registry=registry, confirmations=confirmations, providers=providers,
                elder_id="margaret-01", token="forged", approve=True,
            )
        self.assertNotEqual(session.fsm.state, State.GATED_911)
        self.assertEqual(telephony.emergencies, [])


class TestMockEmergencyDispatch(unittest.IsolatedAsyncioTestCase):
    async def test_mock_dispatch_is_marked_mocked(self):
        res = await MockTelephony().dispatch_emergency("test")
        self.assertTrue(res.ok and res.mocked)


if __name__ == "__main__":
    unittest.main()
