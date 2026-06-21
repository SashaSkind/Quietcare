"""Live proof that the gated emergency-dispatch call works.

Builds TwilioTelephony from the live settings and invokes dispatch_emergency()
— the exact call confirm_911() makes after the human + policy + FSM gates pass.
This dials the configured EMERGENCY_NUMBER for real, so only run it when that
number is a phone you control (NOT a real 911/PSAP line).

Run:  python scripts/verify_emergency_call.py
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.providers.telephony import TwilioTelephony


async def main() -> None:
    if not settings.has_twilio:
        print("Twilio not configured (has_twilio=False); aborting.")
        return
    if not settings.emergency_number:
        print("EMERGENCY_NUMBER not set; dispatch would be mocked. Aborting.")
        return

    tel = TwilioTelephony(
        settings.twilio_account_sid,
        settings.twilio_auth_token,
        settings.twilio_from_number,
        settings.twilio_caretaker_number,
        settings.emergency_number,
    )
    summary = (
        "This is a Quietcare test of the emergency dispatch path. "
        "Margaret may have fallen and did not respond to a check-in. "
        "This is a demonstration call, not a real emergency."
    )
    print(f"placing emergency-dispatch call to EMERGENCY_NUMBER (from {settings.twilio_from_number}) ...")
    res = await tel.dispatch_emergency(summary)
    print(f"  ok={res.ok} mocked={res.mocked} detail={res.detail}")


if __name__ == "__main__":
    asyncio.run(main())
