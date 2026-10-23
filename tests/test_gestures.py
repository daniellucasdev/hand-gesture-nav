"""Testes do detector de gestos com landmarks sintéticos (determinísticos).

Constrói mãos artificiais nos 21 pontos do MediaPipe e percorre o tempo
frame a frame (30 fps simulados), checando exatamente os eventos disparados.
"""

import math

from gestures import (
    GestureDetector,
    POSE_NONE,
    POSE_OPEN_HAND,
    POSE_TWO_FINGERS,
    classify_pose,
)

FPS = 30.0
DT = 1.0 / FPS

FINGER_DIRECTIONS = {
    "index": -0.10,
    "middle": 0.0,
    "ring": 0.10,
    "pinky": 0.20,
}


def make_hand(palm_x=0.5, pose="open"):
    """Mão sintética com pulso em (palm_x, 0.70), dedos apontando para cima.

    pose: 'open' (5 dedos estendidos), 'two' (indicador+médio),
    'two_thumb' (indicador+médio com POLEGAR aberto — o V natural),
    'fist' (todos dobrados), 'three' (indicador+médio+anelar).
    """
    wrist = (palm_x, 0.70)
    lm = [None] * 21
    lm[0] = wrist

    def finger(base_idx, dx, extended):
        mcp = (wrist[0] + dx, wrist[1] - 0.10)
        pip = (wrist[0] + dx, wrist[1] - 0.18)
        dip = (wrist[0] + dx, wrist[1] - 0.22)
        if extended:
            tip = (wrist[0] + dx, wrist[1] - 0.32)
        else:  # dobrado: ponta mais perto do pulso que o pip
            tip = (wrist[0] + dx, wrist[1] - 0.16)
        lm[base_idx] = mcp
        lm[base_idx + 1] = pip
        lm[base_idx + 2] = dip
        lm[base_idx + 3] = tip

    ext = {
        "index": pose in ("open", "two", "three", "two_thumb"),
        "middle": pose in ("open", "two", "three", "two_thumb"),
        "ring": pose in ("open", "three"),
        "pinky": pose == "open",
    }
    finger(5, FINGER_DIRECTIONS["index"], ext["index"])
    finger(9, FINGER_DIRECTIONS["middle"], ext["middle"])
    finger(13, FINGER_DIRECTIONS["ring"], ext["ring"])
    finger(17, FINGER_DIRECTIONS["pinky"], ext["pinky"])

    # polegar: estendido se afastando da palma; dobrado cruzando sobre ela
    if pose in ("open", "two_thumb"):
        lm[1] = (wrist[0] - 0.05, wrist[1] - 0.04)
        lm[2] = (wrist[0] - 0.10, wrist[1] - 0.08)
        lm[3] = (wrist[0] - 0.15, wrist[1] - 0.11)
        lm[4] = (wrist[0] - 0.20, wrist[1] - 0.13)
    else:
        lm[1] = (wrist[0] - 0.05, wrist[1] - 0.04)
        lm[2] = (wrist[0] - 0.07, wrist[1] - 0.06)
        lm[3] = (wrist[0] - 0.04, wrist[1] - 0.03)
        lm[4] = (wrist[0] + 0.01, wrist[1] - 0.02)
    return [(p[0], p[1], 0.0) for p in lm]


def run(detector, frames, t0=100.0):
    """Alimenta o detector; frames = lista de (landmarks|None)."""
    events = []
    for i, lm in enumerate(frames):
        events += detector.update(lm, t0 + i * DT)
    return events


# ---------------------------------------------------------------- poses ----

def test_poses_classificadas():
    assert classify_pose(make_hand(pose="open")) == POSE_OPEN_HAND
    assert classify_pose(make_hand(pose="two")) == POSE_TWO_FINGERS
    assert classify_pose(make_hand(pose="two_thumb")) == POSE_TWO_FINGERS
    assert classify_pose(make_hand(pose="fist")) == POSE_NONE
    assert classify_pose(make_hand(pose="three")) == POSE_NONE


# --------------------------------------------------------------- swipe -----

def test_swipe_direita_para_esquerda_troca_para_direita():
    det = GestureDetector()
    frames = [make_hand(palm_x=x, pose="two") for x in _ramp(0.70, 0.40, 12)]
    assert run(det, frames) == ["workspace_right"]


def test_v_natural_com_polegar_aberto_dispara_swipe():
    """Reproduz a calibração real: V com polegar semi-aberto deve funcionar."""
    det = GestureDetector()
    frames = [make_hand(palm_x=x, pose="two_thumb") for x in _ramp(0.70, 0.40, 12)]
    assert run(det, frames) == ["workspace_right"]


def test_oscilacao_de_pose_nao_quebra_o_swipe():
    """Votação majoritária: frames de pose errada intercalados não resetam."""
    det = GestureDetector()
    frames = []
    for i, x in enumerate(_ramp(0.70, 0.40, 12)):
        pose = "fist" if i % 3 == 1 else "two"  # 1/3 dos frames oscila
        frames.append(make_hand(palm_x=x, pose=pose))
    assert run(det, frames) == ["workspace_right"]


def test_gap_curto_de_mao_nao_quebra_o_swipe():
    """Grace period: a mão sumindo 4 frames no meio do trajeto não reseta."""
    det = GestureDetector()
    frames = [
        make_hand(palm_x=x, pose="two") if not (5 <= i < 9) else None
        for i, x in enumerate(_ramp(0.70, 0.40, 12))
    ]
    assert run(det, frames) == ["workspace_right"]


def test_gap_longo_zera_o_trajeto():
    det = GestureDetector()
    frames = [make_hand(palm_x=x, pose="two") for x in _ramp(0.70, 0.58, 12)]
    frames += [None] * 12                      # 0.4s fora do frame
    frames += [make_hand(palm_x=0.58, pose="two")] * 30  # reaparece parada
    assert run(det, frames) == []


def test_swipe_esquerda_para_direita_troca_para_esquerda():
    det = GestureDetector()
    frames = [make_hand(palm_x=x, pose="two") for x in _ramp(0.30, 0.60, 12)]
    assert run(det, frames) == ["workspace_left"]


def test_arrasto_lento_nao_dispara():
    det = GestureDetector()
    # mesmo trajeto espalhado em 2s: janela de 0.35s nunca acumula 0.20
    frames = [make_hand(palm_x=x, pose="two") for x in _ramp(0.30, 0.55, 60)]
    assert run(det, frames) == []


def test_tremido_pequeno_nao_dispara():
    det = GestureDetector()
    frames = [
        make_hand(palm_x=0.5 + 0.008 * math.sin(i / 2.0), pose="two")
        for i in range(60)
    ]
    assert run(det, frames) == []


def test_movimento_vertical_nao_dispara():
    det = GestureDetector()
    frames = []
    for i in range(30):
        y = 0.45 + 0.25 * (i / 30.0)  # mão desce cruzando a tela
        frames.append(_shift_y(make_hand(palm_x=0.5, pose="two"), y - 0.70))
    assert run(det, frames) == []


def test_mao_aberta_rapida_nao_e_swipe():
    det = GestureDetector()
    frames = [make_hand(palm_x=x, pose="open") for x in _ramp(0.25, 0.70, 15)]
    assert run(det, frames) == []  # swipe exige a pose de dois dedos


def test_swipe_logo_depois_e_suprimido_pelo_cooldown():
    det = GestureDetector()
    frames = []
    frames += [make_hand(palm_x=x, pose="two") for x in _ramp(0.70, 0.40, 12)]
    frames += [make_hand(palm_x=0.40, pose="two")] * 9   # pausa de 0.3s
    frames += [make_hand(palm_x=x, pose="two") for x in _ramp(0.40, 0.70, 12)]
    # o segundo trajeto termina dentro do cooldown de 1.2s -> suprimido
    assert run(det, frames) == ["workspace_right"]


def test_swipes_sequenciais_apos_cooldown_disparam():
    det = GestureDetector()
    frames = []
    frames += [make_hand(palm_x=x, pose="two") for x in _ramp(0.70, 0.40, 12)]
    frames += [make_hand(palm_x=0.40, pose="two")] * 40  # pausa de ~1.3s
    frames += [make_hand(palm_x=x, pose="two") for x in _ramp(0.40, 0.70, 12)]
    assert run(det, frames) == ["workspace_right", "workspace_left"]


def test_tracking_quebrado_zera_estado():
    det = GestureDetector()
    # primeiro movimento curto demais para disparar
    frames = [make_hand(palm_x=x, pose="two") for x in _ramp(0.70, 0.62, 10)]
    frames += [None] * 5  # mão some
    frames += [make_hand(palm_x=0.35, pose="two")]
    # reaparece longe e desliza de volta: o trajeto anterior não vaza
    frames += [make_hand(palm_x=x, pose="two") for x in _ramp(0.35, 0.10, 12)]
    events = run(det, frames)
    assert events == ["workspace_right"]


# ---------------------------------------------------------- mão aberta -----

def test_mao_aberta_2s_dispara_uma_vez():
    det = GestureDetector()
    frames = [make_hand(pose="open")] * 75  # 2.5s a 30fps
    events = run(det, frames)
    assert events == ["open_app"]


def test_mao_aberta_1s_nao_dispara():
    det = GestureDetector()
    frames = [make_hand(pose="open")] * 29  # ~0.97s
    assert run(det, frames) == []


def test_mao_aberta_re_arma_apenas_apos_fechar():
    det = GestureDetector()
    t0 = 100.0
    events = []
    events += run(det, [make_hand(pose="open")] * 75, t0)          # dispara
    events += run(det, [make_hand(pose="open")] * 75, t0 + 75 * DT)  # seguiu segurando
    assert events == ["open_app"]
    # fecha a mão e abre de novo, passando o cooldown de 4s
    t2 = t0 + 150 * DT
    events += run(det, [make_hand(pose="fist")] * 30, t2)
    events += run(det, [make_hand(pose="open")] * 90, t2 + 30 * DT)  # 3s segurando
    assert events == ["open_app", "open_app"]


def test_sem_mao_reseta_progresso():
    det = GestureDetector()
    frames = [make_hand(pose="open")] * 30  # 1s segurando
    frames += [None] * 10                   # some
    frames += [make_hand(pose="open")] * 45  # reaparece e segura 1.5s
    assert run(det, frames) == []  # nunca atinge 2s contínuos


# ------------------------------------------------------------ auxiliares ----

def _ramp(a, b, n):
    return [a + (b - a) * i / (n - 1) for i in range(n)]


def _shift_y(lm, dy):
    return [(x, y + dy, z) for (x, y, z) in lm]
