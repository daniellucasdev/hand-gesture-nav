"""Testes das ações com dry_run=True (nada executa de verdade)."""

import pytest

from actions import parse_keys, press_enter, send_keys, switch_space, toggle_recording


def test_parse_keys_combos():
    assert parse_keys("ctrl+shift+d") == (["control down", "shift down"], "d")
    assert parse_keys("F5") == ([], "f5")
    assert parse_keys("enter") == ([], "enter")
    assert parse_keys("43") == ([], "43")


def test_parse_keys_invalidos():
    with pytest.raises(ValueError):
        parse_keys("banana+d")  # modificador desconhecido
    with pytest.raises(ValueError):
        parse_keys("")  # vazio


def test_send_keys_dry_run():
    assert send_keys("f5", dry_run=True) is True
    assert send_keys("ctrl+shift+d", dry_run=True) is True
    with pytest.raises(ValueError):
        send_keys("banana", dry_run=True)  # tecla desconhecida


def test_dry_run_nao_executa_nada():
    assert switch_space("left", dry_run=True) is True
    assert press_enter(dry_run=True) is True
    assert toggle_recording("Claude", True, "f5", dry_run=True) is True
    assert toggle_recording("Claude", False, "", dry_run=True) is True
    with pytest.raises(ValueError):
        switch_space("up", dry_run=True)
