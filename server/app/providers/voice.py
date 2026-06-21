"""Voice provider: Deepgram STT + TTS, with a mock fallback.

All STT/TTS happens on the backend (per the shared contract). The client only
plays and records audio.
"""

from __future__ import annotations

import base64
from abc import ABC, abstractmethod

# A tiny valid silent WAV (44-byte header, no samples) used by the mock TTS.
_SILENT_WAV = base64.b64encode(
    b"RIFF" + (36).to_bytes(4, "little") + b"WAVE"
    b"fmt " + (16).to_bytes(4, "little")
    + (1).to_bytes(2, "little") + (1).to_bytes(2, "little")
    + (8000).to_bytes(4, "little") + (16000).to_bytes(4, "little")
    + (2).to_bytes(2, "little") + (16).to_bytes(2, "little")
    + b"data" + (0).to_bytes(4, "little")
).decode("ascii")


class Voice(ABC):
    name: str = "voice"

    @abstractmethod
    async def transcribe(self, audio_b64: str | None) -> str:
        ...

    @abstractmethod
    async def synthesize(self, text: str) -> str:
        ...


class DeepgramVoice(Voice):
    name = "deepgram"

    def __init__(self, api_key: str) -> None:
        from deepgram import DeepgramClient  # lazy import

        self._client = DeepgramClient(api_key)

    async def transcribe(self, audio_b64: str | None) -> str:
        if not audio_b64:
            return ""
        from deepgram import PrerecordedOptions

        audio = base64.b64decode(audio_b64)
        source = {"buffer": audio, "mimetype": "audio/wav"}
        options = PrerecordedOptions(model="nova-2", smart_format=True)
        resp = await self._client.listen.asyncrest.v("1").transcribe_file(
            source, options
        )
        try:
            return resp.results.channels[0].alternatives[0].transcript or ""
        except Exception:
            return ""

    async def synthesize(self, text: str) -> str:
        from deepgram import SpeakOptions

        options = SpeakOptions(model="aura-asteria-en")
        resp = await self._client.speak.asyncrest.v("1").stream_memory(
            {"text": text}, options
        )
        audio_bytes = resp.stream.getvalue()
        return base64.b64encode(audio_bytes).decode("ascii")


class MockVoice(Voice):
    """Returns canned transcripts/silence. The transcript echoes the audio's
    declared 'scenario' if the mock client encodes one, otherwise canned text."""

    name = "mock"

    def __init__(self) -> None:
        # Overridable canned transcript used when the audio carries no hint.
        self.canned_transcript = "I'm fine, thank you."

    async def transcribe(self, audio_b64: str | None) -> str:
        # The mock client encodes a scenario hint as a base64 of a UTF-8 string
        # beginning with "QC-SCENARIO:". Decode it if present so the mock STT
        # can return a realistic transcript without a real model.
        if audio_b64:
            try:
                decoded = base64.b64decode(audio_b64).decode("utf-8", "ignore")
                if decoded.startswith("QC-SCENARIO-TRANSCRIPT:"):
                    return decoded.split(":", 1)[1].strip()
            except Exception:
                pass
        return self.canned_transcript

    async def synthesize(self, text: str) -> str:
        return _SILENT_WAV
