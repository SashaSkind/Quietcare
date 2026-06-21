"""Tests for new trigger sources (inactivity/geofence) and gate risk scoring."""

import asyncio
import base64
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.protocol import TriggerMessage, parse_client_message
from app.providers.bus import InProcessBus
from app.providers.factory import Providers
from app.providers.llm import MockLLM
from app.providers.memory import MockMemory
from app.providers.policy_gate import LocalPolicyGate, score_risk
from app.providers.telephony import MockTelephony
from app.providers.voice import MockVoice
from app.session import CaretakerService, ElderSession, SessionRegistry, handle_trigger
from app.state_machine import State


class TestProtocolTriggerSources(unittest.TestCase):
    def test_inactivity_and_geofence_parse(self):
        for src in ("inactivity", "geofence"):
            msg = parse_client_message({"type": "trigger", "elder_id": "x", "trigger_source": src})
            self.assertEqual(msg.trigger_source, src)

    def test_location_and_note_fields(self):
        msg = parse_client_message({
            "type": "trigger", "elder_id": "x", "trigger_source": "geofence",
            "note": "left home", "location": {"lat": 1.0, "lng": 2.0},
        })
        self.assertEqual(msg.note, "left home")
        self.assertEqual(msg.location.lat, 1.0)


class TestRiskScoring(unittest.TestCase):
    def test_fall_high_severity_scores_high(self):
        score, level = score_risk("escalation", {"severity": "high", "trigger_source": "fall", "summary": "fell, no response"})
        self.assertGreaterEqual(score, 50)
        self.assertIn(level, ("high", "critical"))

    def test_scheduled_low_scores_low(self):
        score, level = score_risk("escalation", {"severity": "low", "trigger_source": "scheduled"})
        self.assertLess(score, 25)
        self.assertEqual(level, "low")


class TestRiskGate(unittest.IsolatedAsyncioTestCase):
    async def test_emergency_below_min_blocked_without_human(self):
        gate = LocalPolicyGate(emergency_min_risk=90)
        d = await gate.sanction("emergency_dispatch", {"severity": "low", "trigger_source": "manual"})
        self.assertFalse(d.allowed)

    async def test_emergency_below_min_allowed_with_human(self):
        gate = LocalPolicyGate(emergency_min_risk=90)
        d = await gate.sanction("emergency_dispatch", {"severity": "low", "human_confirmed": True})
        self.assertTrue(d.allowed)

    async def test_escalation_always_allowed_and_scored(self):
        gate = LocalPolicyGate(emergency_min_risk=90)
        d = await gate.sanction("escalation", {"severity": "high", "trigger_source": "fall"})
        self.assertTrue(d.allowed)
        self.assertGreater(d.risk_score, 0)


def _clip(text: str) -> str:
    return base64.b64encode(f"QC-SCENARIO-TRANSCRIPT: {text}".encode()).decode()


class SilentWS:
    """Never answers a listen (simulates the elder not near the device)."""
    session = None
    async def send_text(self, text): pass


class TestGeofenceFlow(unittest.IsolatedAsyncioTestCase):
    async def test_geofence_can_escalate_without_checkin(self):
        providers = Providers(
            llm=MockLLM(), voice=MockVoice(), memory=MockMemory(),
            telephony=MockTelephony(), bus=InProcessBus(),
        )
        registry = SessionRegistry()
        CaretakerService(providers, registry).attach()
        session = ElderSession(SilentWS(), "margaret-01", providers)
        registry.set("margaret-01", session)
        # hard_fall is set True for geofence so escalation can bypass check-in.
        import app.session as sess
        orig = sess.LISTEN_TIMEOUT_S
        sess.LISTEN_TIMEOUT_S = 0.05
        try:
            await handle_trigger(session, TriggerMessage(
                type="trigger", elder_id="margaret-01", trigger_source="geofence",
                note="left safe zone at 2am",
            ))
        finally:
            sess.LISTEN_TIMEOUT_S = orig
        self.assertTrue(session.hard_fall)
        # An incident was persisted with the geofence source.
        events = await providers.memory.get_events("margaret-01")
        self.assertTrue(any(e.get("trigger_source") == "geofence" for e in events))


if __name__ == "__main__":
    unittest.main()
