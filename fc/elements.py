"""
fc/elements.py
Wrappers da DSL: Field, Button e Window.

Ações sempre por foco direto no componente — nunca TAB, nunca coordenada.
Asserts `should_*` falham duro (AssertionError), estilo Cypress.
"""

from __future__ import annotations

from loguru import logger

from core.actions import safe_click, safe_type, wait_window

from .locator_engine import resolver


def _norm(v) -> str:
    return "" if v is None else str(v).strip()


class _Elemento:
    """Base: resolve o alias para um elemento vivo na janela ativa do módulo."""

    def __init__(self, ctx, info: dict):
        self._ctx = ctx
        self._info = info
        self.alias = info.get("alias", "?")

    def _resolver(self, timeout: float = 10.0):
        janela = self._ctx.janela_ativa()
        return resolver(janela, self._info, timeout=timeout, label=self.alias)

    # ── asserts comuns ───────────────────────────────────────────
    def should_exist(self, timeout: float = 10.0):
        self._resolver(timeout=timeout)
        logger.success(f"✓ should_exist: '{self.alias}' existe")
        return self

    def should_be_visible(self, timeout: float = 10.0):
        el = self._resolver(timeout=timeout)
        if not el.is_visible():
            raise AssertionError(f"Elemento '{self.alias}' não está visível")
        logger.success(f"✓ should_be_visible: '{self.alias}'")
        return self


class Field(_Elemento):
    def click(self):
        el = self._resolver()
        safe_click(el, label=f"campo {self.alias}")
        return self

    def type(self, texto: str):
        el = self._resolver()
        el.set_focus()
        safe_type(el, texto, label=f"campo {self.alias}")
        return self

    def clear(self):
        el = self._resolver()
        el.set_focus()
        el.type_keys("^a{DEL}")
        return self

    def press(self, keys: str):
        el = self._resolver()
        el.set_focus()
        el.type_keys(keys)
        return self

    def get_value(self) -> str:
        el = self._resolver()
        try:
            return _norm(el.get_value())   # UIA Edit
        except Exception:
            return _norm(el.window_text())

    def should_have_value(self, esperado: str):
        obtido = self.get_value()
        if _norm(obtido) != _norm(esperado):
            raise AssertionError(
                f"Campo '{self.alias}': esperado '{esperado}', obtido '{obtido}'"
            )
        logger.success(f"✓ should_have_value: '{self.alias}' = '{esperado}'")
        return self

    def should_have_text(self, esperado: str):
        """Igual a should_have_value para campos Delphi (texto == valor do edit)."""
        obtido = self.get_value()
        if _norm(obtido) != _norm(esperado):
            raise AssertionError(
                f"Campo '{self.alias}': texto esperado '{esperado}', obtido '{obtido}'"
            )
        logger.success(f"✓ should_have_text: '{self.alias}' = '{esperado}'")
        return self


class Button(_Elemento):
    def click(self):
        el = self._resolver()
        safe_click(el, label=f"botão {self.alias}")
        return self

    def double_click(self):
        el = self._resolver()
        el.set_focus()
        el.double_click_input()
        logger.info(f"Duplo clique: botão {self.alias}")
        return self


class Window:
    """Wrapper de janela/modal do módulo (resolvido por título via regex)."""

    def __init__(self, ctx, titulo: str, timeout: float = 10.0):
        self._ctx = ctx
        self.titulo = titulo
        app = ctx.app_modulo
        if app is None:
            raise RuntimeError("Nenhum módulo aberto. Chame fc.open_module(...) antes.")
        self._win = wait_window(app, titulo, timeout=timeout, label=titulo)
        self._win.set_focus()

    @property
    def janela(self):
        return self._win

    def press(self, keys: str):
        self._win.set_focus()
        self._win.type_keys(keys)
        return self

    def ok(self):
        return self.press("{ENTER}")

    def close(self):
        self._win.set_focus()
        self._win.type_keys("%{F4}")
        return self

    def should_exist(self):
        logger.success(f"✓ should_exist: janela '{self.titulo}'")
        return self
