#!/bin/bash
# Hand Gesture Nav — setup: venv + dependências + modelo do MediaPipe
set -euo pipefail
cd "$(dirname "$0")/.."

# Python 3.9–3.12 (faixa suportada pelo mediapipe)
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  for c in python3.12 python3.11 python3.10 python3.9 python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if (3,9)<=sys.version_info[:2]<=(3,12) else 1)'; then
      PY="$c"; break
    fi
  done
fi
[ -n "$PY" ] || { echo "Python 3.9-3.12 não encontrado (instale ou use PYTHON=/caminho ./scripts/setup.sh)"; exit 1; }
echo ">> Python: $($PY --version)"

if [ ! -d .venv ]; then
  "$PY" -m venv .venv
fi
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

MODEL="models/hand_landmarker.task"
if [ ! -f "$MODEL" ]; then
  mkdir -p models
  echo ">> Baixando hand_landmarker.task (~8 MB, MediaPipe oficial)..."
  curl -fL --fail-early -o "$MODEL" \
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
fi

echo ">> Setup concluído. Dê dois cliques em scripts/start.command (ou rode: source .venv/bin/activate && python src/main.py)"
