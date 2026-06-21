"""Tests for the voice provider selection + (optional) live Deepgram round-trip.

The live round-trip only runs when RUN_LIVE_TESTS=1 and a Deepgram key is
configured, so the default suite stays offline/deterministic.

Run with:        python -m unittest discover -s tests
Run live too:    RUN_LIVE_TESTS=1 python -m unittest discover -s tests
"""

import base64
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import Settings
from app.providers.factory import _build_voice


def _deepgram_installed() -> bool:
    try:
        import deepgram  # noqa: F401

        return True
    except Exception:
        return False


class TestVoiceSelection(unittest.TestCase):
    def test_mock_when_no_key(self):
        s = Settings(_env_file=None)
        self.assertEqual(_build_voice(s).name, "mock")

    @unittest.skipUnless(_deepgram_installed(), "deepgram-sdk not installed")
    def test_deepgram_when_key_present(self):
        s = Settings(_env_file=None, deepgram_api_key="dummy-key")
        # Client init is offline; selection should pick the real provider.
        self.assertEqual(_build_voice(s).name, "deepgram")


@unittest.skipUnless(
    os.environ.get("RUN_LIVE_TESTS") == "1" and Settings().has_deepgram,
    "live tests disabled (set RUN_LIVE_TESTS=1 with a Deepgram key)",
)
class TestDeepgramLiveRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_tts_is_wav_and_stt_recovers_text(self):
        from app.providers.voice import DeepgramVoice

        v = DeepgramVoice(Settings().deepgram_api_key)
        phrase = "Margaret, are you okay?"
        audio_b64 = await v.synthesize(phrase)
        raw = base64.b64decode(audio_b64)
        self.assertTrue(raw.startswith(b"RIFF"), "TTS should emit WAV")
        transcript = await v.transcribe(audio_b64)
        self.assertIn("margaret", transcript.lower())


if __name__ == "__main__":
    unittest.main()
