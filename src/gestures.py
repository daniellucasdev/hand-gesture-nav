"""Detecção de gestos sobre landmarks de mão do MediaPipe (21 pontos).

Não usa OpenCV nem MediaPipe aqui: recebe landmarks já normalizados
(lista de (x, y, z)) e devolve eventos como strings. 100% testável com
sequências sintéticas — ver tests/test_gestures.py.

Gestos:
- Swipe com DOIS DEDOS (indicador + médio estendidos; polegar, anelar e
  mínimo dobrados): deslocamento horizontal rápido do centro da palma.
    - mão vai da direita para a esquerda -> evento "workspace_right"
      (cmd+seta direita, conforme pedido)
    - mão vai da esquerda para a direita -> evento "workspace_left"
      (cmd+seta esquerda)
- MÃO ABERTA (5 dedos estendidos) segurada por hold_seconds -> "open_app".

Blindagens (lição de CV: ação não é detecção):
- suavização EMA dos landmarks (tremido não vira swipe);
- swipe precisa ser horizontal (|dx| domina |dy|) e rápido (dentro da janela);
- salto grande do centro da palma entre frames = tracking quebrou
  (corte, troca de mão) -> zera o estado, nunca conta;
- cooldowns: swipe não dispara em rajada; mão aberta dispara uma vez por
  episódio e só re-arma depois que a mão deixa de estar aberta.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# Índices dos landmarks da mão (MediaPipe Hands)
WRIST = 0
THUMB_TIP, THUMB_IP = 4, 3
INDEX_TIP, INDEX_PIP, INDEX_MCP = 8, 6, 5
MIDDLE_TIP, MIDDLE_PIP, MIDDLE_MCP = 12, 10, 9
RING_TIP, RING_PIP = 16, 14
PINKY_TIP, PINKY_PIP, PINKY_MCP = 20, 18, 17

POSE_NONE = ""
POSE_TWO_FINGERS = "dois dedos"
POSE_OPEN_HAND = "mão aberta"

# Centro da palma: pulso + 4 bases dos dedos (estável, pouco afetado por dedo)
PALM_POINTS = (WRIST, INDEX_MCP, MIDDLE_MCP, 13, PINKY_MCP)


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def classify_pose(lm) -> str:
    """Classifica a pose a partir dos 21 landmarks normalizados."""
    wrist = lm[WRIST]

    def extended(tip: int, pip: int) -> bool:
        # dedo estendido: ponta mais longe do pulso que a articulação do meio
        return _dist(lm[tip], wrist) > _dist(lm[pip], wrist)

    index = extended(INDEX_TIP, INDEX_PIP)
    middle = extended(MIDDLE_TIP, MIDDLE_PIP)
    ring = extended(RING_TIP, RING_PIP)
    pinky = extended(PINKY_TIP, PINKY_PIP)
    # polegar: estendido quando a ponta se afasta da base do mindinho
    thumb = (
        _dist(lm[THUMB_TIP], lm[PINKY_MCP])
        > _dist(lm[THUMB_IP], lm[PINKY_MCP]) * 1.05
    )
    if index and middle and ring and pinky and thumb:
        return POSE_OPEN_HAND
    if index and middle and not ring and not pinky and not thumb:
        return POSE_TWO_FINGERS
    return POSE_NONE


@dataclass
class GestureDetector:
    hold_seconds: float = 2.0        # mão aberta precisam ficar este tempo
    swipe_min_travel: float = 0.15   # deslocamento mínimo (fração da largura)
    swipe_window: float = 0.35       # o trajeto precisa caber nesta janela (s)
    swipe_cooldown: float = 1.2      # intervalo mínimo entre swipes (s)
    open_cooldown: float = 4.0       # intervalo mínimo entre "abrir app" (s)
    jump_reset: float = 0.35         # salto da palma que zera o estado
    ema_alpha: float = 0.6           # peso do frame novo na suavização

    # estado (populados por update())
    pose: str = POSE_NONE
    smoothed: list | None = None
    hold_progress: float = 0.0
    _trail: list = field(default_factory=list)   # [(t, cx, cy)] com dois dedos
    _swipe_ok_at: float = 0.0
    _hold_start: float | None = None
    _hold_fired: bool = False
    _open_ok_at: float = 0.0
    _last_palm: tuple | None = None

    def update(self, landmarks, now: float) -> list[str]:
        """Processa um frame. landmarks = 21 pontos (x,y,z) ou None (sem mão).

        Devolve uma lista de eventos: 'workspace_left', 'workspace_right',
        'open_app'.
        """
        if landmarks is None:
            self.pose = POSE_NONE
            self.hold_progress = 0.0
            self._reset_motion()
            return []

        sm = self._smooth(landmarks)
        self.pose = classify_pose(sm)
        palm = self._palm_centroid(sm)

        # salto grande = tracking quebrou (corte, outra mão): zera e ignora
        if self._last_palm is not None and _dist(palm, self._last_palm) > self.jump_reset:
            self._last_palm = palm
            self._reset_motion()
            return []
        self._last_palm = palm

        events = self._update_swipe(palm, now)
        events += self._update_hold(now)
        return events

    # -- swipe ------------------------------------------------------------
    def _update_swipe(self, palm: tuple, now: float) -> list[str]:
        if self.pose != POSE_TWO_FINGERS:
            self._trail.clear()  # o trajeto só vale com a pose mantida
            return []
        self._trail.append((now, palm[0], palm[1]))
        while self._trail and now - self._trail[0][0] > self.swipe_window:
            self._trail.pop(0)
        if len(self._trail) < 2 or now < self._swipe_ok_at:
            return []
        t0, x0, y0 = self._trail[0]
        dx, dy = palm[0] - x0, palm[1] - y0
        if abs(dx) < self.swipe_min_travel:
            return []
        if abs(dx) < 2.5 * abs(dy):  # não é predominantemente horizontal
            return []
        # direita->esquerda (dx<0) troca para a DIREITA, conforme o pedido
        direction = "workspace_left" if dx > 0 else "workspace_right"
        self._trail.clear()
        self._swipe_ok_at = now + self.swipe_cooldown
        return [direction]

    # -- mão aberta --------------------------------------------------------
    def _update_hold(self, now: float) -> list[str]:
        if self.pose != POSE_OPEN_HAND:
            self._hold_start = None
            self._hold_fired = False
            self.hold_progress = 0.0
            return []
        if self._hold_start is None:
            self._hold_start = now
        self.hold_progress = min(1.0, (now - self._hold_start) / self.hold_seconds)
        if self._hold_fired or now < self._open_ok_at:
            return []
        if now - self._hold_start >= self.hold_seconds:
            self._hold_fired = True
            self._open_ok_at = now + self.open_cooldown
            return ["open_app"]
        return []

    # -- auxiliares --------------------------------------------------------
    def _smooth(self, lm) -> list:
        if self.smoothed is None or len(self.smoothed) != len(lm):
            self.smoothed = [tuple(p) for p in lm]
            return self.smoothed
        a = self.ema_alpha
        self.smoothed = [
            (
                a * p[0] + (1 - a) * s[0],
                a * p[1] + (1 - a) * s[1],
                a * p[2] + (1 - a) * s[2],
            )
            for s, p in zip(self.smoothed, lm)
        ]
        return self.smoothed

    @staticmethod
    def _palm_centroid(lm) -> tuple:
        xs = [lm[i][0] for i in PALM_POINTS]
        ys = [lm[i][1] for i in PALM_POINTS]
        return (sum(xs) / len(xs), sum(ys) / len(ys))

    def _reset_motion(self) -> None:
        self._trail.clear()
        self._hold_start = None
        self._hold_fired = False
        self.hold_progress = 0.0
