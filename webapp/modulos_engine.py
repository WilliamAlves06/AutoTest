"""webapp/modulos_engine.py — gravador de teclas/cliques p/ ensinar a abertura
de um módulo (sem GUI). Porta a lógica de pages/modulos_ui.py: clique no item
do menu vira "@menuitem:i,j" (índice, livre de resolução via GetMenuItemRect);
teclas viram a sintaxe type_keys (%a, {RIGHT}, {ENTER}...).
"""

from __future__ import annotations

import os
from typing import Callable, Optional


class MenuRecorder:
    """Escuta mouse e teclado globalmente; emite tokens via callback."""

    def __init__(self) -> None:
        self._gravando = False
        self._kb_listener = None
        self._mouse_listener = None
        self._mods_pressionados: set[str] = set()
        self._on_token: Optional[Callable[[str], None]] = None

    def is_running(self) -> bool:
        return self._gravando

    def start(self, on_token: Callable[[str], None]) -> None:
        if self._gravando:
            return
        from pynput import keyboard, mouse

        self._on_token = on_token
        self._mods_pressionados.clear()
        self._kb_listener = keyboard.Listener(
            on_press=self._on_key_press, on_release=self._on_key_release
        )
        self._kb_listener.start()
        self._mouse_listener = mouse.Listener(on_click=self._on_click)
        self._mouse_listener.start()
        self._gravando = True

    def stop(self) -> None:
        self._gravando = False
        for attr in ("_kb_listener", "_mouse_listener"):
            lst = getattr(self, attr)
            if lst is not None:
                try:
                    lst.stop()
                except Exception:
                    pass
                setattr(self, attr, None)

    # ── mouse: clique no menu -> @menuitem:i,j ───────────────────
    def _on_click(self, x, y, button, pressed) -> None:
        if not pressed:
            return
        try:
            from pynput.mouse import Button
            if button != Button.left:
                return
        except Exception:
            pass
        if not self._gravando:
            return
        token = self._clique_para_menuitem(int(x), int(y)) or f"@click:{int(x)},{int(y)}"
        if self._on_token:
            self._on_token(token)

    @staticmethod
    def _clique_para_menuitem(x: int, y: int) -> Optional[str]:
        try:
            import ctypes
            from ctypes import wintypes
            import win32gui

            from fc.context import _achar_main_hwnd
            hwnd = _achar_main_hwnd()
            if not hwnd:
                return None
            hmenu = win32gui.GetMenu(hwnd)
            if not hmenu:
                return None

            user32 = ctypes.windll.user32

            def _rect(hm, idx):
                rc = wintypes.RECT()
                if user32.GetMenuItemRect(hwnd, hm, idx, ctypes.byref(rc)):
                    return (rc.left, rc.top, rc.right, rc.bottom)
                return None

            def _dentro(r):
                return r and r[0] <= x <= r[2] and r[1] <= y <= r[3]

            n_top = win32gui.GetMenuItemCount(hmenu)
            for i in range(n_top):
                hsub = win32gui.GetSubMenu(hmenu, i)
                if hsub:
                    for j in range(win32gui.GetMenuItemCount(hsub)):
                        if _dentro(_rect(hsub, j)):
                            return f"@menuitem:{i},{j}"
                if _dentro(_rect(hmenu, i)):
                    return f"@menuitem:{i}"
            return None
        except Exception:
            return None

    # ── teclado: teclas avulsas -> sintaxe type_keys ─────────────
    def _on_key_release(self, key) -> None:
        nome = self._nome_modificador(key)
        if nome:
            self._mods_pressionados.discard(nome)

    def _on_key_press(self, key) -> None:
        modnome = self._nome_modificador(key)
        if modnome:
            self._mods_pressionados.add(modnome)
            return
        token = self._tecla_para_token(key)
        if token and self._on_token:
            self._on_token(token)

    @staticmethod
    def _nome_modificador(key) -> Optional[str]:
        from pynput import keyboard
        if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
            return "alt"
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            return "ctrl"
        if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
            return "shift"
        return None

    def _tecla_para_token(self, key) -> Optional[str]:
        from pynput import keyboard

        especiais = {
            keyboard.Key.down: "{DOWN}", keyboard.Key.up: "{UP}",
            keyboard.Key.left: "{LEFT}", keyboard.Key.right: "{RIGHT}",
            keyboard.Key.enter: "{ENTER}", keyboard.Key.tab: "{TAB}",
            keyboard.Key.esc: "{ESC}", keyboard.Key.space: "{SPACE}",
            keyboard.Key.home: "{HOME}", keyboard.Key.end: "{END}",
            keyboard.Key.backspace: "{BACKSPACE}", keyboard.Key.delete: "{DELETE}",
        }
        for i in range(1, 13):
            f = getattr(keyboard.Key, f"f{i}", None)
            if f is not None:
                especiais[f] = "{F%d}" % i

        base = especiais.get(key)
        if base is None:
            ch = None
            chattr = getattr(key, "char", None)
            if chattr and chattr.isprintable():
                ch = chattr
            else:
                vk = getattr(key, "vk", None)
                if vk is not None:
                    if 65 <= vk <= 90:
                        ch = chr(vk).lower()
                    elif 48 <= vk <= 57:
                        ch = chr(vk)
                    elif 96 <= vk <= 105:
                        ch = chr(vk - 48)
            if not ch:
                return None
            base = ch

        prefixo = ""
        if "alt" in self._mods_pressionados:
            prefixo += "%"
        if "ctrl" in self._mods_pressionados:
            prefixo += "^"
        if "shift" in self._mods_pressionados and len(base) == 1 and base.isalpha():
            prefixo += "+"
        return prefixo + base
