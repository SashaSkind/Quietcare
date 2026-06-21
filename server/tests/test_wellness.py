"""Tests for wellness trend summaries."""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from app.confirmations import ConfirmationRegistry
from app.main import app
from app.providers.bus import InProcessBus
from app.providers.factory import Providers
from app.providers.llm import MockLLM
from app.providers.memory import MockMemory
from app.providers.telephony import MockTelephony
from app.providers.voice import MockVoice
from app.session import CaretakerService, SessionRegistry
from app.wellness import compute_trends, summarize_wellness


def _providers(memory=None) -> Providers:
    return Providers(
        llm=MockLLM(), voice=MockVoice(), memory=memory or MockMemory(),
        telephony=MockTelephony(), bus=InProcessBus(),
    )


def _now_iso(days_ago=0):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


class TestComputeTrends(unittest.TestCase):
    def test_counts_within_window(self):
        events = [
            {"kind": "incident", "trigger_source": "scheduled", "escalated": False, "ts": _now_iso(1)},
            {"kind": "incident", "trigger_source": "fall", "escalated": True, "ts": _now_iso(2)},
            {"kind": "incident", "trigger_source": "scheduled", "escalated": False, "ts": _now_iso(20)},  # outside 7d
            {"kind": "medication", "status": "confirmed", "ts": _now_iso(1)},
            {"kind": "medication", "status": "missed", "ts": _now_iso(1)},
        ]
        t = compute_trends(events, datetime.now(timezone.utc), days=7)
        self.assertEqual(t["incidents"], 2)
        self.assertEqual(t["escalations"], 1)
        self.assertEqual(t["medication"]["total"], 2)
        self.assertFalse(t["all_normal"])

    def test_wandering_counted(self):
        events = [{"kind": "incident", "trigger_source": "geofence", "escalated": True, "ts": _now_iso(1)}]
        t = compute_trends(events, datetime.now(timezone.utc), days=7)
        self.assertEqual(t["wandering_alerts"], 1)


class TestSummarize(unittest.IsolatedAsyncioTestCase):
    async def test_summary_present(self):
        providers = _providers()
        out = await summarize_wellness(providers, "margaret-01", days=7)
        self.assertIn("trends", out)
        self.assertTrue(len(out["summary"]) > 0)


class TestWellnessEndpoint(unittest.TestCase):
    def setUp(self):
        providers = _providers()
        registry = SessionRegistry()
        app.state.providers = providers
        app.state.registry = registry
        app.state.confirmations = ConfirmationRegistry()
        app.state.caretaker = CaretakerService(providers, registry)
        app.state.bg_tasks = set()
        self.client = TestClient(app)

    def test_wellness_endpoint(self):
        r = self.client.get("/elders/margaret-01/wellness")
        self.assertEqual(r.status_code, 200)
        self.assertIn("summary", r.json())

    def test_wellness_unknown_404(self):
        self.assertEqual(self.client.get("/elders/ghost/wellness").status_code, 404)


if __name__ == "__main__":
    unittest.main()
