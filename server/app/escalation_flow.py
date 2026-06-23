from __future__ import annotations

import logging
from typing import Any

from .providers.factory import Providers

logger = logging.getLogger("quietcare.escalation")


async def call_caretaker_with_emergency_fallback(
    *,
    providers: Providers,
    elder_id: str,
    summary: str,
    severity: str = "high",
    trigger_source: str = "manual",
    hard_fall: bool = False,
    auto_emergency_fallback: bool = False,
    caretaker_ack_timeout_seconds: int = 30,
) -> dict[str, Any]:
    caretaker = await providers.telephony.call_voice_wait_for_answer(
        summary, caretaker_ack_timeout_seconds
    )
    result: dict[str, Any] = {
        "caretaker_call": {
            "ok": caretaker.ok,
            "mocked": caretaker.mocked,
            "detail": caretaker.detail,
            "answered": caretaker.answered,
            "call_sid": caretaker.call_sid,
        },
        "emergency_dispatch": None,
    }

    if caretaker.answered is not False:
        return result

    if not auto_emergency_fallback:
        result["emergency_dispatch"] = {
            "status": "skipped",
            "reason": "auto emergency fallback disabled",
        }
        return result

    decision = await providers.policy_gate.sanction(
        "emergency_dispatch",
        {
            "elder_id": elder_id,
            "severity": severity,
            "summary": summary,
            "reason": "caretaker did not answer escalation call",
            "trigger_source": trigger_source,
            "hard_fall": hard_fall,
            "caretaker_answered": False,
            "auto_fallback": True,
        },
    )
    if not decision.allowed:
        logger.warning(
            "emergency fallback BLOCKED for %s after caretaker no-answer: %s",
            elder_id,
            decision.reason,
        )
        result["emergency_dispatch"] = {
            "status": "blocked_by_policy",
            "reason": decision.reason,
            "decision": decision.to_dict(),
        }
        return result

    emergency = await providers.telephony.dispatch_emergency(summary)
    result["emergency_dispatch"] = {
        "status": "dispatched",
        "ok": emergency.ok,
        "mocked": emergency.mocked,
        "detail": emergency.detail,
        "call_sid": emergency.call_sid,
        "decision": decision.to_dict(),
    }
    logger.warning(
        "emergency fallback dispatched for %s after caretaker no-answer: %s",
        elder_id,
        emergency.detail,
    )
    return result
