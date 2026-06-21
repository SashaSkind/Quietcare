"""AudioScene provider: non-speech distress detection on phone audio.

This complements speech-to-text (Deepgram): instead of *what was said*, it tells
the agent *what was heard* — a thud, scream, groan, glass breaking, etc. — so the
elder-agent can fuse acoustic evidence with the transcript and responsiveness.

Real implementation uses YAMNet (MobileNet trained on Google AudioSet, ~521
classes) via TFLite. When no model is configured, a deterministic mock derives
distress tags from the mock client's scenario hint so the whole flow stays
testable with zero ML dependencies.
"""

from __future__ import annotations

import base64
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger("quietcare.audio_scene")

# AudioSet/YAMNet display names that indicate a potential emergency. Matched
# case-insensitively as substrings against the model's class labels.
DISTRESS_LABELS = (
    "scream", "shout", "yell", "groan", "grunt", "crying", "sob", "wail",
    "moan", "gasp", "thud", "thump", "bang", "slam", "glass", "shatter",
    "breaking", "fall", "whimper", "choking", "cough", "gagging",
)

# Threshold above which a distress label is considered "present".
DISTRESS_THRESHOLD = 0.30


@dataclass
class AudioSceneResult:
    tags: list[tuple[str, float]] = field(default_factory=list)
    distress: bool = False
    source: str = "none"

    def to_dict(self) -> dict:
        return {
            "tags": [{"label": l, "score": round(s, 3)} for l, s in self.tags],
            "distress": self.distress,
            "source": self.source,
        }


def _is_distress(label: str) -> bool:
    low = label.lower()
    return any(key in low for key in DISTRESS_LABELS)


class AudioScene(ABC):
    name: str = "audio_scene"

    @abstractmethod
    async def classify(self, audio_b64: str | None) -> AudioSceneResult:
        ...


class MockAudioScene(AudioScene):
    """Deterministic distress tagging.

    Reads the mock client's ``QC-SCENARIO-TRANSCRIPT:`` / ``QC-SCENARIO-AUDIO:``
    hints (if present) so tests are reproducible. With ``QC-SCENARIO-AUDIO`` the
    payload is a comma-separated ``label:score`` list. Otherwise it infers tags
    from transcript keywords; real (un-hinted) audio yields no distress.
    """

    name = "mock"

    async def classify(self, audio_b64: str | None) -> AudioSceneResult:
        if not audio_b64:
            return AudioSceneResult(source="mock")
        try:
            decoded = base64.b64decode(audio_b64).decode("utf-8", "ignore")
        except Exception:
            return AudioSceneResult(source="mock")

        if decoded.startswith("QC-SCENARIO-AUDIO:"):
            tags: list[tuple[str, float]] = []
            for part in decoded.split(":", 1)[1].split(","):
                part = part.strip()
                if not part:
                    continue
                if ":" in part:
                    label, _, score = part.partition(":")
                    try:
                        tags.append((label.strip(), float(score)))
                    except ValueError:
                        tags.append((label.strip(), 0.9))
                else:
                    tags.append((part, 0.9))
            distress = any(_is_distress(l) and s >= DISTRESS_THRESHOLD for l, s in tags)
            return AudioSceneResult(tags=tags, distress=distress, source="mock")

        if decoded.startswith("QC-SCENARIO-TRANSCRIPT:"):
            text = decoded.split(":", 1)[1].lower()
            if any(k in text for k in ("fell", "can't get up", "help", "[silence]")):
                return AudioSceneResult(
                    tags=[("Thud", 0.8), ("Groan", 0.5)], distress=True, source="mock"
                )
        return AudioSceneResult(source="mock")


class YamnetAudioScene(AudioScene):
    """YAMNet (AudioSet) audio tagging via TFLite.

    Loads a YAMNet ``.tflite`` model + class-map CSV from disk and returns the
    top distress-relevant tags for a WAV/PCM clip. Heavy deps (numpy + a TFLite
    runtime) are imported lazily so the rest of the system needs none of them.
    """

    name = "yamnet"

    def __init__(self, model_path: str, labels_path: str) -> None:
        self._interpreter = self._load_interpreter(model_path)
        self._interpreter.allocate_tensors()
        self._input = self._interpreter.get_input_details()[0]
        self._output = self._interpreter.get_output_details()[0]
        self._labels = self._load_labels(labels_path)

    @staticmethod
    def _load_interpreter(model_path: str):
        # Prefer the lightweight runtimes; fall back to full TensorFlow.
        try:
            from ai_edge_litert.interpreter import Interpreter  # type: ignore
        except Exception:
            try:
                from tflite_runtime.interpreter import Interpreter  # type: ignore
            except Exception:
                from tensorflow.lite import Interpreter  # type: ignore
        return Interpreter(model_path=model_path)

    @staticmethod
    def _load_labels(labels_path: str) -> list[str]:
        import csv

        labels: list[str] = []
        with open(labels_path, newline="") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            name_idx = 2
            if header and "display_name" in header:
                name_idx = header.index("display_name")
            for row in reader:
                if row:
                    labels.append(row[name_idx])
        return labels

    @staticmethod
    def _decode_wav_to_16k_mono(audio_b64: str):
        import io
        import wave

        import numpy as np

        raw = base64.b64decode(audio_b64)
        with wave.open(io.BytesIO(raw), "rb") as wf:
            n_channels = wf.getnchannels()
            sample_rate = wf.getframerate()
            sampwidth = wf.getsampwidth()
            frames = wf.readframes(wf.getnframes())

        dtype = {1: np.int8, 2: np.int16, 4: np.int32}.get(sampwidth, np.int16)
        data = np.frombuffer(frames, dtype=dtype).astype(np.float32)
        if n_channels > 1:
            data = data.reshape(-1, n_channels).mean(axis=1)
        # Normalize to [-1, 1].
        max_val = float(np.iinfo(dtype).max) if dtype != np.float32 else 1.0
        data = data / max_val
        # Resample to 16 kHz via linear interpolation.
        if sample_rate != 16000 and len(data) > 1:
            target_len = int(round(len(data) * 16000 / sample_rate))
            data = np.interp(
                np.linspace(0, len(data) - 1, target_len),
                np.arange(len(data)),
                data,
            ).astype(np.float32)
        return data

    async def classify(self, audio_b64: str | None) -> AudioSceneResult:
        if not audio_b64:
            return AudioSceneResult(source="yamnet")
        try:
            import numpy as np

            waveform = self._decode_wav_to_16k_mono(audio_b64)
            if waveform.size == 0:
                return AudioSceneResult(source="yamnet")
            # YAMNet accepts a 1-D float32 waveform; resize the input tensor.
            self._interpreter.resize_tensor_input(
                self._input["index"], [waveform.size]
            )
            self._interpreter.allocate_tensors()
            self._interpreter.set_tensor(self._input["index"], waveform)
            self._interpreter.invoke()
            scores = self._interpreter.get_tensor(self._output["index"])
            mean_scores = np.mean(scores, axis=0)  # average over frames
            top_idx = np.argsort(mean_scores)[::-1][:10]
            tags = [(self._labels[i], float(mean_scores[i])) for i in top_idx]
            distress = any(
                _is_distress(l) and s >= DISTRESS_THRESHOLD for l, s in tags
            )
            # Keep only the most informative tags for the agent.
            return AudioSceneResult(tags=tags[:6], distress=distress, source="yamnet")
        except Exception as exc:  # pragma: no cover - model/runtime issues
            logger.warning("YAMNet classify failed (%s)", exc)
            return AudioSceneResult(source="yamnet")
