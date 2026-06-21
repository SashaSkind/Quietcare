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

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "mocked": self.mocked,
            "source": self.source,
            "sanction_id": self.sanction_id,
        }


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
    """In-process sanction gate enforcing deterministic, code-level policy.

    Allows by default (so the safety loop is never silently broken), but any
    action in ``blocked_actions`` is hard-blocked — a kill-switch that physically
    prevents that escalation from firing, independent of the LLM.
    """

    name = "local"

    def __init__(self, blocked_actions: Optional[set[str]] = None) -> None:
        self._blocked = set(blocked_actions or set())

    async def sanction(self, action: str, context: dict[str, Any]) -> GateDecision:
        if action in self._blocked:
            logger.warning("policy gate (local) BLOCK action=%s (kill-switch)", action)
            return GateDecision(
                allowed=False,
                reason=f"action '{action}' blocked by local policy kill-switch",
                mocked=False,
                source="local",
            )
        logger.info("policy gate (local) ALLOW action=%s", action)
        return GateDecision(allowed=True, reason="local policy allow", mocked=False, source="local")
