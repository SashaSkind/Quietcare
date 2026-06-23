"""Telephony provider: Twilio SMS/voice with a logging mock fallback."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger("quietcare.telephony")


def _escape_xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _say_twiml(text: str) -> str:
    return f"<Response><Say>{_escape_xml(text)}</Say></Response>"


@dataclass
class TelephonyResult:
    ok: bool
    detail: str
    mocked: bool
    call_sid: str = ""
    answered: bool | None = None


class Telephony(ABC):
    name: str = "telephony"

    @abstractmethod
    async def send_sms(self, text: str) -> TelephonyResult:
        ...

    @abstractmethod
    async def call_voice(self, summary: str) -> TelephonyResult:
        ...

    async def call_voice_wait_for_answer(
        self, summary: str, timeout_s: int
    ) -> TelephonyResult:
        return await self.call_voice(summary)

    @abstractmethod
    async def dispatch_emergency(self, summary: str) -> TelephonyResult:
        """Place the configured emergency call after confirmation or an enabled fallback policy."""
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

        twiml = _say_twiml(summary)

        def _call() -> str:
            call = self._client.calls.create(
                twiml=twiml, from_=self._from, to=self._to
            )
            return call.sid

        sid = await asyncio.to_thread(_call)
        logger.info("Twilio call placed (sid=%s)", sid)
        return TelephonyResult(ok=True, detail=f"call sid={sid}", mocked=False, call_sid=sid)

    async def call_voice_wait_for_answer(
        self, summary: str, timeout_s: int
    ) -> TelephonyResult:
        import asyncio
        import time

        twiml = _say_twiml(summary)
        ring_timeout = max(5, min(int(timeout_s), 60))

        def _call() -> str:
            call = self._client.calls.create(
                twiml=twiml, from_=self._from, to=self._to, timeout=ring_timeout
            )
            return call.sid

        sid = await asyncio.to_thread(_call)
        logger.info("Twilio caretaker call placed (sid=%s); waiting for answer", sid)
        deadline = time.monotonic() + max(1, int(timeout_s))
        unanswered = {"busy", "failed", "no-answer", "canceled"}
        while time.monotonic() < deadline:
            status = await asyncio.to_thread(lambda: self._client.calls(sid).fetch().status)
            if status in ("in-progress", "completed"):
                logger.info("Twilio caretaker call answered (sid=%s status=%s)", sid, status)
                return TelephonyResult(
                    ok=True,
                    detail=f"caretaker answered sid={sid} status={status}",
                    mocked=False,
                    call_sid=sid,
                    answered=True,
                )
            if status in unanswered:
                logger.warning("Twilio caretaker call not answered (sid=%s status=%s)", sid, status)
                return TelephonyResult(
                    ok=False,
                    detail=f"caretaker not answered sid={sid} status={status}",
                    mocked=False,
                    call_sid=sid,
                    answered=False,
                )
            await asyncio.sleep(2)

        try:
            await asyncio.to_thread(lambda: self._client.calls(sid).update(status="completed"))
        except Exception:
            logger.debug("Twilio caretaker call timeout cancel failed", exc_info=True)
        logger.warning("Twilio caretaker call timed out without answer (sid=%s)", sid)
        return TelephonyResult(
            ok=False,
            detail=f"caretaker not answered before timeout sid={sid}",
            mocked=False,
            call_sid=sid,
            answered=False,
        )

    async def dispatch_emergency(self, summary: str) -> TelephonyResult:
        import asyncio

        # Safety: without an explicitly configured emergency number we never
        # place a real call — we log the intent instead.
        if not self._emergency:
            logger.warning("WOULD CALL EMERGENCY (no EMERGENCY_NUMBER set): %s", summary)
            return TelephonyResult(
                ok=True, detail="emergency mocked (no number configured)", mocked=True
            )
        twiml = _say_twiml(f"Emergency dispatch. {summary}")

        def _call() -> str:
            call = self._client.calls.create(
                twiml=twiml, from_=self._from, to=self._emergency
            )
            return call.sid

        sid = await asyncio.to_thread(_call)
        logger.info("Twilio EMERGENCY call placed (sid=%s)", sid)
        return TelephonyResult(ok=True, detail=f"emergency call sid={sid}", mocked=False, call_sid=sid)


class MockTelephony(Telephony):
    name = "mock"

    def __init__(self, caretaker_answers: bool = True) -> None:
        self.caretaker_answers = caretaker_answers

    async def send_sms(self, text: str) -> TelephonyResult:
        logger.warning("WOULD SEND SMS -> caretaker: %s", text)
        print(f"[TELEPHONY MOCK] WOULD SEND SMS: {text}")
        return TelephonyResult(ok=True, detail="mock sms", mocked=True)

    async def call_voice(self, summary: str) -> TelephonyResult:
        logger.warning("WOULD CALL caretaker: %s", summary)
        print(f"[TELEPHONY MOCK] WOULD CALL: {summary}")
        return TelephonyResult(ok=True, detail="mock call", mocked=True, answered=True)

    async def call_voice_wait_for_answer(
        self, summary: str, timeout_s: int
    ) -> TelephonyResult:
        await self.call_voice(summary)
        if self.caretaker_answers:
            return TelephonyResult(
                ok=True, detail="mock caretaker answered", mocked=True, answered=True
            )
        return TelephonyResult(
            ok=False, detail="mock caretaker no answer", mocked=True, answered=False
        )

    async def dispatch_emergency(self, summary: str) -> TelephonyResult:
        logger.warning("WOULD DISPATCH EMERGENCY: %s", summary)
        print(f"[TELEPHONY MOCK] WOULD DISPATCH EMERGENCY: {summary}")
        return TelephonyResult(ok=True, detail="mock emergency", mocked=True)
