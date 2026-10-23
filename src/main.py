#!/usr/bin/env python3
"""Hand Gesture Nav — controle de Spaces do macOS por gestos de mão.

Uso:
    python src/main.py                     # janela da câmera com overlay
    python src/main.py --dry-run           # loga as ações sem executar
    python src/main.py --frames 120        # sai após N frames (smoke test)
    python src/main.py --no-window         # sem janela (roda em background)

Gestos:
    swipe (indicador+médio) da direita p/ esquerda -> ctrl+→ (Space direita)
    swipe (indicador+médio) da esquerda p/ direita -> ctrl+← (Space esquerda)
    mão aberta por 2 segundos                      -> abre o Claude Desktop
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import cv2  # noqa: E402
import mediapipe as mp  # noqa: E402
from mediapipe.tasks import python as mp_python  # noqa: E402
from mediapipe.tasks.python import vision as mp_vision  # noqa: E402

from actions import open_app, switch_space  # noqa: E402
from gestures import GestureDetector  # noqa: E402
import overlay  # noqa: E402

WINDOW_NAME = "Hand Gesture Nav  (Q sai)"
CAMERA_HINT = (
    "[erro] Sem acesso à câmera (índice {index}). Conceda em: Ajustes do Sistema"
    " > Privacidade e Segurança > Câmera > ative o Terminal (ou o app de onde"
    " rodou o projeto) e rode de novo."
)
MODEL_HINT = (
    "[erro] Modelo não encontrado em {path}.\n"
    "       Rode scripts/setup.sh (baixa o hand_landmarker.task oficial do"
    " MediaPipe) e tente de novo."
)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--camera", default="0",
                   help="índice da webcam (default 0) ou caminho de vídeo p/ teste")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument("--model", default="models/hand_landmarker.task", help="caminho do .task")
    p.add_argument("--app-name", default="Claude", help="app aberto pela mão aberta (default Claude)")
    p.add_argument("--hold-seconds", type=float, default=2.0, help="segundos de mão aberta (default 2.0)")
    p.add_argument("--cooldown", type=float, default=1.2, help="cooldown de swipe em segundos (default 1.2)")
    p.add_argument("--confidence", type=float, default=0.6, help="confiança mínima de detecção")
    p.add_argument("--delegate", choices=("CPU", "GPU"), default="CPU",
                   help="delegata do MediaPipe (GPU/Metal falha nesta versão; CPU roda a ~45fps)")
    p.add_argument("--no-mirror", action="store_true", help="não espelhar a imagem")
    p.add_argument("--no-window", action="store_true", help="sem janela de preview")
    p.add_argument("--debug", action="store_true",
                   help="telemetria de calibração (pose/trajeto) a cada 0,5s")
    p.add_argument("--dry-run", action="store_true", help="loga ações sem executar")
    p.add_argument("--frames", type=int, default=0, help="sair após N frames (0 = roda até Q)")
    return p.parse_args(argv)


def create_landmarker(model_path: str, confidence: float, delegate: str):
    """HandLandmarker em modo VIDEO com o delegata pedido ('GPU' ou 'CPU')."""
    delegate_enum = getattr(mp_python.BaseOptions.Delegate, delegate)
    base = mp_python.BaseOptions(model_asset_path=model_path, delegate=delegate_enum)
    options = mp_vision.HandLandmarkerOptions(
        base_options=base,
        running_mode=mp_vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=confidence,
        min_hand_presence_confidence=confidence,
        min_tracking_confidence=0.5,
    )
    return mp_vision.HandLandmarker.create_from_options(options)


def main(argv=None) -> int:
    args = parse_args(argv)
    model_path = pathlib.Path(args.model)
    if not model_path.exists():
        print(MODEL_HINT.format(path=model_path))
        return 1

    det = GestureDetector(hold_seconds=args.hold_seconds, swipe_cooldown=args.cooldown)
    landmarker = create_landmarker(str(model_path), args.confidence, args.delegate)

    source = int(args.camera) if str(args.camera).isdigit() else args.camera
    from_file = not str(args.camera).isdigit()
    cap = cv2.VideoCapture(source)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    if not cap.isOpened():
        print(CAMERA_HINT.format(index=args.camera))
        return 1

    print(f"[ok] {args.app_name} alvo da mão aberta ({args.hold_seconds:.0f}s)."
          + (" DRY-RUN: ações só serão logadas." if args.dry_run else ""),
          flush=True)
    print("[ok] Câmera aberta. Q na janela (ou Ctrl+C) para sair.", flush=True)

    fps, last_t = 0.0, time.monotonic()
    last_event, last_event_at = "", 0.0
    last_debug = 0.0
    frame_i, read_fails, last_ms = 0, 0, 0
    dispatch = {
        "workspace_left": lambda: switch_space("left", args.dry_run),
        "workspace_right": lambda: switch_space("right", args.dry_run),
        "open_app": lambda: open_app(args.app_name, args.dry_run),
    }

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                if from_file:
                    break  # fim do vídeo de teste
                read_fails += 1
                if read_fails > 30:
                    print(CAMERA_HINT.format(index=args.camera))
                    return 1
                continue
            read_fails = 0
            frame_i += 1

            if not args.no_mirror:
                frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            now = time.monotonic()
            if now - last_t > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / (now - last_t))
            last_t = now

            ms = max(last_ms + 1, int(now * 1000))  # timestamps precisam crescer
            last_ms = ms
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect_for_video(mp_image, ms)

            landmarks = None
            if result.hand_landmarks:
                landmarks = [(p.x, p.y, p.z) for p in result.hand_landmarks[0]]
            for event in det.update(landmarks, now):
                last_event, last_event_at = event, now
                dispatch[event]()

            if args.debug and now - last_debug > 0.5:
                last_debug = now
                print(f"[debug] {det.debug_state()}", flush=True)

            if not args.no_window:
                if det.smoothed is not None:
                    overlay.draw_landmarks(frame, det.smoothed)
                overlay.draw_hud(frame, det, args.app_name, fps,
                                 last_event, last_event_at, args.dry_run)
                cv2.imshow(WINDOW_NAME, frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    break

            if args.frames and frame_i >= args.frames:
                break
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        if not args.no_window:
            cv2.destroyAllWindows()
        landmarker.close()
    print("[ok] Encerrado.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
