"""Unit tests for ElderSession state + request/response correlation + registry.

Run with:  python -m unittest discover -s tests
"""

import asyncio
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.providers.bus import InProcessBus
from app.providers.factory import Providers
from app.providers.llm import MockLLM
from app.providers.memory import MockMemory
from app.providers.telephony import MockTelephony
from app.providers.voice import MockVoice
from app.session import ElderSession, SessionRegistry
from app.state_machine import State


class FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))


def _providers() -> Providers:
    return Providers(
        llm=MockLLM(),
        voice=MockVoice(),
        memory=MockMemory(),
        telephony=MockTelephony(),
        bus=InProcessBus(),
    )


def _session() -> tuple[ElderSession, FakeWS]:
    ws = FakeWS()
    return ElderSession(ws, "margaret-01", _providers()), ws


class TestPromptIds(unittest.TestCase):
    def test_prompt_ids_increment(self):
        s, _ = _session()
        self.assertEqual(s.new_prompt_id(), "p1")
        self.assertEqual(s.new_prompt_id(), "p2")
        self.assertEqual(s.current_prompt_id, "p2")


class TestResetIncident(unittest.TestCase):
    def test_reset_creates_fresh_fsm_and_clears_state(self):
        s, _ = _session()
        s.fsm.trigger()
        s.new_prompt_id()
        s.last_transcript = "x"
        s.reset_incident()
        self.assertEqual(s.fsm.state, State.IDLE)
        self.assertIsNone(s.current_prompt_id)
        self.assertEqual(s.last_transcript, "")


class TestStatusEmission(unittest.IsolatedAsyncioTestCase):
    async def test_transitions_emit_client_status(self):
        s, ws = _session()
        s.fsm.trigger()
        await s.begin_checkin_once()
        await s.escalate()
        states = [m["state"] for m in ws.sent if m.get("type") == "status"]
        self.assertEqual(states, ["checking_in", "escalating"])

    async def test_resolve_only_from_checking_in(self):
        s, ws = _session()
        s.fsm.trigger()
        # Not in CHECKING_IN yet -> resolve is a no-op.
        await s.resolve()
        self.assertEqual(s.fsm.state, State.TRIGGERED)
        await s.begin_checkin_once()
        await s.resolve()
        self.assertEqual(s.fsm.state, State.RESOLVED)


class TestAudioResponseCorrelation(unittest.IsolatedAsyncioTestCase):
    async def test_response_resolves_pending_future(self):
        s, _ = _session()

        async def responder():
            # Wait until the listener registers, then deliver audio.
            for _ in range(200):
                if "p1" in s._pending:
                    s.on_audio_response("p1", "AUDIO")
                    return
                await asyncio.sleep(0.005)

        s.new_prompt_id()  # p1
        task = asyncio.create_task(responder())
        result = await s.await_audio_response("p1")
        await task
        self.assertEqual(result, {"audio_b64": "AUDIO", "transcript": None})

    async def test_stale_response_is_ignored(self):
        s, _ = _session()
        # No pending future for p9 -> should not raise.
        s.on_audio_response("p9", "AUDIO")


class TestRegistry(unittest.TestCase):
    def test_set_get_remove(self):
        reg = SessionRegistry()
        s, _ = _session()
        reg.set("margaret-01", s)
        self.assertIs(reg.get("margaret-01"), s)
        reg.remove("margaret-01")
        self.assertIsNone(reg.get("margaret-01"))


if __name__ == "__main__":
    unittest.main()
