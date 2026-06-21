"""Unit tests for the WebSocket protocol v1 models / parser.

Run with:  python -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.protocol import (
    AckMessage,
    AudioResponseMessage,
    HeartbeatMessage,
    ListenMessage,
    RegisterMessage,
    SpeakMessage,
    StatusMessage,
    TriggerMessage,
    parse_client_message,
)


class TestInboundParsing(unittest.TestCase):
    def test_parse_register(self):
        msg = parse_client_message({"type": "register", "elder_id": "m-01"})
        self.assertIsInstance(msg, RegisterMessage)
        self.assertEqual(msg.elder_id, "m-01")

    def test_parse_trigger_defaults(self):
        msg = parse_client_message({"type": "trigger", "elder_id": "m-01"})
        self.assertIsInstance(msg, TriggerMessage)
        # Defaults applied.
        self.assertEqual(msg.trigger_source, "manual")
        self.assertIsNone(msg.audio_clip_b64)
        self.assertEqual(msg.device_state.battery, 1.0)
        self.assertEqual(msg.device_state.connectivity, "unknown")

    def test_parse_trigger_full(self):
        msg = parse_client_message(
            {
                "type": "trigger",
                "elder_id": "m-01",
                "trigger_source": "fall",
                "audio_clip_b64": "AAAA",
                "frame_b64": "BBBB",
                "device_state": {"battery": 0.5, "connectivity": "wifi"},
            }
        )
        self.assertEqual(msg.trigger_source, "fall")
        self.assertEqual(msg.audio_clip_b64, "AAAA")
        self.assertEqual(msg.device_state.battery, 0.5)

    def test_parse_audio_response(self):
        msg = parse_client_message(
            {"type": "audio_response", "elder_id": "m-01", "prompt_id": "p1"}
        )
        self.assertIsInstance(msg, AudioResponseMessage)
        self.assertEqual(msg.prompt_id, "p1")

    def test_parse_heartbeat(self):
        msg = parse_client_message({"type": "heartbeat", "elder_id": "m-01"})
        self.assertIsInstance(msg, HeartbeatMessage)

    def test_extra_fields_ignored(self):
        # Lenient inbound parsing: unknown fields don't raise.
        msg = parse_client_message(
            {"type": "register", "elder_id": "m-01", "unexpected": 123}
        )
        self.assertEqual(msg.elder_id, "m-01")

    def test_unknown_type_raises(self):
        with self.assertRaises(ValueError):
            parse_client_message({"type": "nope", "elder_id": "m-01"})

    def test_missing_required_field_raises(self):
        with self.assertRaises(Exception):
            parse_client_message({"type": "register"})


class TestOutboundModels(unittest.TestCase):
    def test_speak_defaults_type(self):
        m = SpeakMessage(prompt_id="p1", audio_b64="AAAA", text="hi")
        self.assertEqual(m.type, "speak")
        self.assertIn('"type":"speak"', m.model_dump_json().replace(" ", ""))

    def test_listen_shape(self):
        m = ListenMessage(prompt_id="p1", duration_ms=6000)
        self.assertEqual(m.type, "listen")
        self.assertEqual(m.duration_ms, 6000)

    def test_status_and_ack(self):
        self.assertEqual(StatusMessage(state="idle").type, "status")
        self.assertEqual(AckMessage(received="trigger").received, "trigger")


if __name__ == "__main__":
    unittest.main()
