"""Tests for the AudioScene (YAMNet/distress) provider + acoustic fusion.

The real YAMNet path is exercised only when YAMNET_MODEL_PATH/LABELS_PATH point
at a local model (gated behind RUN_LIVE_TESTS); otherwise the deterministic mock
is used so the suite stays offline.

Run with:  python -m unittest discover -s tests
"""

import asyncio
import base64
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import Settings
from app.providers.audio_scene import (
    AudioSceneResult,
    EnsembleAudioScene,
    MockAudioScene,
)
from app.providers.bus import InProcessBus
from app.providers.factory import Providers, _build_audio_scene
from app.providers.llm import MockLLM
from app.providers.memory import MockMemory
from app.providers.telephony import MockTelephony
from app.providers.voice import MockVoice
from app.protocol import TriggerMessage
from app.session import ElderSession, SessionRegistry, handle_trigger


def _b64(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


class TestMockAudioScene(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_audio_hint(self):
        scene = MockAudioScene()
        res = await scene.classify(_b64("QC-SCENARIO-AUDIO: Thud:0.82,Groan:0.5"))
        labels = {l for l, _ in res.tags}
        self.assertIn("Thud", labels)
        self.assertTrue(res.distress)

    async def test_non_distress_audio_hint(self):
        scene = MockAudioScene()
        res = await scene.classify(_b64("QC-SCENARIO-AUDIO: Speech:0.9,Silence:0.4"))
        self.assertFalse(res.distress)

    async def test_transcript_hint_infers_distress(self):
        scene = MockAudioScene()
        res = await scene.classify(_b64("QC-SCENARIO-TRANSCRIPT: I fell and can't get up"))
        self.assertTrue(res.distress)

    async def test_empty_and_plain_audio(self):
        scene = MockAudioScene()
        self.assertFalse((await scene.classify(None)).distress)
        self.assertFalse((await scene.classify(_b64("random noise"))).distress)


class TestFactorySelection(unittest.TestCase):
    def test_mock_when_no_model(self):
        s = Settings(_env_file=None)
        self.assertEqual(_build_audio_scene(s).name, "mock")

    def test_explicit_mock_backend(self):
        s = Settings(_env_file=None, audio_scene_backend="mock")
        self.assertEqual(_build_audio_scene(s).name, "mock")

    def test_yamnet_backend_falls_back_to_mock_without_model(self):
        s = Settings(_env_file=None, audio_scene_backend="yamnet")
        self.assertEqual(_build_audio_scene(s).name, "mock")

    def test_both_backend_falls_back_to_mock_when_none_available(self):
        # No YAMNet model configured and PANNs deps absent in test env -> mock.
        s = Settings(_env_file=None, audio_scene_backend="both")
        self.assertEqual(_build_audio_scene(s).name, "mock")

    def test_summary_includes_audio_scene(self):
        providers = Providers(
            llm=MockLLM(), voice=MockVoice(), memory=MockMemory(),
            telephony=MockTelephony(), bus=InProcessBus(),
        )
        self.assertEqual(providers.summary()["audio_scene"], "mock")


class _StubScene:
    """Minimal AudioScene stub returning a fixed result for ensemble tests."""

    def __init__(self, name, tags, distress):
        self.name = name
        self._result = AudioSceneResult(tags=tags, distress=distress, source=name)

    async def classify(self, audio_b64):
        return self._result


class TestEnsembleAudioScene(unittest.IsolatedAsyncioTestCase):
    async def test_merges_tags_by_max_score_and_ors_distress(self):
        a = _StubScene("yamnet", [("Thud", 0.4), ("Speech", 0.7)], distress=False)
        b = _StubScene("panns", [("Thud", 0.9), ("Groan", 0.6)], distress=True)
        ens = EnsembleAudioScene([a, b])
        self.assertEqual(ens.name, "ensemble(yamnet+panns)")
        res = await ens.classify("x")
        tag_map = dict(res.tags)
        self.assertEqual(tag_map["Thud"], 0.9)  # max across backends
        self.assertIn("Groan", tag_map)
        self.assertIn("Speech", tag_map)
        self.assertTrue(res.distress)  # OR of members
        self.assertEqual(res.source, "yamnet+panns")

    async def test_distress_false_when_no_member_flags(self):
        a = _StubScene("yamnet", [("Speech", 0.8)], distress=False)
        b = _StubScene("panns", [("Music", 0.5)], distress=False)
        res = await EnsembleAudioScene([a, b]).classify("x")
        self.assertFalse(res.distress)

    async def test_requires_at_least_one_member(self):
        with self.assertRaises(ValueError):
            EnsembleAudioScene([])


class AutoRespondWS:
    def __init__(self, transcript: str) -> None:
        self.transcript = transcript
        self.session = None

    async def send_text(self, text: str) -> None:
        msg = json.loads(text)
        if msg.get("type") == "listen":
            asyncio.create_task(self._respond(msg["prompt_id"]))

    async def _respond(self, prompt_id: str) -> None:
        for _ in range(200):
            if self.session and prompt_id in self.session._pending:
                self.session.on_audio_response(
                    prompt_id, _b64(f"QC-SCENARIO-TRANSCRIPT: {self.transcript}")
                )
                return
            await asyncio.sleep(0.005)


class TestAcousticFusionInFlow(unittest.IsolatedAsyncioTestCase):
    async def test_trigger_clip_classified_as_distress(self):
        providers = Providers(
            llm=MockLLM(), voice=MockVoice(), memory=MockMemory(),
            telephony=MockTelephony(), bus=InProcessBus(),
        )
        registry = SessionRegistry()
        ws = AutoRespondWS("[silence]")
        session = ElderSession(ws, "margaret-01", providers)
        ws.session = session
        registry.set("margaret-01", session)
        # Trigger clip carries an explicit distress audio hint.
        trigger = TriggerMessage(
            type="trigger", elder_id="margaret-01", trigger_source="fall",
            audio_clip_b64=_b64("QC-SCENARIO-AUDIO: Thud:0.9,Groan:0.6"),
        )
        await handle_trigger(session, trigger)
        ev = session.acoustic_evidence
        self.assertIn("trigger", ev)
        self.assertTrue(ev["trigger"]["distress"])
        # The check-in response was also classified.
        self.assertIn("last_checkin", ev)


@unittest.skipUnless(
    os.environ.get("RUN_LIVE_TESTS") == "1" and Settings().has_yamnet,
    "live YAMNet disabled (set RUN_LIVE_TESTS=1 + YAMNET_MODEL_PATH/LABELS_PATH)",
)
class TestYamnetLive(unittest.IsolatedAsyncioTestCase):
    async def test_classifies_real_wav(self):
        from app.providers.audio_scene import YamnetAudioScene
        from app.providers.voice import DeepgramVoice

        s = Settings()
        scene = YamnetAudioScene(s.yamnet_model_path, s.yamnet_labels_path)
        # Use Deepgram TTS to produce a real WAV if available, else skip body.
        if s.has_deepgram:
            wav_b64 = await DeepgramVoice(s.deepgram_api_key).synthesize("hello there")
            res = await scene.classify(wav_b64)
            self.assertEqual(res.source, "yamnet")
            self.assertTrue(len(res.tags) > 0)


def _panns_available() -> bool:
    try:
        import panns_inference  # noqa: F401

        return True
    except Exception:
        return False


@unittest.skipUnless(
    os.environ.get("RUN_LIVE_TESTS") == "1" and _panns_available(),
    "live PANNs disabled (set RUN_LIVE_TESTS=1 + pip install panns-inference torch)",
)
class TestPannsLive(unittest.IsolatedAsyncioTestCase):
    async def test_classifies_real_wav(self):
        from app.providers.audio_scene import PannsAudioScene
        from app.providers.voice import DeepgramVoice

        s = Settings()
        scene = PannsAudioScene(s.panns_checkpoint_path)
        if s.has_deepgram:
            wav_b64 = await DeepgramVoice(s.deepgram_api_key).synthesize("hello there")
            res = await scene.classify(wav_b64)
            self.assertEqual(res.source, "panns")
            self.assertTrue(len(res.tags) > 0)


if __name__ == "__main__":
    unittest.main()
