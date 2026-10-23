"""Overlay da janela da câmera: desenho dos landmarks e HUD.

Os textos do cv2.putText não suportam acentos (fontes Hershey), então o
HUD usa rótulos em ASCII ("MAO ABERTA"); o terminal imprime em PT-BR.
"""

from __future__ import annotations

import time

import cv2

from gestures import POSE_OK, POSE_OPEN_HAND, POSE_THUMBS_UP, POSE_TWO_FINGERS

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
]

GREEN = (120, 220, 120)
WHITE = (245, 245, 245)
DARK = (30, 30, 30)
YELLOW = (60, 200, 255)
RED = (80, 80, 255)

EVENT_LABELS = {
    "workspace_left": "<- Space esquerda",
    "workspace_right": "Space direita ->",
    "open_app": "Abrir app",
    "toggle_recording": "Gravar audio (toggle)",
    "press_enter": "Enter",
}

POSE_LABELS = {
    POSE_TWO_FINGERS: "DOIS DEDOS",
    POSE_OPEN_HAND: "MAO ABERTA",
    POSE_OK: "OK",
    POSE_THUMBS_UP: "JOINHA",
}


def _px(p, w, h):
    return (int(p[0] * w), int(p[1] * h))


def draw_landmarks(frame, lm) -> None:
    h, w = frame.shape[:2]
    for a, b in HAND_CONNECTIONS:
        cv2.line(frame, _px(lm[a], w, h), _px(lm[b], w, h), GREEN, 2, cv2.LINE_AA)
    for p in lm:
        cv2.circle(frame, _px(p, w, h), 4, WHITE, -1, cv2.LINE_AA)


def draw_hud(frame, detector, app_name: str, fps: float,
             last_event: str, last_event_at: float, dry_run: bool,
             recording: bool = False) -> None:
    lines = [f"Mao: {POSE_LABELS.get(detector.pose, '-')}  |  FPS: {fps:.0f}"]

    if recording:
        lines.append("REC: ON")

    if detector.pose == POSE_OPEN_HAND:
        secs = detector.hold_progress * detector.hold_seconds
        filled = int(detector.hold_progress * 22)
        bar = "#" * filled + "." * (22 - filled)
        lines.append(f"Abrir {app_name}: [{bar}] {secs:.1f}s/{detector.hold_seconds:.1f}s")

    if last_event and time.monotonic() - last_event_at < 2.0:
        lines.append(f">>> {EVENT_LABELS.get(last_event, last_event)}")
    if dry_run:
        lines.append("DRY-RUN: nenhuma acao executada")

    x, y0, dy = 12, 28, 26
    for i, text in enumerate(lines):
        y = y0 + i * dy
        color = RED if text.startswith("DRY-RUN") else WHITE
        cv2.putText(frame, text, (x + 1, y + 1), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, DARK, 3, cv2.LINE_AA)
        cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, color, 1, cv2.LINE_AA)
