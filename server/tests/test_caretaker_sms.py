"""Tests for inbound caretaker SMS: intent routing, thread memory, call bridge."""

import asyncio
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.caretaker_query import (
    detect_intent,
    handle_inbound_sms,
    prompt_elder_to_call,
)
from app.providers.bus import InProcessBus
from app.providers.factory import Providers
from app.providers.llm import MockLLM
from app.providers.memory import MockMemory
from app.providers.telephony import MockTelephony
from app.providers.voice import MockVoice
from app.session import ElderSession, SessionRegistry


async def _seed(memory):
    await memory.set_profile(
        "margaret-01",
        {"elder_id": "margaret-01", "name": "Margaret", "medications": ["BP pill"],
         "caretaker": {"name": "Lisa", "phone": "+1-555-0100"}},
    )


def _providers(memory):
    return Providers(
        llm=MockLLM(), voice=MockVoice(), memory=memory,
        telephony=MockTelephony(), bus=InProcessBus(),
    )


class SpeakCaptureWS:
    def __init__(self):
        self.spoken = []
        self.session = None

    async def send_text(self, text):
        msg = json.loads(text)
        if msg.get("type") == "speak":
            self.spoken.append(msg.get("text", ""))


class TestIntentDetection(unittest.TestCase):
    def test_intents(self):
        self.assertEqual(detect_intent("have her call me please"), "call_me")
        self.assertEqual(detect_intent("how has she been this week?"), "wellness")
        self.assertEqual(detect_intent("she's running low on her prescription"), "refill")
        self.assertEqual(detect_intent("how's mom today?"), "recap")


class TestCallBridge(unittest.IsolatedAsyncioTestCase):
    async def test_prompts_connected_idle_elder(self):
        memory = MockMemory()
        await _seed(memory)
        providers = _providers(memory)
        registry = SessionRegistry()
        ws = SpeakCaptureWS()
        session = ElderSession(ws, "margaret-01", providers)
        ws.session = session
        registry.set("margaret-01", session)
        ok = await prompt_elder_to_call(registry, "margaret-01", "Lisa")
        self.assertTrue(ok)
        await asyncio.sleep(0.02)  # let the spawned speak task run
        self.assertTrue(any("Lisa" in s for s in ws.spoken))

    async def test_no_session_returns_false(self):
        memory = MockMemory()
        await _seed(memory)
        ok = await prompt_elder_to_call(SessionRegistry(), "margaret-01", "Lisa")
        self.assertFalse(ok)


class TestInboundSmsRouting(unittest.IsolatedAsyncioTestCase):
    async def _setup(self):
        memory = MockMemory()
        await _seed(memory)
        providers = _providers(memory)
        return providers, memory, SessionRegistry()

    async def test_recap_persists_thread(self):
        providers, memory, registry = await self._setup()
        reply = await handle_inbound_sms(providers, registry, "+15550100", "how's mom?")
        self.assertTrue(len(reply) > 0)
        thread = await memory.get_sms_thread("margaret-01")
        self.assertEqual(thread[0]["role"], "user")
        self.assertEqual(thread[1]["role"], "assistant")

    async def test_wellness_intent(self):
        providers, memory, registry = await self._setup()
        reply = await handle_inbound_sms(providers, registry, "+15550100", "how has she been this week?")
        self.assertTrue(len(reply) > 0)

    async def test_refill_intent_runs_browser(self):
        providers, memory, registry = await self._setup()
        reply = await handle_inbound_sms(providers, registry, "+15550100", "she's low on her prescription")
        self.assertIn("refill", reply.lower())

    async def test_call_me_intent_without_session(self):
        providers, memory, registry = await self._setup()
        reply = await handle_inbound_sms(providers, registry, "+15550100", "have her call me")
        self.assertIn("reachable", reply.lower())

    async def test_unknown_number(self):
        providers, memory, registry = await self._setup()
        reply = await handle_inbound_sms(providers, registry, "+19998887777", "hi")
        self.assertIn("isn't linked", reply)


if __name__ == "__main__":
    unittest.main()
