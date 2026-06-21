"""Tests for the everyday-care features: Browserbase refill handoff and the
inbound caretaker SMS recap channel.

Run with:  python -m unittest discover -s tests
"""

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from app.caretaker_query import _phones_match, resolve_elder_by_caretaker, summarize_for_caretaker
from app.config import Settings
from app.confirmations import ConfirmationRegistry
from app.main import app
from app.providers.browser import BrowserTaskResult, MockBrowser
from app.providers.bus import InProcessBus
from app.providers.factory import Providers, _build_browser
from app.providers.llm import MockLLM
from app.providers.memory import MockMemory
from app.providers.telephony import MockTelephony
from app.providers.voice import MockVoice
from app.session import CaretakerService, SessionRegistry


def _providers(memory=None) -> Providers:
    return Providers(
        llm=MockLLM(), voice=MockVoice(), memory=memory or MockMemory(),
        telephony=MockTelephony(), bus=InProcessBus(),
    )


def _install_state(memory=None) -> Providers:
    providers = _providers(memory)
    registry = SessionRegistry()
    app.state.providers = providers
    app.state.registry = registry
    app.state.confirmations = ConfirmationRegistry()
    app.state.caretaker = CaretakerService(providers, registry)
    app.state.bg_tasks = set()
    return providers


class TestBrowserProvider(unittest.IsolatedAsyncioTestCase):
    async def test_mock_browser_runs_task(self):
        res = await MockBrowser().run_task("Refill prescription: lisinopril")
        self.assertTrue(res.ok and res.mocked)
        self.assertIn("lisinopril", res.detail)

    def test_factory_mock_without_keys(self):
        s = Settings(_env_file=None)
        self.assertEqual(_build_browser(s).name, "mock")

    def test_factory_browserbase_with_keys(self):
        s = Settings(_env_file=None, browserbase_api_key="k", browserbase_project_id="p")
        self.assertEqual(_build_browser(s).name, "browserbase")

    def test_summary_includes_browser(self):
        self.assertEqual(_providers().summary()["browser"], "mock")


class TestRefillEndpoint(unittest.TestCase):
    def setUp(self):
        _install_state()
        self.client = TestClient(app)

    def test_refill_known_elder(self):
        resp = self.client.post(
            "/elders/margaret-01/refill", json={"medication": "lisinopril"}
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["task"]["ok"])
        self.assertEqual(body["elder_id"], "margaret-01")

    def test_refill_unknown_elder_404(self):
        resp = self.client.post("/elders/ghost/refill", json={"medication": "x"})
        self.assertEqual(resp.status_code, 404)


class TestPhoneMatching(unittest.TestCase):
    def test_matches_on_suffix(self):
        self.assertTrue(_phones_match("+1-555-123-4567", "+15551234567"))
        self.assertTrue(_phones_match("(555) 123-4567", "555.123.4567"))

    def test_rejects_mismatch_and_empty(self):
        self.assertFalse(_phones_match("+15551234567", "+15559999999"))
        self.assertFalse(_phones_match("", "+15551234567"))


class TestCaretakerQuery(unittest.IsolatedAsyncioTestCase):
    async def test_resolve_by_caretaker_phone(self):
        mem = MockMemory()
        await mem.set_profile(
            "frank-02",
            {"elder_id": "frank-02", "name": "Frank",
             "caretaker": {"name": "Joe", "phone": "+1-555-123-4567"}},
        )
        eid = await resolve_elder_by_caretaker(mem, "+15551234567")
        self.assertEqual(eid, "frank-02")

    async def test_resolve_returns_none_for_unknown(self):
        mem = MockMemory()
        self.assertIsNone(await resolve_elder_by_caretaker(mem, "+19998887777"))

    async def test_summary_uses_llm_recap(self):
        providers = _providers()
        text = await summarize_for_caretaker(providers, "margaret-01", "how's mom?")
        self.assertTrue(len(text) > 0)

    async def test_summary_fallback_without_llm_text(self):
        # An LLM that returns empty text -> deterministic fallback recap.
        class EmptyLLM:
            name = "empty"

            async def run(self, system, messages, tools):
                from app.providers.llm import LLMResult
                return LLMResult(content=[], text="", stop_reason="end_turn")

        providers = _providers()
        providers.llm = EmptyLLM()
        text = await summarize_for_caretaker(providers, "margaret-01", "update?")
        self.assertIn("Margaret", text)


class TestInboundSmsWebhook(unittest.TestCase):
    def setUp(self):
        # Seed an elder whose caretaker phone we will text from.
        mem = MockMemory()
        asyncio.run(mem.set_profile(
            "margaret-01",
            {"elder_id": "margaret-01", "name": "Margaret",
             "caretaker": {"name": "Lisa", "phone": "+1-555-0100"}},
        ))
        _install_state(memory=mem)
        self.client = TestClient(app)

    def test_known_caretaker_gets_recap(self):
        resp = self.client.post(
            "/twilio/sms", data={"Body": "how's mom today?", "From": "+15550100"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("<Message>", resp.text)
        self.assertIn("application/xml", resp.headers["content-type"])

    def test_unknown_number_gets_guidance(self):
        resp = self.client.post(
            "/twilio/sms", data={"Body": "hi", "From": "+19990001111"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("isn't linked", resp.text)


if __name__ == "__main__":
    unittest.main()
