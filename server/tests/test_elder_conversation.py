import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.elder_conversation import handle_elder_conversation, wants_attention
from app.providers.bus import InProcessBus
from app.providers.factory import Providers
from app.providers.llm import MockLLM
from app.providers.memory import MockMemory
from app.providers.telephony import MockTelephony, TelephonyResult
from app.providers.voice import MockVoice


class RecordingTelephony(MockTelephony):
    def __init__(self, caretaker_answers: bool = True) -> None:
        super().__init__(caretaker_answers=caretaker_answers)
        self.sms: list[str] = []
        self.calls: list[str] = []
        self.emergencies: list[str] = []

    async def send_sms(self, text: str) -> TelephonyResult:
        self.sms.append(text)
        return await super().send_sms(text)

    async def call_voice(self, summary: str) -> TelephonyResult:
        self.calls.append(summary)
        return await super().call_voice(summary)

    async def dispatch_emergency(self, summary: str) -> TelephonyResult:
        self.emergencies.append(summary)
        return await super().dispatch_emergency(summary)


def _providers(telephony: RecordingTelephony) -> Providers:
    return Providers(
        llm=MockLLM(),
        voice=MockVoice(),
        memory=MockMemory(),
        telephony=telephony,
        bus=InProcessBus(),
    )


class TestElderConversation(unittest.IsolatedAsyncioTestCase):
    def test_wake_detection(self):
        self.assertTrue(wants_attention("Quietcare what time is it"))
        self.assertTrue(wants_attention("I need help"))
        self.assertFalse(wants_attention("the television is on"))

    async def test_chat_response_synthesizes_audio(self):
        telephony = RecordingTelephony()
        res = await handle_elder_conversation(
            providers=_providers(telephony),
            elder_id="margaret-01",
            transcript="Quietcare how am I doing today",
            auto_emergency_fallback=False,
            caretaker_ack_timeout_seconds=1,
        )
        self.assertEqual(res["action"], "chat")
        self.assertTrue(res["reply_text"])
        self.assertTrue(res["audio_b64"])
        self.assertEqual(telephony.sms, [])
        self.assertEqual(telephony.calls, [])

    async def test_help_request_alerts_caretaker(self):
        telephony = RecordingTelephony(caretaker_answers=True)
        res = await handle_elder_conversation(
            providers=_providers(telephony),
            elder_id="margaret-01",
            transcript="Quietcare help I fell",
            auto_emergency_fallback=True,
            caretaker_ack_timeout_seconds=1,
        )
        self.assertEqual(res["action"], "escalated")
        self.assertEqual(len(telephony.sms), 1)
        self.assertEqual(len(telephony.calls), 1)
        self.assertEqual(telephony.emergencies, [])


if __name__ == "__main__":
    unittest.main()
