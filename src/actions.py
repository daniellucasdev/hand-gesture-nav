"""Ações de sistema do macOS disparadas pelos gestos.

Troca de Space via AppleScript (key code + command) e abertura de app via
`open -a`. Com dry_run=True nenhuma ação é executada, só logada — usado
pelos testes e para experimentar os gestos sem efeito colateral.
"""

from __future__ import annotations

import subprocess

# Key codes do macOS: 123 = seta esquerda, 124 = seta direita
ARROW_KEYCODES = {"left": 123, "right": 124}

ACCESSIBILITY_HINT = (
    "[dica] O macOS bloqueou o envio de teclas. Permita em: Ajustes do Sistema"
    " > Privacidade e Segurança > Acessibilidade > ative o Terminal (ou o app"
    " de onde você rodou este projeto) e tente de novo."
)


def switch_space(direction: str, dry_run: bool = False) -> bool:
    """Troca o Space ativo com ctrl + seta. direction: 'left' | 'right'."""
    if direction not in ARROW_KEYCODES:
        raise ValueError(f"direção inválida: {direction!r} (use 'left' ou 'right')")
    keycode = ARROW_KEYCODES[direction]
    script = (
        'tell application "System Events" to key code '
        f"{keycode} using control down"
    )
    label = (
        f"Space para a {'esquerda (ctrl+←)' if direction == 'left' else 'direita (ctrl+→)'}"
    )
    return _run(["osascript", "-e", script], label, dry_run)


def open_app(app_name: str = "Claude", dry_run: bool = False) -> bool:
    """Abre (ou traz para frente) um aplicativo instalado em /Applications."""
    return _run(["open", "-a", app_name], f"abrir app: {app_name}", dry_run)


def _run(cmd: list[str], label: str, dry_run: bool) -> bool:
    print(f"[ação] {label}" + ("  [dry-run]" if dry_run else ""), flush=True)
    if dry_run:
        return True
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        print(f"[erro] {label}: {exc}", flush=True)
        return False
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        print(f"[erro] {label}: {stderr}", flush=True)
        denied = (
            "(1002)" in stderr
            or "assistive access" in stderr.lower()
            or "acionar teclas" in stderr.lower()
            or "send keystrokes" in stderr.lower()
        )
        if denied:
            print(ACCESSIBILITY_HINT, flush=True)
        return False
    return True
