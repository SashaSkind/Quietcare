"""Mock Quietcare client: drives the backend over the WebSocket protocol.

Usage:
    python mock/send_trigger.py --scenario fine
    python mock/send_trigger.py --scenario emergency [--url ws://localhost:8080/ws]

It connects to /ws, registers, sends a trigger (with a short sample WAV), and
auto-answers any `listen` with a canned response for the chosen scenario. It
prints the full exchange and a clear verdict on whether the caretaker/Twilio
path was taken (watch the SERVER console for the actual "WOULD SEND/CALL" lines).
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
from datetime import datetime, timezone

import websockets

ELDER_ID = "margaret-01"

# A tiny silent WAV used as the pre-event audio clip (acoustic context only).
SAMPLE_WAV_B64 = base64.b64encode(
    b"RIFF" + (36).to_bytes(4, "little") + b"WAVE"
    b"fmt " + (16).to_bytes(4, "little")
    + (1).to_bytes(2, "little") + (1).to_bytes(2, "little")
    + (8000).to_bytes(4, "little") + (16000).to_bytes(4, "little")
    + (2).to_bytes(2, "little") + (16).to_bytes(2, "little")
    + b"data" + (0).to_bytes(4, "little")
).decode("ascii")

# The mock backend's MockVoice decodes this prefix to produce a transcript,
# letting us simulate STT without a real model.
SCENARIO_REPLIES = {
    "fine": "I'm fine, just dropped a pot.",
    "emergency": "",  # silence -> no clear response -> escalation
}


def _hint(transcript: str) -> str:
    return base64.b64encode(
        (f"QC-SCENARIO-TRANSCRIPT:{transcript}").encode("utf-8")
    ).decode("ascii")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _p(direction: str, payload: dict) -> None:
    arrow = "->" if direction == "out" else "<-"
    print(f"  {arrow} {json.dumps(payload)}")


async def run(url: str, scenario: str) -> int:
    reply_transcript = SCENARIO_REPLIES[scenario]
    print(f"\n=== Quietcare mock client | scenario={scenario} | {url} ===")
    last_status = None

    async with websockets.connect(url) as ws:
        # 1) register
        reg = {"type": "register", "elder_id": ELDER_ID}
        await ws.send(json.dumps(reg))
        _p("out", reg)

        # 2) trigger
        trigger = {
            "type": "trigger",
            "elder_id": ELDER_ID,
            "ts": _now(),
            "trigger_source": "fall",
            "audio_clip_b64": SAMPLE_WAV_B64,
            "frame_b64": None,
            "device_state": {"battery": 0.82, "connectivity": "wifi"},
        }
        await ws.send(json.dumps(trigger))
        _p("out", trigger)

        # 3) react to backend messages
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=20.0)
            except asyncio.TimeoutError:
                print("  (timeout waiting for backend)")
                break

            msg = json.loads(raw)
            _p("in", msg)
            mtype = msg.get("type")

            if mtype == "status":
                last_status = msg.get("state")
                if last_status in ("resolved", "escalating"):
                    # Give the server a moment to finish the caretaker-agent.
                    await asyncio.sleep(0.3)
                    break

            elif mtype == "listen":
                response = {
                    "type": "audio_response",
                    "elder_id": ELDER_ID,
                    "ts": _now(),
                    "prompt_id": msg.get("prompt_id"),
                    "audio_clip_b64": _hint(reply_transcript),
                }
                await ws.send(json.dumps(response))
                shown = reply_transcript or "[silence]"
                print(f"     (answered listen with: {shown!r})")

    # 4) verdict
    print("\n--- RESULT ---")
    print(f"final status: {last_status}")
    if last_status == "escalating":
        print("CARETAKER PATH TAKEN -> Twilio invoked "
              "(see server log for 'WOULD SEND/CALL' or real SMS/CALL).")
    elif last_status == "resolved":
        print("RESOLVED SILENTLY -> no caretaker notification, no Twilio.")
    else:
        print("Inconclusive (no terminal status received).")
    print("--------------\n")

    expected = "escalating" if scenario == "emergency" else "resolved"
    return 0 if last_status == expected else 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario", choices=["fine", "emergency"], default="fine"
    )
    parser.add_argument("--url", default="ws://localhost:8080/ws")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.url, args.scenario)))


if __name__ == "__main__":
    main()
