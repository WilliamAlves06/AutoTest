"""webapp/mapear_engine.py — varredura de janela, realce on-screen e captura
manual (clique físico -> elemento), sem GUI própria.

Porta a lógica de pages/mapear_ui.py (AliasEditorWindow + _OverlayRealce) para
rodar a partir da web app: o realce continua sendo uma janela real piscando
na tela (o Formula Certa é um app desktop local), só que disparada via HTTP
em vez de um botão Tkinter.
"""

from __future__ import annotations

import json
import re
import threading
import tkinter as tk
import unicodedata
from pathlib import Path
from typing import Callable, Optional

import pythoncom

from tools.mapear_janela import _conectar_app, _obter_janela, mapear_janela, merge_key

_TRANSP = "#00fe01"


def slug_alias(titulo: str) -> str:
    if not titulo:
        return ""
    txt = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode()
    txt = re.sub(r"[^a-zA-Z0-9]+", "_", txt).strip("_").lower()
    return txt[:30]


def _aba_path(el: dict) -> tuple:
    """Caminho de abas do elemento como tupla (chave estavel). () = fora de aba."""
    a = el.get("aba")
    if isinstance(a, list):
        return tuple(a)
    if a:
        return (a,)
    return ()


def _garantir_unicidade(elementos: list[dict]) -> None:
    """Torna unicos os aliases nao-vazios (in-place), preservando a ORDEM.

    A 1a ocorrencia de um nome fica limpa (aba ativa, varrida primeiro); colisoes
    seguintes recebem o prefixo da aba mais interna (ex.: cnpj -> internet_cnpj) e,
    se ainda colidir, um sufixo numerico. Sem isso, aliases iguais em abas
    diferentes seriam colapsados ('ultimo vence') ao carregar o modulo, deixando
    campos inacessiveis."""
    usados: set[str] = set()
    for el in elementos:
        alias = (el.get("alias") or "").strip()
        if not alias:
            continue
        if alias not in usados:
            usados.add(alias)
            el["alias"] = alias
            continue
        ak = _aba_path(el)
        base = f"{slug_alias(ak[-1])}_{alias}" if ak else alias
        cand, i = base, 2
        while cand in usados:
            cand = f"{base}_{i}"
            i += 1
        usados.add(cand)
        el["alias"] = cand


def dedup_elementos(elementos: list[dict]) -> list[dict]:
    vistos: set = set()
    saida: list[dict] = []
    for el in elementos:
        auto_id = (el.get("automation_id") or "").strip()
        if auto_id:
            chave = ("aid", auto_id)
        else:
            chave = (
                "vis", el.get("control_type"), el.get("title"), el.get("class_name"),
                tuple(el.get("rectangle") or ()),
            )
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append(el)
    return saida


def prefill_aliases_do_mapa(elementos: list[dict], modulo: str) -> None:
    """Pré-preenche `el['alias']` a partir do alias-map já curado (in-place)."""
    if not modulo:
        return
    try:
        from fc.mapping_store import carregar_modulo
        curado = carregar_modulo(modulo)
    except Exception:
        return
    # Chaveado pela ABA tambem: o mesmo (class_name, found_index) aparece em toda
    # aba (found_index reinicia por aba na varredura), entao sem a aba na chave um
    # alias curado seria espalhado por todas as abas, apontando campos diferentes.
    por_idx: dict[tuple, str] = {}
    por_titulo: dict[tuple, str] = {}
    for alias, e in curado.items():
        ak = _aba_path(e)
        cls = e.get("class_name") or ""
        fi = e.get("found_index")
        if fi is not None:
            por_idx[(ak, cls, fi)] = alias
        ti, ct = e.get("title"), e.get("control_type")
        if ti and ct:
            por_titulo[(ak, ct, ti)] = alias

    for el in elementos:
        if el.get("alias"):
            continue
        ak = _aba_path(el)
        fi = el.get("found_index")
        cls = el.get("class_name") or ""
        alias = por_idx.get((ak, cls, fi)) if fi is not None else None
        if not alias:
            ti, ct = el.get("title"), el.get("control_type")
            if ti and ct:
                alias = por_titulo.get((ak, ct, ti))
        if alias:
            el["alias"] = alias
        elif el.get("title"):
            el["alias"] = slug_alias(el["title"])

    # Garante aliases unicos por aba (fim do colapso 'ultimo vence' em carregar_modulo).
    _garantir_unicidade(elementos)


def escanear(
    modulo: str,
    exe_path: Optional[str],
    on_progress: Callable[[str], None],
    existing: Optional[list[dict]] = None,
) -> list[dict]:
    """Varre a janela do módulo. Se `existing` for passado, mescla só os
    elementos novos (re-mapear); senão pré-preenche aliases do mapa curado."""
    processo = modulo if modulo.lower().endswith(".exe") else f"{modulo}.exe"
    out_path = mapear_janela(
        None, processo=processo, exe_path=exe_path, timeout_janela=30,
        incluir_ocultos=True, on_progress=on_progress, varrer_todas_abas=True,
    )
    elementos = dedup_elementos(json.loads(Path(out_path).read_text(encoding="utf-8")))

    if existing:
        chaves = {merge_key(el) for el in existing}
        novos = [el for el in elementos if merge_key(el) not in chaves]
        return existing + novos

    prefill_aliases_do_mapa(elementos, modulo)
    return elementos


def escanear_async(
    modulo: str,
    exe_path: Optional[str],
    on_progress: Callable[[str], None],
    on_done: Callable[[list[dict]], None],
    on_error: Callable[[str], None],
    existing: Optional[list[dict]] = None,
) -> None:
    def worker() -> None:
        pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
        try:
            elementos = escanear(modulo, exe_path, on_progress, existing)
            on_done(elementos)
        except Exception as exc:  # noqa: BLE001
            on_error(str(exc))
        finally:
            pythoncom.CoUninitialize()

    threading.Thread(target=worker, daemon=True).start()


# ── realce on-screen (moldura piscante) ──────────────────────────
class _Overlay(tk.Toplevel):
    def __init__(self, root, rect, cor: str = "#ff2d2d", piscadas: int = 3, dur: int = 130):
        super().__init__(root)
        left, top, right, bottom = rect
        w, h = max(2, right - left), max(2, bottom - top)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-transparentcolor", _TRANSP)
        except tk.TclError:
            pass
        self.configure(bg=cor)
        inner = tk.Frame(self, bg=_TRANSP)
        inner.pack(fill="both", expand=True, padx=3, pady=3)
        self.geometry(f"{w + 6}x{h + 6}+{left - 3}+{top - 3}")
        self._restantes = piscadas * 2
        self._dur = dur
        self._piscar()

    def _piscar(self) -> None:
        if not self.winfo_exists():
            return
        if self._restantes <= 0:
            self.destroy()
            return
        if self.state() == "withdrawn":
            self.deiconify()
        else:
            self.withdraw()
        self._restantes -= 1
        self.after(self._dur, self._piscar)


class _OverlayOwner:
    """Thread dedicada com um Tk() escondido + mainloop próprio — a web app não
    tem nenhuma janela tk "principal" para hospedar o realce."""

    def __init__(self) -> None:
        self._root: Optional[tk.Tk] = None
        self._ready = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()
        self._ready.wait(timeout=5)

    def _run(self) -> None:
        self._root = tk.Tk()
        self._root.withdraw()
        self._ready.set()
        self._root.mainloop()

    def flash(self, rect: list[int]) -> None:
        if self._root is None:
            return
        try:
            self._root.after(0, lambda: _Overlay(self._root, rect))
        except Exception:
            pass


_overlay_owner: Optional[_OverlayOwner] = None


def _owner() -> _OverlayOwner:
    global _overlay_owner
    if _overlay_owner is None:
        _overlay_owner = _OverlayOwner()
    return _overlay_owner


def _hl_fast_resolve(win, el: dict):
    auto_id = el.get("automation_id")
    ctype = el.get("control_type") or None
    cls = el.get("class_name")
    title = el.get("title")
    fi = el.get("found_index")

    specs: list[dict] = []
    if auto_id:
        kw = {"auto_id": str(auto_id)}
        if ctype:
            kw["control_type"] = ctype
        specs.append(kw)
    if cls and title:
        specs.append({"class_name": cls, "title": title})
    if title and ctype and not cls:
        specs.append({"control_type": ctype, "title": title})
    if cls and fi is not None:
        specs.append({"class_name": cls, "found_index": fi})

    ultimo = None
    for kw in specs:
        try:
            return win.child_window(**kw).wrapper_object()
        except Exception as exc:  # noqa: BLE001
            ultimo = exc
    raise ultimo or RuntimeError("nenhuma estratégia de localização")


class ScanSession:
    """Conexão (app/janela) cacheada por módulo — evita reconectar a cada
    clique de realce/captura."""

    def __init__(self, processo: str, exe_path: Optional[str] = None) -> None:
        self.processo = processo
        self.exe_path = exe_path
        self.app = None
        self.win = None
        self._lock = threading.Lock()

    def _connect(self) -> None:
        self.app = _conectar_app(processo=self.processo, exe_path=self.exe_path or "", timeout_janela=8)
        self.win = _obter_janela(self.app, None, 8, self.processo)

    def resolver_rect(self, el: dict) -> Optional[list[int]]:
        with self._lock:
            for _ in (1, 2):
                try:
                    if self.win is None:
                        self._connect()
                    w = _hl_fast_resolve(self.win, el)
                    r = w.rectangle()
                    return [r.left, r.top, r.right, r.bottom]
                except Exception:
                    self.app = None
                    self.win = None
            return None

    def capturar(self, x: int, y: int) -> Optional[dict]:
        try:
            from pywinauto import Desktop
            from core.recorder.locator import ElementLocator

            elem = Desktop(backend="uia").from_point(int(x), int(y))
            top = elem.top_level_parent()
            loc = ElementLocator().resolve(top, elem)
            r = elem.rectangle()

            def _s(fn):
                try:
                    v = fn()
                    return (v or "").strip() if isinstance(v, str) else v
                except Exception:
                    return None

            return {
                "alias": "",
                "automation_id": loc.automation_id or _s(elem.automation_id) or "",
                "class_name": loc.class_name or _s(elem.class_name) or "",
                "title": loc.title or _s(elem.window_text) or "",
                "control_type": loc.control_type or str(elem.element_info.control_type),
                "found_index": loc.found_index,
                "instance": loc.instance,
                "rectangle": [r.left, r.top, r.right, r.bottom],
            }
        except Exception:
            return None


_sessions: dict[str, ScanSession] = {}


def get_session(processo: str, exe_path: Optional[str] = None) -> ScanSession:
    sess = _sessions.get(processo)
    if sess is None:
        sess = ScanSession(processo, exe_path)
        _sessions[processo] = sess
    return sess


def pedir_realce(modulo: str, el: dict, exe_path: Optional[str] = None) -> None:
    processo = modulo if modulo.lower().endswith(".exe") else f"{modulo}.exe"

    def worker() -> None:
        pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
        try:
            rect = get_session(processo, exe_path).resolver_rect(el)
            if rect:
                _owner().flash(rect)
        finally:
            pythoncom.CoUninitialize()

    threading.Thread(target=worker, daemon=True).start()


class CaptureRecorder:
    """Listener global de clique: ao capturar, resolve o elemento sob o
    cursor e devolve via callback (a confirmação/alias fica a cargo da UI)."""

    def __init__(self) -> None:
        self._on = False
        self._busy = False
        self._listener = None

    def is_running(self) -> bool:
        return self._on

    def start(self, modulo: str, exe_path: Optional[str], on_capture: Callable[[dict], None]) -> None:
        if self._on:
            return
        from pynput import mouse

        processo = modulo if modulo.lower().endswith(".exe") else f"{modulo}.exe"
        sess = get_session(processo, exe_path)
        self._on = True
        self._busy = False

        def on_click(x, y, button, pressed) -> None:
            if not pressed or not self._on or self._busy:
                return
            try:
                from pynput.mouse import Button
                if button != Button.left:
                    return
            except Exception:
                pass
            self._busy = True

            def worker() -> None:
                pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
                try:
                    info = sess.capturar(int(x), int(y))
                finally:
                    pythoncom.CoUninitialize()
                    self._busy = False
                if info:
                    on_capture(info)

            threading.Thread(target=worker, daemon=True).start()

        self._listener = mouse.Listener(on_click=on_click)
        self._listener.start()

    def stop(self) -> None:
        self._on = False
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
