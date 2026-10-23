# Decisões de arquitetura

## 1. App desktop Python, não web (23/10/2026)

Pedido: "desktop ou web — pondere o que for melhor". Decisão: **desktop**.

- Aba de navegador em segundo plano tem o loop de vídeo pausado por
  throttling — e o gesto de trocar Space acontece justamente com a janela do
  app fora de foco. Falharia no caso de uso central. (Hacks com áudio/PiP
  existem, mas são frágeis e específicos de navegador.)
- Processo nativo injeta teclas via osascript e chama `open -a` direto, sem
  camada HTTP; o app web precisaria do mesmo backend de qualquer forma.
- Permissões equivalentes (câmera + acessibilidade) nos dois mundos; no
  desktop, concedidas uma vez por app (Terminal) e esquecidas.
- Padrão consolidado no conjunto de projetos do usuário (venv + launcher
  .command, ex.: boxing-vision).

Web só ganharia na UI — o overlay do OpenCV resolve bem para um app de uso
pessoal.

## 2. MediaPipe Hand Landmarker por regras, não rede treinada (23/10/2026)

- 21 keypoints prontos, modelo de 7,8 MB, ~22 ms/frame em CPU no M2 —
  sobra para 30 fps.
- Regra do projeto de CV: camada temporal por regras ANTES de qualquer rede
  treinada. Swipe/hold são fully determinísticos e testáveis sem rede.
- Alternativas descartadas: YOLO de mãos (mais pesado, sem keypoints 3D
  estáveis por dedo), treinamento próprio (não há dataset; custo alto para
  3 gestos).

## 3. CPU como delegata padrão (23/10/2026)

O delegate GPU (Metal) do MediaPipe 0.10.x falha no primeiro frame no macOS
com "Only 4-channel texture input formats are supported". Medido: CPU
processa em ~21,7 ms/frame (M2) — acima do necessário. GPU fica disponível
por flag (--delegate GPU) para versões futuras do mediapipe.

## 4. Mapeamento do swipe literal ao pedido (23/10/2026)

"direita para a esquerda > workspace para a direita" é contraintuitivo (é o
inverso da metáfora de arrastar conteúdo) e FOI mantido como pedido. Para
inverter, trocar os dois ramos em gestures.GestureDetector._update_swipe.

## 5. Dois dedos exige polegar dobrado (23/10/2026)

A pose de swipe (indicador+médio) só vale com polegar, anelar e mínimo
dobrados. Isso torna "mão aberta" e "dois dedos" mutuamente exclusivos —
mão aberta passando rápido NÃO dispara swipe, e V de dois dedos NÃO inicia o
hold.

## 6. Modelo fora do git (23/10/2026)

hand_landmarker.task (7,8 MB) é baixado por scripts/setup.sh do repositório
oficial do MediaPipe e fica em models/ (gitignored). Padrão: repos só de
código + docs.

## 7. Injeção de teclas via osascript, não CGEvent/pynput (23/10/2026)

osascript é stdlib-adjacente (subprocess), sem dependência nova, e o erro de
permissão (1002) é detectável para instruir o usuário. pynput/Quartz exigiria
o mesmo grant de Acessibilidade com mais código.

## 8. Emenda de calibração: polegar livre na pose de dois dedos + votação e grace (23/10/2026)

Primeira sessão de calibração com a mão real: mão aberta disparou 2x, swipe
0x. Causas encontradas e corrigidas:

- **Polegar saiu da exigência da pose de dois dedos.** Em V natural o polegar
  fica semi-aberto e a regra original ("polegar dobrado") rejeitava a pose —
  ela nunca era reconhecida. A exclusão com a mão aberta (intenção da
  decisão 3) continua garantida por anelar+mínimo dobrados.
- **Votação majoritária da pose (3 frames).** Com landmarks reais a
  classificação oscila frame a frame e cada frame de pose errada zerava o
  trajeto do swipe — nunca acumulava 15% de deslocamento.
- **Frames sem mão não zeram mais o trajeto diretamente.** Quem decide é o
  grace de 0,18 s no próximo frame com mão (gap curto de blur/sombra não
  mata o swipe; mão fora por mais que isso zera).
- **Flag --debug** (telemetria de pose/trajeto/hold a cada 0,5 s) para
  calibrar com dados, não com adivinhação.

Blindagens da decisão 4 foram fortalecidas, não removidas.

## 9. Modificador do swipe: ctrl, não cmd (23/10/2026, correção do Daniel)

Eu havia entendido cmd+seta; o correto para trocar de Space é **ctrl+seta**
(`key code N using control down` no osascript). Mudado em src/actions.py e em
toda a documentação. O mapeamento direção->seta (decisão 4) não mudou.

## 10. Novos gestos: OK (toggle de gravação) e joinha (Enter) (23/10/2026)

- **OK** = círculo polegar+indicador (ponta a ponta, < 30% da escala da mão)
  com médio/anelar/mínimo estendidos -> evento "toggle_recording". Checado
  ANTES da mão aberta na classificação (não conflita: na mão aberta o polegar
  fica longe do indicador).
- **Joinha** = polegar estendido + 4 dedos dobrados + ponta acima do IP acima
  do MCP (aponta para cima) -> "press_enter" (key code 36).
- Ambos disparam uma vez por EPISÓDIO da pose (re-armam só quando a mão sai
  da pose), com cooldown de 1,5 s — segurar a mão não repete o disparo.
- Gravação de áudio: o Claude Desktop não tem atalho público de voz, então o
  atalho é configurável via --voice-keys; sem ele, o gesto ativa o app e
  avisa. Estado do toggle (iniciar/encerrar) é mantido no app.

