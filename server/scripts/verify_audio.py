"""Live verification of the audio stack: Deepgram (STT+TTS) and the YAMNet
audio-scene ML model.

What it does:
  1. Deepgram TTS->STT round-trip: synthesize a sentence to WAV, then transcribe
     that WAV back and check the text round-trips. Proves both directions live.
  2. YAMNet: load the configured TFLite model and classify (a) the synthesized
     speech WAV — expect speech-related tags — and (b) a synthetic noise burst,
     printing the top AudioSet tags and the distress flag.

Run:  python scripts/verify_audio.py
"""
from __future__ import annotations

import asyncio
import base64
import io
import os
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.providers.audio_scene import YamnetAudioScene
from app.providers.voice import DeepgramVoice


def _synthetic_noise_wav(seconds: float = 1.0, rate: int = 16000) -> str:
    """A loud broadband burst (decaying) as a stand-in 'thud/impact' clip."""
    import numpy as np

    n = int(seconds * rate)
    t = np.linspace(0, seconds, n, endpoint=False)
    burst = (np.random.randn(n) * np.exp(-t * 6)).astype(np.float32)
    pcm = np.clip(burst, -1, 1)
    pcm16 = (pcm * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm16.tobytes())
    return base64.b64encode(buf.getvalue()).decode("ascii")


async def main() -> None:
    print("=== Deepgram (TTS -> STT round-trip) ===")
    phrase = "Margaret, are you okay? Please answer if you can hear me."
    voice = DeepgramVoice(settings.deepgram_api_key)
    wav_b64 = await voice.synthesize(phrase)
    print(f"  TTS: synthesized {len(base64.b64decode(wav_b64))} bytes of WAV")
    transcript = await voice.transcribe(wav_b64)
    print(f"  STT: transcript -> {transcript!r}")
    ok = bool(transcript.strip())
    print(f"  ROUND-TRIP OK: {ok}")

    print("\n=== YAMNet (audio-scene ML) ===")
    if not settings.has_yamnet:
        print("  YAMNet not configured; skipping.")
        return
    scene = YamnetAudioScene(settings.yamnet_model_path, settings.yamnet_labels_path)
    print(f"  model loaded; {len(scene._labels)} class labels")

    res_speech = await scene.classify(wav_b64)
    print("  [synthesized speech] top tags:")
    for label, score in res_speech.tags:
        print(f"    {label:28} {score:.3f}")
    print(f"    distress={res_speech.distress} source={res_speech.source}")

    res_noise = await scene.classify(_synthetic_noise_wav())
    print("  [synthetic noise burst] top tags:")
    for label, score in res_noise.tags:
        print(f"    {label:28} {score:.3f}")
    print(f"    distress={res_noise.distress} source={res_noise.source}")


if __name__ == "__main__":
    asyncio.run(main())
