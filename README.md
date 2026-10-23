# Hand Gesture Nav

Controle os Spaces (áreas de trabalho) do macOS com a mão, pela webcam. 100%
local, sem nuvem, sem dados saindo da máquina.

| Gesto | Ação |
|---|---|
| Swipe com **dois dedos** (indicador + médio) da **direita para a esquerda** | Space para a **direita** (cmd+→) |
| Swipe com **dois dedos** da **esquerda para a direita** | Space para a **esquerda** (cmd+←) |
| **Mão aberta** por **2 segundos** | Abre o **Claude Desktop** |

```
 ┌────────────────────────────────────────────┐
 │ Mao: DOIS DEDOS  |  FPS: 31                │
 │ >>> Space direita ->                       │
 │                                            │
 │              👌 (sua mão,                  │
 │            com esqueleto desenhado)        │
 └────────────────────────────────────────────┘
   janela da câmera com overlay + HUD
```

## Por que app desktop (Python) e não web?

Ponderação que fechou a arquitetura (detalhes em docs/decisoes.md):

1. **Aba em segundo plano morre.** Num app web, o navegador pausa o loop de
   vídeo (`requestAnimationFrame` throttling) quando a aba não está visível —
   e "não está visível" é EXATAMENTE o estado ao trocar de Space. O gesto
   falharia no único momento em que você o usa.
2. **Injeção de teclas direta.** O processo Python envia cmd+seta via
   osascript e abre apps via `open -a`, sem um servidor HTTP no meio.
3. **Mesmo padrão de projetos anteriores** (venv + launcher .command de duplo
   clique), zero navegador para manter.

A inferência roda em CPU com MediaPipe Hand Landmarker: ~22 ms/frame no M2,
bem acima dos 30 fps da webcam. (O delegate GPU/Metal desta versão do
MediaPipe está quebrado no macOS — tentar usar por conta e risco, via
`--delegate GPU`.)

## Instalação

Requisito: Python 3.9–3.12 (`python3 --version`). Depois, de um terminal:

```bash
cd ~/Desktop/hand-gesture-nav
./scripts/setup.sh     # cria .venv, instala deps, baixa o modelo (~8 MB)
```

## Permissões do macOS (uma vez só)

| Permissão | Onde liberar | Para quê |
|---|---|---|
| **Câmera** | Ajustes > Privacidade e Segurança > **Câmera** > ative **Terminal** | capturar a webcam |
| **Acessibilidade** | Ajustes > Privacidade e Segurança > **Acessibilidade** > ative **Terminal** | enviar cmd+seta ao sistema |

O app detecta as duas ausências e imprime estas instruções na hora, em vez de
quebrar.

## Uso

Duplo clique em `scripts/start.command` no Finder, ou:

```bash
source .venv/bin/activate
python src/main.py
```

- Aperte **Q** na janela da câmera (ou Ctrl+C no terminal) para sair.
- **Primeira vez, rode com `--dry-run`**: os gestos aparecem no terminal sem
  executar nada — bom para calibrar distância/velocidade.
- O cmd+seta vai para o **app em foco**; para só trocar de Space, deixe o
  Finder/desktop em foco (clique no papel de parede antes de gesticular).

Flags úteis:

```bash
python src/main.py --dry-run            # loga as ações, não executa
python src/main.py --hold-seconds 1.5   # mão aberta mais rápida
python src/main.py --cooldown 0.8       # swipes mais rápidos em sequência
python src/main.py --app-name Safari    # outro app na mão aberta
python src/main.py --frames 120         # sai sozinho após N frames
python src/main.py --camera arquivo.mp4 # processa um vídeo (teste sem webcam)
```

## Testes

14 testes determinísticos cobrindo a máquina de estados de gestos com mãos
sintéticas (swipes nos dois sentidos, arrasto lento, tremido, movimento
vertical, cooldown, re-arme da mão aberta, tracking quebrado):

```bash
source .venv/bin/activate && python -m pytest tests/ -q
```

## Estrutura

```
src/actions.py    ações: cmd+seta (Spaces) e abrir app (osascript / open -a)
src/gestures.py   máquina de estados: poses, swipe e hold (sem OpenCV — testável isolado)
src/overlay.py    desenho dos landmarks + HUD
src/main.py       loop da câmera, MediaPipe, dispatch das ações
scripts/setup.sh  venv + dependências + download do modelo
scripts/start.command  duplo-clique para iniciar
models/           hand_landmarker.task (baixado, não versionado)
docs/decisoes.md  decisões de arquitetura datadas
```

## Como funciona (resumo)

MediaPipe Hand Landmarker devolve 21 pontos normalizados por frame. Pose:

- **dedo estendido** = ponta mais longe do pulso que a articulação do meio;
- **dois dedos** = indicador + médio estendidos, polegar/anelar/mínimo dobrados;
- **mão aberta** = os cinco estendidos.

Sobre as poses, uma camada temporal por regras: swipe = trajeto horizontal
(≥15% da largura) dentro de 0,35 s, com cooldown de 1,2 s; mão aberta =
cronômetro de 2 s que só re-arma depois que a mão fecha/some. Tremido é
filtrado com EMA; salto grande do centro da palma (troca de mão/corte) zera o
estado em vez de contar. Regra de ouro do projeto: **detecção não é ação** —
nada dispara sem passar pelas blindagens.

## Limitações conhecidas

- Uma mão por vez (a mais confiável do frame).
- Punho fechado às vezes não é detectado pelo MediaPipe (detector de palma) —
  irrelevante para os gestos.
- Deixe o rosto/luz decente: contra-luz forte derruba a detecção.
- O app troca de Space do app em foco; editores/IDEs podem capturar cmd+seta
  (neles, o atalho do Space não dispara).

## Créditos

Modelo [MediaPipe Hand Landmarker](https://developers.google.com/mediapipe) (Apache 2.0),
baixado automaticamente por scripts/setup.sh.
