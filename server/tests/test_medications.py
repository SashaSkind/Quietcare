"""Tests for medication reminders + adherence."""

import asyncio
import base64
import json
import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.medications import (
    MedicationService,
    adherence_summary,
    confirmation_from_transcript,
    due_medications,
    run_medication_reminder,
)
from app.providers.bus import InProcessBus
from app.providers.factory import Providers
from app.providers.llm import MockLLM
from app.providers.memory import MockMemory
from app.providers.telephony import MockTelephony
from app.providers.voice import MockVoice
from app.session import ElderSession, SessionRegistry


def _clip(text: str) -> str:
    return base64.b64encode(f"QC-SCENARIO-TRANSCRIPT: {text}".encode()).decode()


class AutoRespondWS:
    """Replies to every `listen` with a fixed transcript clip."""

    def __init__(self, transcript: str) -> None:
        self._clip = _clip(transcript)
        self.session = None

    async def send_text(self, text: str) -> None:
        msg = json.loads(text)
        if msg.get("type") == "listen":
            asyncio.create_task(self._respond(msg["prompt_id"]))

    async def _respond(self, prompt_id: str) -> None:
        for _ in range(200):
            if self.session and prompt_id in self.session._pending:
                self.session.on_audio_response(prompt_id, self._clip)
                return
            await asyncio.sleep(0.005)


def _providers(memory=None) -> Providers:
    return Providers(
        llm=MockLLM(), voice=MockVoice(), memory=memory or MockMemory(),
        telephony=MockTelephony(), bus=InProcessBus(),
    )


class TestPureLogic(unittest.TestCase):
    def test_confirmation_detection(self):
        self.assertTrue(confirmation_from_transcript("Yes I took it"))
        self.assertFalse(confirmation_from_transcript("no not yet"))
        self.assertIsNone(confirmation_from_transcript(""))

    def test_due_medications_matches_minute(self):
        meds = [{"name": "BP pill", "time": "14:00"}, {"name": "vitamin", "time": "09:00"}]
        now = datetime(2026, 1, 1, 14, 0)
        due = due_medications(meds, now, set())
        self.assertEqual([m["name"] for m in due], ["BP pill"])

    def test_due_medications_dedup(self):
        meds = [{"name": "BP pill", "time": "14:00"}]
        now = datetime(2026, 1, 1, 14, 0)
        self.assertEqual(due_medications(meds, now, {"BP pill@14:00@2026-01-01"}), [])

    def test_adherence_summary(self):
        events = [
            {"kind": "medication", "status": "confirmed"},
            {"kind": "medication", "status": "missed"},
            {"kind": "incident"},
        ]
        s = adherence_summary(events)
        self.assertEqual((s["confirmed"], s["missed"], s["total"]), (1, 1, 2))
        self.assertEqual(s["adherence_rate"], 0.5)


class TestReminderFlow(unittest.IsolatedAsyncioTestCase):
    async def test_confirmed_dose_logs_event(self):
        providers = _providers()
        ws = AutoRespondWS("yes I took it")
        session = ElderSession(ws, "margaret-01", providers)
        ws.session = session
        event = await run_medication_reminder(session, {"name": "BP pill", "time": "14:00"})
        self.assertEqual(event["status"], "confirmed")
        events = await providers.memory.get_events("margaret-01")
        self.assertEqual(events[-1]["status"], "confirmed")

    async def test_missed_dose_when_no_response(self):
        providers = _providers()

        class SilentWS:
            session = None
            async def send_text(self, text): pass

        session = ElderSession(SilentWS(), "margaret-01", providers)
        # No response -> transcript empty -> missed. Speed up by patching timeout.
        import app.session as sess
        orig = sess.LISTEN_TIMEOUT_S
        sess.LISTEN_TIMEOUT_S = 0.05
        try:
            event = await run_medication_reminder(session, {"name": "BP pill", "time": "14:00"})
        finally:
            sess.LISTEN_TIMEOUT_S = orig
        self.assertEqual(event["status"], "missed")


class TestScheduler(unittest.IsolatedAsyncioTestCase):
    async def test_tick_logs_missed_when_offline(self):
        memory = MockMemory()
        await memory.set_medications("margaret-01", [{"name": "BP pill", "time": "14:00"}])
        providers = _providers(memory)
        svc = MedicationService(providers, SessionRegistry(), _Settings())
        results = await svc.tick(datetime(2026, 1, 1, 14, 0))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "missed")
        # Dedup: a second tick the same minute fires nothing.
        self.assertEqual(await svc.tick(datetime(2026, 1, 1, 14, 0)), [])

    async def test_tick_runs_reminder_for_connected_session(self):
        memory = MockMemory()
        await memory.set_medications("margaret-01", [{"name": "BP pill", "time": "14:00"}])
        providers = _providers(memory)
        registry = SessionRegistry()
        ws = AutoRespondWS("yes")
        session = ElderSession(ws, "margaret-01", providers)
        ws.session = session
        registry.set("margaret-01", session)
        svc = MedicationService(providers, registry, _Settings())
        results = await svc.tick(datetime(2026, 1, 1, 14, 0))
        self.assertEqual(results[0]["status"], "confirmed")


class _Settings:
    med_confirm_window_ms = 8000
    med_tick_seconds = 60


if __name__ == "__main__":
    unittest.main()
