"""Fake-phone WebSocket client for end-to-end voice pipeline testing.

Simulates the iOS app *network-wise*: connects to the backend /ws, registers as
an elder, then sends a `voice_conversation` frame carrying a REAL spoken WAV
clip (synthesized via the same Deepgram TTS the app plays). This exercises the
full backend path the phone relies on -- STT -> conversation agent -> TTS --
without depending on the flaky on-device microphone capture.

Run (backend must already be running on :8080):
    source .venv/bin/activate
    python -m scripts.fake_phone "Hello Quietcare, how are you today?"

Notes:
- Uses the safe `chat` path only. Help/emergency phrases are intentionally NOT
  sent here because escalation would trigger real caretaker SMS/calls.
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys

import websockets

from app.config import settings
from app.providers.voice import DeepgramVoice

WS_URL = "ws://localhost:8080/ws"
ELDER_ID = "margaret-01"

DEFAULT_PHRASES = [
    "Hello Quietcare, how are you doing today?",
    "I'm feeling a little tired but I am okay.",
]


async def synth_clip(text: str) -> str:
    """Produce a base64 WAV of spoken `text` -- stands in for a phone mic clip."""
    voice = DeepgramVoice(settings.deepgram_api_key)
    audio_b64 = await voice.synthesize(text)
    raw = base64.b64decode(audio_b64)
    print(f"  synth '{text}' -> {len(raw)} WAV bytes ({len(audio_b64)} b64 chars)")
    return audio_b64


async def run(phrases: list[str]) -> int:
    print(f"connecting to {WS_URL} as {ELDER_ID} ...")
    async with websockets.connect(WS_URL, max_size=16 * 1024 * 1024) as ws:
        await ws.send(json.dumps({"type": "register", "elder_id": ELDER_ID}))
        # drain the initial status frame
        first = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        print(f"  registered; first server frame: {first.get('type')}")

        failures = 0
        for phrase in phrases:
            print(f"\n--- sending spoken clip: {phrase!r} ---")
            clip = await synth_clip(phrase)
            await ws.send(
                json.dumps(
                    {
                        "type": "voice_conversation",
                        "elder_id": ELDER_ID,
                        "ts": "2026-01-01T00:00:00Z",
                        "audio_clip_b64": clip,
                    }
                )
            )
            # wait for the voice_conversation_reply (ignore other frames)
            reply = None
            for _ in range(10):
                frame = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                if frame.get("type") == "voice_conversation_reply":
                    reply = frame
                    break
                print(f"  (ignoring {frame.get('type')})")
            if not reply:
                print("  ERROR: no voice_conversation_reply received")
                failures += 1
                continue
            transcript = reply.get("transcript", "")
            reply_text = reply.get("reply_text", "")
            action = reply.get("action")
            audio_len = len(reply.get("audio_b64", ""))
            print(f"  STT transcript : {transcript!r}")
            print(f"  agent action   : {action}")
            print(f"  reply_text     : {reply_text!r}")
            print(f"  reply audio    : {audio_len} b64 chars")
            if not transcript:
                print("  RESULT: FAIL -- backend transcribed nothing")
                failures += 1
            else:
                print("  RESULT: OK -- round trip transcribed + replied")
        return failures


def main() -> None:
    phrases = sys.argv[1:] or DEFAULT_PHRASES
    failures = asyncio.run(run(phrases))
    print(f"\n=== done: {len(phrases) - failures}/{len(phrases)} clips transcribed OK ===")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
