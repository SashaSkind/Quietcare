"""PolicyGate provider: a sanction gate for high-stakes escalation actions.

The gate *physically* prevents an escalation (notifying the human caretaker, or
an emergency dispatch) from firing without sanction. Every irreversible
escalation action asks the gate for approval first; a denial blocks the action
in code, independent of the LLM.

This is an in-code chokepoint (LocalPolicyGate) — NOT ArmorIQ, which is an MCP
security *scanner* (see providers/security_scan.py), not a per-action gate. The
gate allows by default but a configured kill-switch (policy_block_actions) can
hard-block specific actions. MockPolicyGate (allow-all) is used in tests.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger("quietcare.policy_gate")


@dataclass
class GateDecision:
    allowed: bool
    reason: str
    mocked: bool
    source: str = "none"
    sanction_id: Optional[str] = None
    risk_score: int = 0
    risk_level: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "mocked": self.mocked,
            "source": self.source,
            "sanction_id": self.sanction_id,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
        }


# Deterministic risk model: weighted signals -> 0-100 score.
_SEVERITY_WEIGHT = {"low": 10, "medium": 30, "high": 55}
_SOURCE_WEIGHT = {
    "fall": 30, "inactivity": 25, "audio_event": 15,
    "geofence": 20, "manual": 5, "scheduled": 0,
}
_DISTRESS_KEYWORDS = ("thud", "scream", "groan", "glass", "fell", "help", "unconscious", "no response")


def score_risk(action: str, context: dict[str, Any]) -> tuple[int, str]:
    """Compute a 0-100 risk score + level from escalation context signals."""
    score = 0
    score += _SEVERITY_WEIGHT.get(str(context.get("severity", "")).lower(), 0)
    score += _SOURCE_WEIGHT.get(str(context.get("trigger_source", "")).lower(), 0)
    blob = (str(context.get("summary", "")) + " " + str(context.get("reason", ""))).lower()
    score += sum(8 for k in _DISTRESS_KEYWORDS if k in blob)
    if context.get("hard_fall"):
        score += 15
    if action == "emergency_dispatch":
        score += 20  # by definition a high-stakes action
    score = max(0, min(100, score))
    level = "critical" if score >= 75 else "high" if score >= 50 else "medium" if score >= 25 else "low"
    return score, level


class PolicyGate(ABC):
    name: str = "policy_gate"

    @abstractmethod
    async def sanction(self, action: str, context: dict[str, Any]) -> GateDecision:
        """Return whether ``action`` (e.g. 'escalation', 'emergency_dispatch')
        is sanctioned given ``context``."""
        ...


class MockPolicyGate(PolicyGate):
    """Allow-all gate (logs). Used in tests."""

    name = "mock"

    async def sanction(self, action: str, context: dict[str, Any]) -> GateDecision:
        logger.info("policy gate (mock) ALLOW action=%s", action)
        return GateDecision(allowed=True, reason="mock allow", mocked=True, source="mock")


class LocalPolicyGate(PolicyGate):
    """In-process sanction gate with deterministic risk scoring.

    For every action it computes a 0-100 risk score from the context. It allows
    by default (so the safety loop is never silently broken), but:
      - any action in ``blocked_actions`` is hard-blocked (kill-switch), and
      - an ``emergency_dispatch`` whose risk is below ``emergency_min_risk`` is
        blocked UNLESS the context carries human_confirmed=True (a human already
        approved it out-of-band).
    """

    name = "local"

    def __init__(
        self,
        blocked_actions: Optional[set[str]] = None,
        emergency_min_risk: int = 0,
    ) -> None:
        self._blocked = set(blocked_actions or set())
        self._emergency_min_risk = emergency_min_risk

    async def sanction(self, action: str, context: dict[str, Any]) -> GateDecision:
        score, level = score_risk(action, context)

        if action in self._blocked:
            logger.warning("policy gate (local) BLOCK action=%s (kill-switch)", action)
            return GateDecision(
                allowed=False,
                reason=f"action '{action}' blocked by local policy kill-switch",
                mocked=False, source="local", risk_score=score, risk_level=level,
            )

        if (
            action == "emergency_dispatch"
            and score < self._emergency_min_risk
            and not context.get("human_confirmed")
        ):
            logger.warning(
                "policy gate (local) BLOCK emergency_dispatch: risk %s < min %s",
                score, self._emergency_min_risk,
            )
            return GateDecision(
                allowed=False,
                reason=f"emergency risk {score} below required {self._emergency_min_risk}",
                mocked=False, source="local", risk_score=score, risk_level=level,
            )

        logger.info("policy gate (local) ALLOW action=%s risk=%s(%s)", action, score, level)
        return GateDecision(
            allowed=True, reason=f"allow (risk {score}/{level})",
            mocked=False, source="local", risk_score=score, risk_level=level,
        )
