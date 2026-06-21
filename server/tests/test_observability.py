"""Tests for Arize observability graceful degradation.

Verifies that with no ARIZE_* keys the tracer is never initialized and the
agent/tool span helpers are pure no-ops (yielding None, never raising), so the
system runs identically with zero observability config.

Run with:  python -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.observability as obs
from app.config import Settings


class TestHasArizeFlag(unittest.TestCase):
    def test_disabled_when_keys_absent(self):
        s = Settings(_env_file=None)
        self.assertFalse(s.has_arize)

    def test_enabled_when_both_keys_present(self):
        s = Settings(_env_file=None, arize_space_id="sp", arize_api_key="key")
        self.assertTrue(s.has_arize)

    def test_disabled_when_only_one_key(self):
        self.assertFalse(Settings(_env_file=None, arize_space_id="sp").has_arize)
        self.assertFalse(Settings(_env_file=None, arize_api_key="key").has_arize)


class TestInitTracingNoOp(unittest.TestCase):
    def setUp(self):
        self._orig_settings = obs.settings
        self._orig_init = obs._initialized
        self._orig_tracer = obs._tracer
        obs.settings = Settings(_env_file=None)
        obs._initialized = False
        obs._tracer = None

    def tearDown(self):
        obs.settings = self._orig_settings
        obs._initialized = self._orig_init
        obs._tracer = self._orig_tracer

    def test_init_is_noop_without_keys(self):
        obs.init_tracing()
        self.assertFalse(obs._initialized)
        self.assertIsNone(obs._tracer)


class TestSpanHelpersNoOp(unittest.TestCase):
    def setUp(self):
        self._orig_tracer = obs._tracer
        obs._tracer = None  # ensure inactive

    def tearDown(self):
        obs._tracer = self._orig_tracer

    def test_agent_span_yields_none(self):
        with obs.agent_span("elder", "prompt") as span:
            self.assertIsNone(span)
            obs.record_output(span, "out")  # must not raise on None

    def test_tool_span_yields_none(self):
        with obs.tool_span("speak_to_elder", {"text": "hi"}) as span:
            self.assertIsNone(span)

    def test_record_output_on_none_is_safe(self):
        obs.record_output(None, {"any": "value"})


if __name__ == "__main__":
    unittest.main()
