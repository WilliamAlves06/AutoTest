"""
core/recorder/action_detector.py
Detecta cliques e digitacao em tempo real (pynput + hook Win32).
Acoes sao enfileiradas para consumo thread-safe pela UI Tkinter.
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

try:
    import win32gui
    import win32process
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

try:
    from pynput import mouse as pynput_mouse
    from pynput import keyboard as pynput_keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

try:
    from pywinauto import Application
    PYWINAUTO_AVAILABLE = True
except ImportError:
    PYWINAUTO_AVAILABLE = False

from core.recorder.locator import ElementLocator, ElementInfo

try:
    from core.recorder.win32_keyboard_hook import Win32KeyboardHook
    WIN32_HOOK_AVAILABLE = WIN32_AVAILABLE
except ImportError:
    WIN32_HOOK_AVAILABLE = False

KEY_FLUSH_MS = 300
_SPECIAL_DEDUPE_SEC = 0.08
_MENU_CLICK_SUPPRESS_SEC = 0.5


@dataclass
class DetectedAction:
    """Uma acao gravada."""
    action_type:   str
    element:       Optional[ElementInfo] = None
    text:          Optional[str] = None
    key:           Optional[str] = None
    process_name:  Optional[str] = None
    window_title:  Optional[str] = None
    timestamp:     float = field(default_factory=time.time)
    resolved:      bool = True
    _x:            Optional[int] = field(default=None, repr=False)
    _y:            Optional[int] = field(default=None, repr=False)

    def to_display_line(self, index: int) -> str:
        prefix = f"{index:>3}  "

        if self.action_type == "process_changed":
            return f"{prefix}# novo processo: {self.process_name}"

        if self.action_type == "special_key":
            return f'{prefix}win.type_keys("{self.key}")'

        if self.action_type == "type" and self.text:
            if self.element and self.element.is_resolved():
                return (
                    f"{prefix}{self.element.to_autoit_string()}\n"
                    f"      safe_type({self.element.to_wait_element_call()}, "
                    f'"{self._escape(self.text)}")'
                )
            return f'{prefix}win.type_keys("{self._escape(self.text)}")'

        if self.action_type == "click":
            if not self.resolved or self.element is None or not self.element.is_resolved():
                return (
                    f"{prefix}clique ignorado (nao mapeado) — prefira teclado"
                )
            return (
                f"{prefix}{self.element.to_autoit_string()}\n"
                f"      safe_click({self.element.to_wait_element_call()})"
            )

        return f"{prefix}# acao: {self.action_type}"

    @staticmethod
    def _escape(text: str) -> str:
        return text.replace("\\", "\\\\").replace('"', '\\"')


class ActionDetector:
    """Escuta mouse e teclado; enfileira DetectedAction para a UI."""

    def __init__(self):
        self._callback: Optional[Callable[[DetectedAction], None]] = None
        self._running = False
        self._locator = ElementLocator()
        self._queue: queue.Queue[DetectedAction] = queue.Queue()
        self._key_buffer: list[str] = []
        self._key_flush_timer: Optional[threading.Timer] = None
        self._key_lock = threading.Lock()
        self._alt_pressed = False
        self._current_process: Optional[str] = None
        self._last_action_time: float = 0.0
        self._last_action_type: Optional[str] = None
        self._mouse_listener = None
        self._keyboard_listener = None
        self._win32_hook: Optional[Win32KeyboardHook] = None
        self._last_special_key: Optional[str] = None
        self._last_special_time: float = 0.0
        self._hook_ok = False

    def start(self, callback: Optional[Callable[[DetectedAction], None]] = None) -> None:
        if self._running:
            return
        if not PYNPUT_AVAILABLE:
            raise RuntimeError("pynput nao instalado. Execute: pip install pynput==1.7.6")

        self._callback = callback
        self._running = True
        self._key_buffer.clear()
        self._current_process = None
        self._alt_pressed = False
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

        self._mouse_listener = pynput_mouse.Listener(on_click=self._on_click)
        self._keyboard_listener = pynput_keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._mouse_listener.daemon = True
        self._keyboard_listener.daemon = True
        self._mouse_listener.start()
        self._keyboard_listener.start()

        if WIN32_HOOK_AVAILABLE:
            self._win32_hook = Win32KeyboardHook(self._on_win32_special_key)
            self._hook_ok = self._win32_hook.start()

    def stop(self) -> None:
        self._running = False
        self._flush_keys()
        if self._win32_hook:
            self._win32_hook.stop()
            self._win32_hook = None
        if self._mouse_listener:
            self._mouse_listener.stop()
            self._mouse_listener = None
        if self._keyboard_listener:
            self._keyboard_listener.stop()
            self._keyboard_listener = None

    def is_running(self) -> bool:
        return self._running

    def drain_queue(self) -> list[DetectedAction]:
        """Remove e retorna todas as acoes pendentes (chamar na thread do Tk)."""
        items: list[DetectedAction] = []
        while True:
            try:
                items.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return items

    def _on_key_release(self, key):
        if not self._running:
            return
        if not PYNPUT_AVAILABLE:
            return
        if key in (
            pynput_keyboard.Key.alt,
            pynput_keyboard.Key.alt_l,
            pynput_keyboard.Key.alt_r,
        ):
            self._alt_pressed = False

    def _on_click(self, x, y, button, pressed):
        if not self._running or not pressed:
            return
        if button != pynput_mouse.Button.left:
            return
        self._flush_keys()
        threading.Thread(target=self._resolve_click, args=(x, y), daemon=True).start()

    def _on_win32_special_key(self, type_key: str) -> None:
        if self._running:
            self._emit_special_key(type_key)

    def _emit_special_key(self, type_key: str) -> None:
        now = time.time()
        if (
            type_key == self._last_special_key
            and (now - self._last_special_time) < _SPECIAL_DEDUPE_SEC
        ):
            return
        self._last_special_key = type_key
        self._last_special_time = now
        self._alt_pressed = False

        self._flush_keys()
        action = DetectedAction(
            action_type="special_key",
            key=type_key,
            timestamp=now,
        )
        self._enqueue(action)

    def _on_key_press(self, key):
        if not self._running:
            return

        if PYNPUT_AVAILABLE:
            if key in (
                pynput_keyboard.Key.alt,
                pynput_keyboard.Key.alt_l,
                pynput_keyboard.Key.alt_r,
            ):
                self._alt_pressed = True
                return

        try:
            char = key.char
            if char:
                if self._alt_pressed and char.isalpha():
                    self._emit_special_key(f"%{char.lower()}")
                    return
                self._buffer_key(char)
                return
        except AttributeError:
            pass

        self._flush_keys()
        special = self._map_special_key(key)
        if special:
            self._emit_special_key(special)

    def _should_suppress_menu_click(self) -> bool:
        if self._last_action_type != "special_key":
            return False
        return (time.time() - self._last_action_time) < _MENU_CLICK_SUPPRESS_SEC

    def _resolve_click(self, x: int, y: int) -> None:
        if self._should_suppress_menu_click():
            return

        window, process_name = None, None

        if WIN32_AVAILABLE and PYWINAUTO_AVAILABLE:
            window, process_name = self._resolve_window_by_point(x, y)

        if window is None and WIN32_AVAILABLE and PYWINAUTO_AVAILABLE:
            window, process_name = self._resolve_window_foreground()

        self._maybe_emit_process_change(process_name)

        info = None
        if window is not None:
            try:
                element = window.from_point(x, y)
                info = self._locator.resolve(window, element)
            except Exception:
                info = ElementInfo(process_name=process_name, strategy_used="failed")

        resolved = info is not None and info.is_resolved()
        action = DetectedAction(
            action_type="click",
            element=info,
            process_name=process_name,
            window_title=info.window_title if info else None,
            timestamp=time.time(),
            resolved=resolved,
            _x=x,
            _y=y,
        )
        self._enqueue(action)

    def _resolve_window_by_point(self, x: int, y: int):
        try:
            hwnd = win32gui.WindowFromPoint((x, y))
            if not hwnd:
                return None, None
            return self._hwnd_to_window(hwnd)
        except Exception:
            return None, None

    def _resolve_window_foreground(self):
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None, None
            return self._hwnd_to_window(hwnd)
        except Exception:
            return None, None

    def _hwnd_to_window(self, hwnd):
        import psutil
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        app = Application(backend="uia").connect(process=pid, timeout=3)
        window = app.window(handle=hwnd)
        try:
            window = window.top_level_parent()
        except Exception:
            pass
        process_name = psutil.Process(pid).name()
        return window, process_name

    def _maybe_emit_process_change(self, process_name: Optional[str]) -> None:
        if process_name and process_name != self._current_process:
            if self._current_process is not None:
                self._enqueue(DetectedAction(
                    action_type="process_changed",
                    process_name=process_name,
                    timestamp=time.time(),
                ))
            self._current_process = process_name

    def _attach_foreground_context(self, action: DetectedAction) -> None:
        if not (WIN32_AVAILABLE and PYWINAUTO_AVAILABLE):
            return
        try:
            window, process_name = self._resolve_window_foreground()
            if window is None:
                return
            self._maybe_emit_process_change(process_name)
            info = self._locator.resolve_focused(window)
            if info.is_resolved():
                action.element = info
                action.process_name = process_name
                action.window_title = info.window_title
        except Exception:
            pass

    def _buffer_key(self, char: str) -> None:
        with self._key_lock:
            self._key_buffer.append(char)
            if self._key_flush_timer:
                self._key_flush_timer.cancel()
            self._key_flush_timer = threading.Timer(
                KEY_FLUSH_MS / 1000.0, self._flush_keys
            )
            self._key_flush_timer.daemon = True
            self._key_flush_timer.start()

    def _flush_keys(self) -> None:
        with self._key_lock:
            if self._key_flush_timer:
                self._key_flush_timer.cancel()
                self._key_flush_timer = None
            if not self._key_buffer:
                return
            text = "".join(self._key_buffer)
            self._key_buffer.clear()

        action = DetectedAction(
            action_type="type",
            text=text,
            timestamp=time.time(),
        )
        self._attach_foreground_context(action)
        if action.element and action.element.is_resolved():
            action.resolved = True
        self._enqueue(action)

    def _enqueue(self, action: DetectedAction) -> None:
        if not self._running:
            return
        self._last_action_time = action.timestamp
        self._last_action_type = action.action_type
        try:
            self._queue.put(action)
            if self._callback:
                self._callback(action)
        except Exception:
            pass

    @staticmethod
    def _map_special_key(key) -> Optional[str]:
        if not PYNPUT_AVAILABLE:
            return None
        return _PYNPUT_KEY_MAP.get(key)

    @staticmethod
    def _build_pynput_key_map() -> dict:
        K = pynput_keyboard.Key
        pairs = [
            ("enter", "{ENTER}"),
            ("tab", "{TAB}"),
            ("space", " "),
            ("esc", "{ESC}"),
            ("escape", "{ESC}"),
            ("backspace", "{BACKSPACE}"),
            ("delete", "{DELETE}"),
            ("f1", "{F1}"),
            ("f2", "{F2}"),
            ("f3", "{F3}"),
            ("f4", "{F4}"),
            ("f5", "{F5}"),
            ("f6", "{F6}"),
            ("f7", "{F7}"),
            ("f8", "{F8}"),
            ("f9", "{F9}"),
            ("f10", "{F10}"),
            ("f11", "{F11}"),
            ("f12", "{F12}"),
            ("up", "{UP}"),
            ("down", "{DOWN}"),
            ("left", "{LEFT}"),
            ("right", "{RIGHT}"),
            ("page_up", "{PGUP}"),
            ("page_down", "{PGDN}"),
            ("home", "{HOME}"),
            ("end", "{END}"),
        ]
        mapping = {}
        for name, value in pairs:
            attr = getattr(K, name, None)
            if attr is not None:
                mapping[attr] = value
        return mapping


_PYNPUT_KEY_MAP = (
    ActionDetector._build_pynput_key_map()
    if PYNPUT_AVAILABLE
    else {}
)
