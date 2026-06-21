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


class TwilioTelephony(Telephony):
    name = "twilio"

    def __init__(
        self, account_sid: str, auth_token: str, from_number: str, to_number: str
    ) -> None:
        from twilio.rest import Client  # lazy import

        self._client = Client(account_sid, auth_token)
        self._from = from_number
        self._to = to_number

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
