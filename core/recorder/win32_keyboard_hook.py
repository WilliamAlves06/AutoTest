"""
Hook de teclado de baixo nivel (Win32) para capturar setas, Enter e menus Alt+letra.
Complementa o pynput quando o menu do sistema esta ativo.
"""

from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes
from typing import Callable, Optional

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
LLKHF_ALTDOWN = 0x20

VK_MENU = 0x12
VK_LMENU = 0xA4
VK_RMENU = 0xA5
VK_RETURN = 0x0D
VK_TAB = 0x09
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_BACK = 0x08
VK_DELETE = 0x2E
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_PRIOR = 0x21
VK_NEXT = 0x22
VK_HOME = 0x24
VK_END = 0x23
VK_F1 = 0x70

_DEBOUNCE_SEC = 0.08

_ALT_ONLY_VKS = {VK_MENU, VK_LMENU, VK_RMENU}


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
    ctypes.c_long,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
)

# Instancia ativa — callback em modulo evita WinFunctionType duplicado no Py 3.14
_active_hook: Optional["Win32KeyboardHook"] = None


@LowLevelKeyboardProc
def _global_hook_proc(n_code, w_param, l_param):
    hook = _active_hook
    if hook is None or not hook._running:
        return user32.CallNextHookEx(0, n_code, w_param, l_param)
    return hook._hook_callback(n_code, w_param, l_param)


user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    LowLevelKeyboardProc,
    wintypes.HINSTANCE,
    wintypes.DWORD,
]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = ctypes.c_long
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.PeekMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
    wintypes.UINT,
]
user32.PeekMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetCurrentThreadId.restype = wintypes.DWORD


def _vk_to_type_keys(vk: int) -> Optional[str]:
    mapping = {
        VK_RETURN: "{ENTER}",
        VK_TAB: "{TAB}",
        VK_ESCAPE: "{ESC}",
        VK_SPACE: " ",
        VK_BACK: "{BACKSPACE}",
        VK_DELETE: "{DELETE}",
        VK_LEFT: "{LEFT}",
        VK_UP: "{UP}",
        VK_RIGHT: "{RIGHT}",
        VK_DOWN: "{DOWN}",
        VK_PRIOR: "{PGUP}",
        VK_NEXT: "{PGDN}",
        VK_HOME: "{HOME}",
        VK_END: "{END}",
    }
    if vk in mapping:
        return mapping[vk]
    if VK_F1 <= vk <= VK_F1 + 11:
        return f"{{F{vk - VK_F1 + 1}}}"
    return None


class Win32KeyboardHook:
    """Captura teclas de navegacao e atalhos Alt (callback leve, sem pywinauto)."""

    def __init__(self, on_special_key: Callable[[str], None]):
        self._on_special_key = on_special_key
        self._hook_id = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._installed = False
        self._last_sig: Optional[tuple] = None
        self._last_time = 0.0
        self._thread_id: Optional[int] = None
        self._proc = None
        self.last_error: Optional[str] = None

    @property
    def is_installed(self) -> bool:
        return self._installed

    def start(self) -> bool:
        if self._running:
            return self._installed
        self._running = True
        self.last_error = None
        self._thread = threading.Thread(target=self._message_loop, daemon=True)
        self._thread.start()
        for _ in range(50):
            if self._installed or self.last_error:
                break
            time.sleep(0.02)
        return self._installed

    def stop(self) -> None:
        self._running = False
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)

    def _message_loop(self) -> None:
        global _active_hook  # noqa: PLW0603
        self._thread_id = kernel32.GetCurrentThreadId()
        _active_hook = self
        self._proc = _global_hook_proc
        try:
            self._hook_id = user32.SetWindowsHookExW(
                WH_KEYBOARD_LL,
                _global_hook_proc,
                kernel32.GetModuleHandleW(None),
                0,
            )
        except (ctypes.ArgumentError, TypeError) as exc:
            self.last_error = f"SetWindowsHookExW: {exc} — usando apenas pynput"
            self._installed = False
            self._running = False
            return
        if not self._hook_id:
            self.last_error = "SetWindowsHookExW falhou — usando apenas pynput"
            self._installed = False
            self._running = False
            return

        self._installed = True
        msg = wintypes.MSG()
        while self._running:
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.01)

        if self._hook_id:
            user32.UnhookWindowsHookEx(self._hook_id)
            self._hook_id = None
        self._installed = False
        if _active_hook is self:
            _active_hook = None

    def _hook_callback(self, n_code, w_param, l_param):
        if n_code >= 0 and self._running and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
            kb = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = kb.vkCode
            if vk in _ALT_ONLY_VKS:
                return user32.CallNextHookEx(self._hook_id, n_code, w_param, l_param)

            alt_down = bool(kb.flags & LLKHF_ALTDOWN)
            type_key = None

            if alt_down and 0x41 <= vk <= 0x5A:
                type_key = f"%{chr(vk).lower()}"
            elif alt_down and 0x61 <= vk <= 0x7A:
                type_key = f"%{chr(vk).lower()}"
            elif not alt_down or vk in (VK_LEFT, VK_RIGHT, VK_UP, VK_DOWN, VK_RETURN):
                type_key = _vk_to_type_keys(vk)

            if type_key and self._should_emit(type_key):
                try:
                    self._on_special_key(type_key)
                except Exception:
                    pass

        return user32.CallNextHookEx(self._hook_id, n_code, w_param, l_param)

    def _should_emit(self, type_key: str) -> bool:
        now = time.time()
        if self._last_sig == type_key and (now - self._last_time) < _DEBOUNCE_SEC:
            return False
        self._last_sig = type_key
        self._last_time = now
        return True
