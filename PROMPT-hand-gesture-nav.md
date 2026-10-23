# Prompt — Hand Gesture Nav (controle de Spaces do macOS por gestos de mão)

## O que quero

Continuar o desenvolvimento do projeto hand-gesture-nav, que já existe e está
neste repositório. O app abre a webcam, lê gestos da minha mão e executa:

1. Swipe com DOIS dedos (indicador+médio) da direita para a esquerda > troca o
   Space do macOS para a DIREITA (cmd + seta direita).
2. Swipe com dois dedos da esquerda para a direita > troca o Space para a
   ESQUERDA (cmd + seta esquerda).
3. Mão aberta por 2 segundos > abre o Claude Desktop.

Roda APENAS local no meu Mac. Este prompt é o contrato: nada de recriar o
projeto de outro jeito ou reabrir decisões já fechadas.

## Estado atual (verificado em 23/10/2026 — confirme antes de usar, referências podem ter mudado)

- Código completo e funcional em src/main.py (loop da câmera), src/gestures.py
  (máquina de estados de gestos), src/actions.py (osascript/open -a) e
  src/overlay.py (HUD). Launchers: scripts/setup.sh (uma vez) e
  scripts/start.command (duplo clique).
- 14 testes em tests/test_gestures.py passando (python -m pytest tests/ -q
  dentro do venv).
- Pipeline provado com foto e vídeo real de mão: pose "mão aberta"
  classificada com 0.96 de confiança; app de ponta a ponta com vídeo dispara
  "abrir app" exatamente uma vez (com --dry-run).
- open -a Claude funciona (Claude Desktop instalado em /Applications/Claude.app).
- NÃO verificado ainda: os 3 gestos com a MINHA mão na webcam e a troca real
  de Space — dependem de 2 permissões do macOS que só eu concedo:
  Câmera > Terminal e Acessibilidade > Terminal (Ajustes > Privacidade e
  Segurança). O app detecta a falta das duas e imprime instruções.

## Contexto do repo (verifique antes de usar — referências podem ter mudado)

- Local no disco: ~/Desktop/hand-gesture-nav (repo público:
  github.com/daniellucasdev/hand-gesture-nav).
- venv em .venv com Python 3.11 (/Users/dan/.local/bin/python3.11). Para
  rodar/testar: source .venv/bin/activate e então python -m pytest tests/ -q
  ou python src/main.py.
- Modelo hand_landmarker.task (7,8 MB) fica em models/, baixado por
  scripts/setup.sh do storage oficial do MediaPipe, e NÃO é versionado.
- Detecção roda em CPU por decisão (delegate GPU/Metal do MediaPipe 0.10.x
  quebrado no macOS; CPU dá ~22 ms/frame no M2). Flag --delegate GPU existe
  para experimentar.
- Documentação viva em docs/decisoes.md (decisões datadas) e README.md (uso,
  permissões, flags).

## Decisões já fechadas (NÃO reabrir)

1. App desktop Python (OpenCV + MediaPipe Tasks), NÃO web — aba de navegador
   em segundo plano tem o loop de vídeo pausado, o que mataria o gesto na
   hora de trocar de Space. Detalhes em docs/decisoes.md, item 1.
2. Mapeamento do swipe é literal ao pedido acima (direita->esquerda vira
   Space DIREITA) — é invertido da intuição de arrastar conteúdo de propósito.
3. Pose de "dois dedos" exige polegar, anelar e mínimo dobrados — torna os
   dois gestos mutuamente exclusivos (mão aberta rápida não dispara swipe).
4. Blindagens obrigatórias (não remover): EMA anti-tremido, swipe horizontal
   (|dx| >= 2.5*|dy|) com trajeto mínimo e cooldown, hold que re-arma só
   depois de a mão fechar/some, reset total quando o centro da palma salta
   (tracking quebrou). Detecção não é ação.
5. Injeção de teclas via osascript (subprocess), sem pynput/CGEvent.

## Quando retomar, faça nesta ordem

1. Rode os testes e um smoke: cd ~/Desktop/hand-gesture-nav && source
   .venv/bin/activate && python -m pytest tests/ -q && python src/main.py
   --dry-run --frames 60.
2. Se algo quebrou (ex.: versão nova de mediapipe), conserte ANTES de
   evoluir; olhe docs/decisoes.md item 3 para o drama do GPU/CPU.
3. Me ajude a calibrar com a mão real (dry-run primeiro): se swipes não
   disparam, baixe swipe_min_travel em src/gestures.py; se dispararem sozinhos,
   aumente. Hold: --hold-seconds. Não mexa nas blindagens do item 4.
4. Só depois disso, evolua o que eu pedir (novos gestos, novo app-alvo, UI).

## Restrições

- 100% local: nenhum dado de vídeo/imagem sai do Mac, nenhuma telemetria.
- Não adicionar dependência além de mediapipe/opencv/numpy/pytest sem me
  perguntar.
- Commits em PT-BR, fatias pequenas, sem Co-Authored-By.
- Permissões do macOS (Câmera, Acessibilidade) são minhas para conceder —
  nunca tente burlar TCC.
- Se eu mudar de ideia sobre o mapeamento do swipe, atualize também
  tests/test_gestures.py e docs/decisoes.md no mesmo commit.
