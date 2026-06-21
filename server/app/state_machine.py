"""Explicit escalation state machine.

The LLM *decides* transitions (by which tools it calls); this code *enforces*
them and the safety invariants:

  - 911 is never reachable without explicit human confirmation.
  - Every escalation passes through a check-in first, UNLESS the trigger is an
    unambiguous hard fall with no motion (``hard_fall``).

Flow:
  idle -> triggered -> checking_in -> (resolved | escalating)
                    \-> escalating (only if hard_fall)
  escalating -> caretaker_notified -> (human_ack | 911_gated)
"""

from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger("quietcare.fsm")


class State(str, Enum):
    IDLE = "idle"
    TRIGGERED = "triggered"
    CHECKING_IN = "checking_in"
    RESOLVED = "resolved"
    ESCALATING = "escalating"
    CARETAKER_NOTIFIED = "caretaker_notified"
    HUMAN_ACK = "human_ack"
    GATED_911 = "911_gated"


# Map internal states to the protocol-facing client status enum.
CLIENT_STATUS = {
    State.IDLE: "idle",
    State.TRIGGERED: "checking_in",
    State.CHECKING_IN: "checking_in",
    State.RESOLVED: "resolved",
    State.ESCALATING: "escalating",
    State.CARETAKER_NOTIFIED: "escalating",
    State.HUMAN_ACK: "escalating",
    State.GATED_911: "escalating",
}


class InvalidTransition(Exception):
    pass


_ALLOWED: dict[State, set[State]] = {
    State.IDLE: {State.TRIGGERED},
    State.TRIGGERED: {State.CHECKING_IN, State.ESCALATING},
    State.CHECKING_IN: {State.RESOLVED, State.ESCALATING},
    State.RESOLVED: set(),
    State.ESCALATING: {State.CARETAKER_NOTIFIED},
    State.CARETAKER_NOTIFIED: {State.HUMAN_ACK, State.GATED_911},
    State.HUMAN_ACK: set(),
    State.GATED_911: set(),
}


class EscalationStateMachine:
    def __init__(self, elder_id: str) -> None:
        self.elder_id = elder_id
        self.state = State.IDLE
        self.history: list[State] = [State.IDLE]
        self._passed_checkin = False

    def _transition(self, target: State) -> None:
        if target not in _ALLOWED[self.state]:
            raise InvalidTransition(
                f"{self.elder_id}: cannot go {self.state.value} -> {target.value}"
            )
        logger.info("FSM[%s]: %s -> %s", self.elder_id, self.state.value, target.value)
        self.state = target
        self.history.append(target)

    # ---- transitions ----
    def trigger(self) -> None:
        self._transition(State.TRIGGERED)

    def begin_checkin(self) -> None:
        self._transition(State.CHECKING_IN)
        self._passed_checkin = True

    def resolve(self) -> None:
        self._transition(State.RESOLVED)

    def escalate(self, *, hard_fall: bool = False) -> None:
        # Invariant: escalation must follow a check-in unless hard fall.
        if self.state == State.TRIGGERED and not hard_fall:
            raise InvalidTransition(
                f"{self.elder_id}: escalation requires a check-in first "
                "(no hard_fall override)"
            )
        self._transition(State.ESCALATING)

    def caretaker_notified(self) -> None:
        self._transition(State.CARETAKER_NOTIFIED)

    def human_ack(self) -> None:
        self._transition(State.HUMAN_ACK)

    def gate_911(self, *, human_confirmed: bool) -> None:
        # Hard safety invariant enforced in code regardless of LLM intent.
        if not human_confirmed:
            raise InvalidTransition(
                f"{self.elder_id}: 911 requires explicit human confirmation"
            )
        self._transition(State.GATED_911)

    @property
    def client_status(self) -> str:
        return CLIENT_STATUS[self.state]

    def trace(self) -> str:
        return " -> ".join(s.value for s in self.history)
