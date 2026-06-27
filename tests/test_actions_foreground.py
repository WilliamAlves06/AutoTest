"""Testes do foreground da janela antes de focar o controle (core/actions.py)."""

import pytest

from core.actions import _trazer_janela_frente, safe_click, safe_type

pytestmark = pytest.mark.unit


class _Top:
    """Janela de topo falsa: registra is_minimized/restore/set_focus."""
    def __init__(self, log, minimized=False):
        self._log = log
        self._min = minimized

    def is_minimized(self):
        self._log.append("is_minimized")
        return self._min

    def restore(self):
        self._log.append("restore")

    def set_focus(self):
        self._log.append("top.set_focus")


class _El:
    """Controle falso cujo top_level_parent() é uma _Top compartilhando o log."""
    def __init__(self, log, minimized=False):
        self._log = log
        self._top = _Top(log, minimized=minimized)

    def top_level_parent(self):
        return self._top

    def set_focus(self):
        self._log.append("el.set_focus")

    def type_keys(self, text, **kw):
        self._log.append(("type_keys", text))

    def click_input(self):
        self._log.append("click_input")


def test_trazer_janela_frente_foca_o_topo():
    log = []
    _trazer_janela_frente(_El(log))
    assert "top.set_focus" in log


def test_trazer_janela_frente_restaura_se_minimizada():
    log = []
    _trazer_janela_frente(_El(log, minimized=True))
    assert log == ["is_minimized", "restore", "top.set_focus"]


def test_trazer_janela_frente_nunca_quebra():
    class _Quebra:
        def top_level_parent(self):
            raise RuntimeError("sem janela")
    _trazer_janela_frente(_Quebra())   # não deve levantar


def test_safe_type_foca_o_topo_antes_do_controle():
    log = []
    safe_type(_El(log), "57", label="Filial")
    assert log == ["is_minimized", "top.set_focus", "el.set_focus", ("type_keys", "57")]


def test_safe_click_foca_o_topo_antes_do_controle():
    log = []
    safe_click(_El(log), label="salvar")
    assert log == ["is_minimized", "top.set_focus", "el.set_focus", "click_input"]
