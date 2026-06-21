"""Unit tests for the escalation state machine safety invariants.

Run with:  python -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.state_machine import EscalationStateMachine, InvalidTransition, State


class TestEscalationStateMachine(unittest.TestCase):
    def _fresh(self) -> EscalationStateMachine:
        return EscalationStateMachine("margaret-01")

    def test_happy_resolve_path(self):
        sm = self._fresh()
        sm.trigger()
        sm.begin_checkin()
        sm.resolve()
        self.assertEqual(sm.state, State.RESOLVED)
        self.assertEqual(sm.client_status, "resolved")

    def test_happy_escalate_path(self):
        sm = self._fresh()
        sm.trigger()
        sm.begin_checkin()
        sm.escalate()
        sm.caretaker_notified()
        self.assertEqual(sm.state, State.CARETAKER_NOTIFIED)
        self.assertEqual(sm.client_status, "escalating")

    def test_escalation_requires_checkin(self):
        sm = self._fresh()
        sm.trigger()
        # No check-in yet, and not a hard fall -> must refuse.
        with self.assertRaises(InvalidTransition):
            sm.escalate(hard_fall=False)

    def test_hard_fall_may_bypass_checkin(self):
        sm = self._fresh()
        sm.trigger()
        sm.escalate(hard_fall=True)  # allowed for unambiguous hard fall
        self.assertEqual(sm.state, State.ESCALATING)

    def test_911_blocked_without_human_confirmation(self):
        sm = self._fresh()
        sm.trigger()
        sm.begin_checkin()
        sm.escalate()
        sm.caretaker_notified()
        with self.assertRaises(InvalidTransition):
            sm.gate_911(human_confirmed=False)
        self.assertNotEqual(sm.state, State.GATED_911)

    def test_911_allowed_with_human_confirmation(self):
        sm = self._fresh()
        sm.trigger()
        sm.begin_checkin()
        sm.escalate()
        sm.caretaker_notified()
        sm.gate_911(human_confirmed=True)
        self.assertEqual(sm.state, State.GATED_911)

    def test_911_not_reachable_directly(self):
        sm = self._fresh()
        sm.trigger()
        # Cannot jump straight to 911 even with confirmation (wrong state).
        with self.assertRaises(InvalidTransition):
            sm.gate_911(human_confirmed=True)

    def test_no_transition_out_of_resolved(self):
        sm = self._fresh()
        sm.trigger()
        sm.begin_checkin()
        sm.resolve()
        with self.assertRaises(InvalidTransition):
            sm.escalate(hard_fall=True)


if __name__ == "__main__":
    unittest.main()
