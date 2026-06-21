#!/usr/bin/env bash
# Fetch the YAMNet TFLite model + class-map CSV into server/models/.
# The TFLite model lives on Kaggle Models (the old GCS link is 403-gated), so
# this delegates to the Python fetcher which pulls it anonymously via kagglehub.
#
# Usage:  bash scripts/fetch_yamnet.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python3}"
# Prefer the project venv if present.
if [ -x "${SCRIPT_DIR}/../.venv/bin/python" ]; then
  PY="${SCRIPT_DIR}/../.venv/bin/python"
fi

"${PY}" -c "import kagglehub" 2>/dev/null || "${PY}" -m pip install kagglehub
exec "${PY}" "${SCRIPT_DIR}/fetch_yamnet.py"
