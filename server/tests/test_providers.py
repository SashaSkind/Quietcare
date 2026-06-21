"""Unit tests for provider mocks + the factory's mock-fallback behavior.

Run with:  python -m unittest discover -s tests
"""

import base64
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import Settings
from app.providers.bus import InProcessBus
from app.providers.factory import build_providers
from app.providers.llm import MockLLM
from app.providers.memory import SAMPLE_ELDER, MockMemory
from app.providers.telephony import MockTelephony
from app.providers.voice import MockVoice


def _b64(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


class TestMockVoice(unittest.IsolatedAsyncioTestCase):
    async def test_synthesize_returns_valid_b64_wav(self):
        v = MockVoice()
        out = await v.synthesize("hello")
        # Decodes cleanly and starts with a RIFF/WAVE header.
        raw = base64.b64decode(out)
        self.assertTrue(raw.startswith(b"RIFF"))
        self.assertIn(b"WAVE", raw)

    async def test_transcribe_scenario_hint(self):
        v = MockVoice()
        clip = _b64("QC-SCENARIO-TRANSCRIPT: I fell and can't get up")
        self.assertEqual(await v.transcribe(clip), "I fell and can't get up")

    async def test_transcribe_canned_default(self):
        v = MockVoice()
        self.assertEqual(await v.transcribe(None), "I'm fine, thank you.")
        self.assertEqual(await v.transcribe(_b64("noise")), "I'm fine, thank you.")


class TestMockMemory(unittest.IsolatedAsyncioTestCase):
    async def test_seeded_profile(self):
        m = MockMemory()
        prof = await m.get_profile(SAMPLE_ELDER["elder_id"])
        self.assertIsNotNone(prof)
        self.assertEqual(prof["name"], "Margaret")

    async def test_set_get_roundtrip(self):
        m = MockMemory()
        await m.set("k", {"a": 1})
        self.assertEqual(await m.get("k"), {"a": 1})
        self.assertIsNone(await m.get("missing"))

    async def test_events_append_and_list(self):
        m = MockMemory()
        eid = "x-1"
        self.assertEqual(await m.get_events(eid), [])
        await m.log_event(eid, {"kind": "a"})
        await m.log_event(eid, {"kind": "b"})
        events = await m.get_events(eid)
        self.assertEqual([e["kind"] for e in events], ["a", "b"])


class TestMockTelephony(unittest.IsolatedAsyncioTestCase):
    async def test_sms_and_call_are_mocked_ok(self):
        t = MockTelephony()
        sms = await t.send_sms("hi")
        call = await t.call_voice("summary")
        self.assertTrue(sms.ok and sms.mocked)
        self.assertTrue(call.ok and call.mocked)


class TestInProcessBus(unittest.IsolatedAsyncioTestCase):
    async def test_publish_fans_out_to_handlers(self):
        bus = InProcessBus()
        seen = []

        async def handler(msg):
            seen.append(msg)

        bus.subscribe(handler)
        await bus.publish({"topic": "t", "x": 1})
        self.assertEqual(seen, [{"topic": "t", "x": 1}])


class TestMockLLMPolicy(unittest.IsolatedAsyncioTestCase):
    """The mock LLM emulates each agent's tool plan from message history."""

    async def test_elder_first_step_loads_context(self):
        llm = MockLLM()
        tools = [{"name": "speak_to_elder"}, {"name": "get_elder_profile"}]
        res = await llm.run("sys", [{"role": "user", "content": "go"}], tools)
        names = {tc.name for tc in res.tool_calls}
        self.assertIn("get_elder_profile", names)
        self.assertEqual(res.stop_reason, "tool_use")

    async def test_caretaker_first_step_loads_profile(self):
        llm = MockLLM()
        tools = [{"name": "send_caretaker_sms"}, {"name": "get_elder_profile"}]
        res = await llm.run(
            "sys", [{"role": "user", "content": "severity=high"}], tools
        )
        self.assertEqual([tc.name for tc in res.tool_calls], ["get_elder_profile"])


class TestFactoryFallback(unittest.TestCase):
    def test_empty_settings_yield_all_mocks(self):
        # No env file, all credentials blank -> every provider is the mock.
        s = Settings(_env_file=None)
        p = build_providers(s)
        self.assertEqual(p.llm.name, "mock")
        self.assertEqual(p.voice.name, "mock")
        self.assertEqual(p.memory.name, "mock")
        self.assertEqual(p.telephony.name, "mock")
        self.assertEqual(p.bus.name, "in-process")


class TestAnthropicBaseUrlNormalization(unittest.TestCase):
    def test_trailing_v1_is_stripped(self):
        try:
            from app.providers.llm import AnthropicLLM
        except Exception:  # pragma: no cover
            self.skipTest("anthropic SDK not installed")
        llm = AnthropicLLM("key", "https://api.tokenrouter.com/v1", "model")
        base = str(llm._client.base_url).rstrip("/")
        # The SDK appends /v1/messages; base must NOT already end in /v1.
        self.assertFalse(base.endswith("/v1"))
        self.assertTrue(base.endswith("tokenrouter.com"))


if __name__ == "__main__":
    unittest.main()
