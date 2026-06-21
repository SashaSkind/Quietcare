"""Telephony provider: Twilio SMS/voice with a logging mock fallback."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger("quietcare.telephony")


@dataclass
class TelephonyResult:
    ok: bool
    detail: str
    mocked: bool


class Telephony(ABC):
    name: str = "telephony"

    @abstractmethod
    async def send_sms(self, text: str) -> TelephonyResult:
        ...

    @abstractmethod
    async def call_voice(self, summary: str) -> TelephonyResult:
        ...

    @abstractmethod
    async def dispatch_emergency(self, summary: str) -> TelephonyResult:
        """Place the gated emergency call. Only invoked after explicit human
        confirmation (enforced by the state machine + confirmation registry)."""
        ...


class TwilioTelephony(Telephony):
    name = "twilio"

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
        to_number: str,
        emergency_number: str = "",
    ) -> None:
        from twilio.rest import Client  # lazy import

        self._client = Client(account_sid, auth_token)
        self._from = from_number
        self._to = to_number
        self._emergency = emergency_number

    async def send_sms(self, text: str) -> TelephonyResult:
        import asyncio

        def _send() -> str:
            msg = self._client.messages.create(
                body=text, from_=self._from, to=self._to
            )
            return msg.sid

        sid = await asyncio.to_thread(_send)
        logger.info("Twilio SMS sent (sid=%s)", sid)
        return TelephonyResult(ok=True, detail=f"SMS sent sid={sid}", mocked=False)

    async def call_voice(self, summary: str) -> TelephonyResult:
        import asyncio

        twiml = f"<Response><Say>{summary}</Say></Response>"

        def _call() -> str:
            call = self._client.calls.create(
                twiml=twiml, from_=self._from, to=self._to
            )
            return call.sid

        sid = await asyncio.to_thread(_call)
        logger.info("Twilio call placed (sid=%s)", sid)
        return TelephonyResult(ok=True, detail=f"call sid={sid}", mocked=False)

    async def dispatch_emergency(self, summary: str) -> TelephonyResult:
        import asyncio

        # Safety: without an explicitly configured emergency number we never
        # place a real call — we log the intent instead.
        if not self._emergency:
            logger.warning("WOULD CALL EMERGENCY (no EMERGENCY_NUMBER set): %s", summary)
            return TelephonyResult(
                ok=True, detail="emergency mocked (no number configured)", mocked=True
            )
        twiml = f"<Response><Say>Emergency dispatch. {summary}</Say></Response>"

        def _call() -> str:
            call = self._client.calls.create(
                twiml=twiml, from_=self._from, to=self._emergency
            )
            return call.sid

        sid = await asyncio.to_thread(_call)
        logger.info("Twilio EMERGENCY call placed (sid=%s)", sid)
        return TelephonyResult(ok=True, detail=f"emergency call sid={sid}", mocked=False)


class MockTelephony(Telephony):
    name = "mock"

    async def send_sms(self, text: str) -> TelephonyResult:
        logger.warning("WOULD SEND SMS -> caretaker: %s", text)
        print(f"[TELEPHONY MOCK] WOULD SEND SMS: {text}")
        return TelephonyResult(ok=True, detail="mock sms", mocked=True)

    async def call_voice(self, summary: str) -> TelephonyResult:
        logger.warning("WOULD CALL caretaker: %s", summary)
        print(f"[TELEPHONY MOCK] WOULD CALL: {summary}")
        return TelephonyResult(ok=True, detail="mock call", mocked=True)

    async def dispatch_emergency(self, summary: str) -> TelephonyResult:
        logger.warning("WOULD DISPATCH EMERGENCY: %s", summary)
        print(f"[TELEPHONY MOCK] WOULD DISPATCH EMERGENCY: {summary}")
        return TelephonyResult(ok=True, detail="mock emergency", mocked=True)
