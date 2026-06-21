"""Tests for incident persistence + the caretaker history endpoint.

Run with:  python -m unittest discover -s tests
"""

import asyncio
import base64
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from app.confirmations import ConfirmationRegistry
from app.main import app
from app.protocol import TriggerMessage
from app.providers.bus import InProcessBus
from app.providers.factory import Providers
from app.providers.llm import MockLLM
from app.providers.memory import MockMemory
from app.providers.telephony import MockTelephony
from app.providers.voice import MockVoice
from app.session import (
    CaretakerService,
    ElderSession,
    SessionRegistry,
    handle_trigger,
)


def _b64(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


class AutoRespondWS:
    def __init__(self, transcript: str) -> None:
        self.transcript = transcript
        self.session: ElderSession | None = None

    async def send_text(self, text: str) -> None:
        msg = json.loads(text)
        if msg.get("type") == "listen":
            asyncio.create_task(self._respond(msg["prompt_id"]))

    async def _respond(self, prompt_id: str) -> None:
        for _ in range(200):
            if self.session and prompt_id in self.session._pending:
                clip = _b64(f"QC-SCENARIO-TRANSCRIPT: {self.transcript}")
                self.session.on_audio_response(prompt_id, clip)
                return
            await asyncio.sleep(0.005)


def _providers() -> Providers:
    return Providers(
        llm=MockLLM(), voice=MockVoice(), memory=MockMemory(),
        telephony=MockTelephony(), bus=InProcessBus(),
    )


class TestIncidentPersistence(unittest.IsolatedAsyncioTestCase):
    async def _run(self, transcript: str, trigger_source: str) -> Providers:
        providers = _providers()
        registry = SessionRegistry()
        CaretakerService(providers, registry, ConfirmationRegistry()).attach()
        ws = AutoRespondWS(transcript)
        session = ElderSession(ws, "margaret-01", providers)
        ws.session = session
        registry.set("margaret-01", session)
        await handle_trigger(
            session,
            TriggerMessage(type="trigger", elder_id="margaret-01",
                           trigger_source=trigger_source),
        )
        return providers

    async def test_fine_incident_persisted(self):
        providers = await self._run("I'm fine, just dropped the remote", "manual")
        incidents = [e for e in await providers.memory.get_events("margaret-01")
                     if e.get("kind") == "incident"]
        self.assertEqual(len(incidents), 1)
        inc = incidents[0]
        self.assertFalse(inc["escalated"])
        self.assertEqual(inc["final_state"], "resolved")
        self.assertIn("ts", inc)
        self.assertIn("fsm_trace", inc)

    async def test_emergency_incident_marked_escalated(self):
        providers = await self._run("[silence]", "fall")
        incidents = [e for e in await providers.memory.get_events("margaret-01")
                     if e.get("kind") == "incident"]
        self.assertEqual(len(incidents), 1)
        self.assertTrue(incidents[0]["escalated"])


class TestHistoryEndpoint(unittest.TestCase):
    def setUp(self):
        providers = _providers()
        registry = SessionRegistry()
        app.state.providers = providers
        app.state.registry = registry
        app.state.confirmations = ConfirmationRegistry()
        app.state.caretaker = CaretakerService(providers, registry)
        app.state.bg_tasks = set()
        self.client = TestClient(app)
        # Seed some events directly.
        asyncio.run(self._seed(providers))

    async def _seed(self, providers):
        await providers.memory.log_event("margaret-01", {"kind": "incident", "final_state": "resolved"})
        await providers.memory.log_event("margaret-01", {"kind": "note", "text": "hi"})

    def test_events_endpoint_returns_history(self):
        resp = self.client.get("/elders/margaret-01/events")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 2)

    def test_kind_filter(self):
        resp = self.client.get("/elders/margaret-01/events", params={"kind": "incident"})
        events = resp.json()["events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["kind"], "incident")

    def test_empty_for_unknown_elder(self):
        resp = self.client.get("/elders/ghost/events")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 0)


if __name__ == "__main__":
    unittest.main()
