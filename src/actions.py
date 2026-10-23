"""Ações de sistema do macOS disparadas pelos gestos.

Troca de Space via AppleScript (key code + command) e abertura de app via
`open -a`. Com dry_run=True nenhuma ação é executada, só logada — usado
pelos testes e para experimentar os gestos sem efeito colateral.
"""

from __future__ import annotations

import subprocess
import time

# Key codes do macOS: 123 = seta esquerda, 124 = seta direita
ARROW_KEYCODES = {"left": 123, "right": 124}

MODIFIERS = {
    "cmd": "command down",
    "ctrl": "control down",
    "alt": "option down",
    "opt": "option down",
    "shift": "shift down",
    "fn": "fn down",
}

# Teclas nomeadas aceitas em --voice-keys (key codes do macOS)
NAMED_KEYS = {
    "enter": 36, "return": 36, "space": 49, "tab": 48, "esc": 53,
    "delete": 51, "left": 123, "right": 124, "down": 125, "up": 126,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
    "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
}

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


def press_enter(dry_run: bool = False) -> bool:
    """Aperta Enter (key code 36) no app em foco."""
    script = 'tell application "System Events" to key code 36'
    return _run(["osascript", "-e", script], "Enter", dry_run)


def parse_keys(spec: str) -> tuple[list[str], str]:
    """Converte "ctrl+shift+d" em (modificadores osascript, tecla).

    A tecla pode ser nomeada (enter, space, f5...), um key code numérico ou
    um caractere (vai via keystroke).
    """
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    if not parts:
        raise ValueError(f"atalho vazio: {spec!r}")
    *mods, key = parts
    osa_mods = []
    for m in mods:
        if m not in MODIFIERS:
            raise ValueError(f"modificador desconhecido: {m!r} (use {', '.join(MODIFIERS)})")
        osa_mods.append(MODIFIERS[m])
    if not key:
        raise ValueError(f"atalho sem tecla: {spec!r}")
    return osa_mods, key


def send_keys(spec: str, dry_run: bool = False) -> bool:
    """Envia um atalho de teclado ("ctrl+shift+d", "f5", "enter", "a"...)."""
    mods, key = parse_keys(spec)
    if key.isdigit():
        action = f"key code {key}"
    elif key in NAMED_KEYS:
        action = f"key code {NAMED_KEYS[key]}"
    elif len(key) == 1:
        action = f'keystroke "{key}"'
    else:
        raise ValueError(f"tecla desconhecida: {key!r} (nome, key code ou 1 caractere)")
    if mods:
        action += f" using {{{', '.join(mods)}}}"
    return _run(
        ["osascript", "-e", f'tell application "System Events" to {action}'],
        f"atalho {spec}",
        dry_run,
    )


def toggle_recording(
    app_name: str, start: bool, key_spec: str, dry_run: bool = False
) -> bool:
    """Ativa o app e (se configurado) envia o atalho de gravação de áudio.

    `start` diz se este disparo INICIA (True) ou ENCERRA (False) a gravação —
    o estado é mantido por quem chama. Sem key_spec, o gesto apenas traz o
    app para frente e avisa como configurar o atalho.
    """
    verbo = "iniciar" if start else "encerrar"
    ok = _run(["open", "-a", app_name], f"{verbo} gravação: ativar {app_name}", dry_run)
    if key_spec:
        time.sleep(0.4)  # dar foco ao app antes do atalho
        ok = send_keys(key_spec, dry_run) and ok
    elif not dry_run:
        print(
            "[aviso] Sem atalho de gravação configurado: use --voice-keys com o"
            f" atalho de voz/ditado do seu {app_name} (ex.: --voice-keys f5).",
            flush=True,
        )
    return ok


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
