from __future__ import annotations

import asyncio
import base64
import io
import math
import os
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.providers.audio_scene import YamnetAudioScene


def make_wav_b64(samples: np.ndarray, rate: int = 16000) -> str:
    pcm = np.clip(samples, -1.0, 1.0)
    pcm16 = (pcm * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm16.tobytes())
    return base64.b64encode(buf.getvalue()).decode("ascii")


def sine_tone(seconds: float = 1.0, rate: int = 16000, hz: int = 440) -> np.ndarray:
    t = np.linspace(0, seconds, int(seconds * rate), endpoint=False)
    return (0.4 * np.sin(2 * math.pi * hz * t)).astype(np.float32)


def noise_burst(seconds: float = 1.0, rate: int = 16000) -> np.ndarray:
    rng = np.random.default_rng(42)
    t = np.linspace(0, seconds, int(seconds * rate), endpoint=False)
    return (rng.normal(0, 0.5, t.shape) * np.exp(-t * 7)).astype(np.float32)


async def classify_clip(
    scene: YamnetAudioScene,
    name: str,
    samples: np.ndarray,
    expected_distress: bool,
) -> bool:
    result = await scene.classify(make_wav_b64(samples))
    print(f"\n{name}")
    print(f"  source={result.source} distress={result.distress} tags={len(result.tags)}")
    for label, score in result.tags[:6]:
        print(f"  {score:0.4f}  {label}")
    return (
        result.source == "yamnet"
        and len(result.tags) > 0
        and result.distress is expected_distress
    )


async def main() -> int:
    print("YAMNet verification")
    print(f"  has_yamnet={settings.has_yamnet}")
    print(f"  model={settings.yamnet_model_path_resolved}")
    print(f"  labels={settings.yamnet_labels_path_resolved}")

    if not settings.has_yamnet:
        print("FAIL: YAMNet model or label file is missing.")
        return 1

    scene = YamnetAudioScene(
        settings.yamnet_model_path_resolved,
        settings.yamnet_labels_path_resolved,
    )
    print(f"  provider={scene.name}")
    print(f"  label_count={len(scene._labels)}")

    checks = [
        await classify_clip(scene, "sine_tone_440hz", sine_tone(), False),
        await classify_clip(scene, "noise_burst", noise_burst(), True),
    ]
    ok = all(checks)
    print(f"\nYAMNET_INFERENCE_OK={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
