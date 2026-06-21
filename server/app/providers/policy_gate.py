"""PolicyGate provider: a sanction gate for high-stakes escalation actions.

This is the ArmorIQ integration point — the gate that *physically* prevents an
escalation (notifying the human caretaker, or an emergency dispatch) from firing
without sanction. Every irreversible escalation action asks the gate for
approval first; a denial blocks the action in code, independent of the LLM.

When no ArmorIQ credentials are configured, a MockPolicyGate allows everything
(and logs), so the system runs unchanged with zero setup.
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
    """Allow-all gate (logs). Keeps the system running without ArmorIQ creds."""

    name = "mock"

    async def sanction(self, action: str, context: dict[str, Any]) -> GateDecision:
        logger.info("policy gate (mock) ALLOW action=%s", action)
        return GateDecision(allowed=True, reason="mock allow", mocked=True, source="mock")


class ArmorIQPolicyGate(PolicyGate):
    """ArmorIQ-backed sanction gate.

    Calls ArmorIQ's policy endpoint with the action + context and interprets the
    decision. The HTTP contract is intentionally tolerant of common response
    shapes; adjust ``_endpoint`` / parsing to match your ArmorIQ deployment.

    fail_open controls behavior when ArmorIQ is unreachable: True lets the action
    proceed (so a gate outage never blocks reaching help — safer for the elder),
    False blocks (strict "no escalation without sanction").
    """

    name = "armoriq"

    def __init__(self, api_key: str, base_url: str, fail_open: bool = True) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._fail_open = fail_open

    @property
    def _endpoint(self) -> str:
        return f"{self._base_url}/v1/sanction"

    async def sanction(self, action: str, context: dict[str, Any]) -> GateDecision:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    self._endpoint,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"action": action, "context": context},
                )
            if resp.status_code != 200:
                return self._on_error(f"ArmorIQ HTTP {resp.status_code}")
            data = resp.json()
            # Tolerate {"allowed": bool} or {"decision": "allow"|"deny"}.
            allowed = data.get("allowed")
            if allowed is None:
                allowed = str(data.get("decision", "")).lower() in ("allow", "allowed")
            reason = data.get("reason", "armoriq decision")
            sanction_id = data.get("id") or data.get("sanction_id")
            logger.info("policy gate (armoriq) action=%s allowed=%s", action, allowed)
            return GateDecision(
                allowed=bool(allowed),
                reason=str(reason),
                mocked=False,
                source="armoriq",
                sanction_id=sanction_id,
            )
        except Exception as exc:  # pragma: no cover - network
            return self._on_error(f"ArmorIQ error: {exc}")

    def _on_error(self, detail: str) -> GateDecision:
        logger.warning("%s; fail_open=%s", detail, self._fail_open)
        return GateDecision(
            allowed=self._fail_open,
            reason=detail + (" (fail-open)" if self._fail_open else " (fail-closed)"),
            mocked=False,
            source="armoriq",
        )
