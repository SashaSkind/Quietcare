"""Tests for the ArmorIQ policy gate that sanctions escalation actions.

Covers the gate provider + factory selection, and that a denying gate blocks
both the caretaker escalation (elder-agent) and the 911 emergency dispatch.

Run with:  python -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.elder import run_elder_agent
from app.config import Settings
from app.confirmations import ConfirmationRegistry
from app.providers.bus import InProcessBus
from app.providers.factory import Providers, _build_policy_gate
from app.providers.llm import MockLLM
from app.providers.memory import MockMemory
from app.providers.policy_gate import GateDecision, MockPolicyGate, PolicyGate
from app.providers.telephony import MockTelephony, TelephonyResult
from app.providers.voice import MockVoice
from app.session import SessionRegistry, confirm_911


class DenyingGate(PolicyGate):
    name = "deny"

    async def sanction(self, action, context):
        return GateDecision(allowed=False, reason="denied by test", mocked=False, source="deny")


class RecordingTelephony(MockTelephony):
    def __init__(self):
        super().__init__()
        self.emergencies = []

    async def dispatch_emergency(self, summary):
        self.emergencies.append(summary)
        return await super().dispatch_emergency(summary)


class TestPolicyGateProvider(unittest.IsolatedAsyncioTestCase):
    async def test_mock_allows(self):
        d = await MockPolicyGate().sanction("escalation", {})
        self.assertTrue(d.allowed and d.mocked)


class TestFactorySelection(unittest.TestCase):
    def test_mock_without_keys(self):
        s = Settings(_env_file=None)
        self.assertEqual(_build_policy_gate(s).name, "mock")

    def test_armoriq_with_keys(self):
        s = Settings(_env_file=None, armoriq_api_key="k", armoriq_base_url="https://x")
        self.assertEqual(_build_policy_gate(s).name, "armoriq")

    def test_summary_includes_policy_gate(self):
        p = Providers(
            llm=MockLLM(), voice=MockVoice(), memory=MockMemory(),
            telephony=MockTelephony(), bus=InProcessBus(),
        )
        self.assertEqual(p.summary()["policy_gate"], "mock")


class TestArmorIQFailModes(unittest.IsolatedAsyncioTestCase):
    async def test_fail_open_allows_on_error(self):
        from app.providers.policy_gate import ArmorIQPolicyGate

        # Unreachable host -> error path.
        gate = ArmorIQPolicyGate("k", "http://127.0.0.1:1", fail_open=True)
        d = await gate.sanction("escalation", {})
        self.assertTrue(d.allowed)
        self.assertIn("fail-open", d.reason)

    async def test_fail_closed_blocks_on_error(self):
        from app.providers.policy_gate import ArmorIQPolicyGate

        gate = ArmorIQPolicyGate("k", "http://127.0.0.1:1", fail_open=False)
        d = await gate.sanction("escalation", {})
        self.assertFalse(d.allowed)
        self.assertIn("fail-closed", d.reason)


class _AutoRespondWS:
    def __init__(self, transcript):
        import base64
        self._clip = base64.b64encode(f"QC-SCENARIO-TRANSCRIPT: {transcript}".encode()).decode()
        self.session = None

    async def send_text(self, text):
        import asyncio
        import json
        msg = json.loads(text)
        if msg.get("type") == "listen":
            asyncio.create_task(self._respond(msg["prompt_id"]))

    async def _respond(self, prompt_id):
        import asyncio
        for _ in range(200):
            if self.session and prompt_id in self.session._pending:
                self.session.on_audio_response(prompt_id, self._clip)
                return
            await asyncio.sleep(0.005)


class TestEscalationGatedByPolicy(unittest.IsolatedAsyncioTestCase):
    async def test_denying_gate_blocks_caretaker_escalation(self):
        from app.protocol import TriggerMessage
        from app.session import CaretakerService, ElderSession, handle_trigger

        telephony = RecordingTelephony()
        providers = Providers(
            llm=MockLLM(), voice=MockVoice(), memory=MockMemory(),
            telephony=telephony, bus=InProcessBus(), policy_gate=DenyingGate(),
        )
        registry = SessionRegistry()
        CaretakerService(providers, registry, ConfirmationRegistry()).attach()
        ws = _AutoRespondWS("[silence]")
        session = ElderSession(ws, "margaret-01", providers)
        ws.session = session
        registry.set("margaret-01", session)
        await handle_trigger(
            session,
            TriggerMessage(type="trigger", elder_id="margaret-01", trigger_source="fall"),
        )
        # Gate denied -> never escalated, no caretaker contact.
        from app.state_machine import State
        self.assertNotEqual(session.fsm.state, State.ESCALATING)
        self.assertNotEqual(session.fsm.state, State.CARETAKER_NOTIFIED)


class Test911GatedByPolicy(unittest.IsolatedAsyncioTestCase):
    async def _setup(self, gate):
        from app.session import ElderSession

        telephony = RecordingTelephony()
        providers = Providers(
            llm=MockLLM(), voice=MockVoice(), memory=MockMemory(),
            telephony=telephony, bus=InProcessBus(), policy_gate=gate,
        )
        registry = SessionRegistry()
        confirmations = ConfirmationRegistry()
        session = ElderSession(_AutoRespondWS("x"), "margaret-01", providers)
        session.fsm.trigger()
        session.fsm.begin_checkin()
        session.fsm.escalate()
        session.fsm.caretaker_notified()
        registry.set("margaret-01", session)
        pc = confirmations.create("margaret-01", "no response", "fall, unresponsive")
        return providers, registry, confirmations, session, telephony, pc.token

    async def test_denying_gate_blocks_dispatch(self):
        from app.state_machine import State

        providers, registry, confirmations, session, telephony, token = await self._setup(DenyingGate())
        result = await confirm_911(
            registry=registry, confirmations=confirmations, providers=providers,
            elder_id="margaret-01", token=token, approve=True,
        )
        self.assertEqual(result["status"], "blocked_by_policy")
        self.assertEqual(telephony.emergencies, [])
        self.assertNotEqual(session.fsm.state, State.GATED_911)

    async def test_allowing_gate_permits_dispatch(self):
        from app.state_machine import State

        providers, registry, confirmations, session, telephony, token = await self._setup(MockPolicyGate())
        result = await confirm_911(
            registry=registry, confirmations=confirmations, providers=providers,
            elder_id="margaret-01", token=token, approve=True,
        )
        self.assertEqual(result["status"], "confirmed")
        self.assertEqual(len(telephony.emergencies), 1)
        self.assertEqual(session.fsm.state, State.GATED_911)


if __name__ == "__main__":
    unittest.main()
