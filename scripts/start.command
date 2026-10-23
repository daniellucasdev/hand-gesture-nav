#!/bin/bash
# Hand Gesture Nav — inicia o app (duplo-clique no Finder)
cd "$(dirname "$0")/.."
source .venv/bin/activate
echo "✋ Hand Gesture Nav — dois dedos: swipe troca de Space | mão aberta 2s: abre o Claude | Q na janela para sair"
exec python src/main.py "$@"
