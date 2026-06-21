#!/usr/bin/env python3
"""Fetch the YAMNet TFLite model + class-map CSV into server/models/.

The TFLite model now lives on Kaggle Models (the old GCS direct link is 403),
so we pull it anonymously via kagglehub. The class map comes from the
tensorflow/models repo on GitHub.

Usage:  python scripts/fetch_yamnet.py
        (requires: pip install kagglehub)
"""

from __future__ import annotations

import glob
import os
import shutil
import sys
import urllib.request

KAGGLE_SLUG = "google/yamnet/tfLite/classification-tflite"
LABELS_URL = (
    "https://raw.githubusercontent.com/tensorflow/models/master/"
    "research/audioset/yamnet/yamnet_class_map.csv"
)

SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(SERVER_DIR, "models")
MODEL_PATH = os.path.join(MODELS_DIR, "yamnet.tflite")
LABELS_PATH = os.path.join(MODELS_DIR, "yamnet_class_map.csv")


def main() -> int:
    os.makedirs(MODELS_DIR, exist_ok=True)

    try:
        import kagglehub
    except ImportError:
        print("ERROR: kagglehub not installed. Run:  pip install kagglehub", file=sys.stderr)
        return 1

    print(f"Downloading YAMNet TFLite model from Kaggle ({KAGGLE_SLUG}) ...")
    cache_dir = kagglehub.model_download(KAGGLE_SLUG)
    tflites = glob.glob(os.path.join(cache_dir, "*.tflite"))
    if not tflites:
        print(f"ERROR: no .tflite found in {cache_dir}", file=sys.stderr)
        return 1
    shutil.copyfile(tflites[0], MODEL_PATH)
    model_bytes = os.path.getsize(MODEL_PATH)

    print(f"Downloading YAMNet class map -> {LABELS_PATH}")
    urllib.request.urlretrieve(LABELS_URL, LABELS_PATH)
    with open(LABELS_PATH) as f:
        header = f.readline()
        label_count = sum(1 for _ in f)
    if "display_name" not in header:
        print("ERROR: class map missing 'display_name' header.", file=sys.stderr)
        return 1

    print()
    print(f"Done. Model: {model_bytes} bytes | Labels: {label_count} classes")
    print()
    print("Add these to server/.env:")
    print(f"  YAMNET_MODEL_PATH={MODEL_PATH}")
    print(f"  YAMNET_LABELS_PATH={LABELS_PATH}")
    print("  AUDIO_SCENE_BACKEND=yamnet   # or 'both' to ensemble with PANNs")
    print()
    print("Then install the runtime deps:  pip install numpy ai-edge-litert")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
