"""
core/recorder/action_detector.py
Detecta cliques e digitacao em tempo real (pynput + hook Win32).
Acoes sao enfileiradas para consumo thread-safe pela UI Tkinter.
"""

from __future__ import annotations

import os
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

try:
    import pythoncom
    PYTHONCOM_AVAILABLE = True
except ImportError:
    PYTHONCOM_AVAILABLE = False

from core.recorder.locator import ElementLocator, ElementInfo

try:
    from core.recorder.win32_keyboard_hook import Win32KeyboardHook
    WIN32_HOOK_AVAILABLE = WIN32_AVAILABLE
except ImportError:
    WIN32_HOOK_AVAILABLE = False

KEY_FLUSH_MS = 300
_SPECIAL_DEDUPE_SEC = 0.08
_MENU_CLICK_SUPPRESS_SEC = 0.5

_ALIAS_STOP = object()        # sentinela: encerra o worker de resolução de aliases
_ALIAS_WAIT_SEC = 3.0         # espera máx. do clique pelo cache do módulo ficar pronto

# Diagnóstico do recorder: registra, por clique, o que from_point/foco/handle
# resolveram. Desligado por padrão; ligue com RECORDER_DEBUG=1 para depurar.
_RECORDER_DEBUG = os.environ.get("RECORDER_DEBUG", "0") != "0"
_DEBUG_LOG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "logs", "recorder_debug.log",
)


def _dbg(msg: str) -> None:
    if not _RECORDER_DEBUG:
        return
    try:
        os.makedirs(os.path.dirname(_DEBUG_LOG), exist_ok=True)
        with open(_DEBUG_LOG, "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except Exception:
        pass


@dataclass
class DetectedAction:
    """Uma acao gravada."""
    action_type:   str
    element:       Optional[ElementInfo] = None
    text:          Optional[str] = None
    key:           Optional[str] = None
    process_name:  Optional[str] = None
    window_title:  Optional[str] = None
    assert_kind:   Optional[str] = None   # "visible" | "text" | "value" (action_type=="assert")
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

        if self.action_type == "assert":
            alvo = (self.element.to_autoit_string()
                    if self.element and self.element.is_resolved() else "elemento")
            if self.assert_kind == "visible":
                return f"{prefix}assert visivel: {alvo}"
            return f'{prefix}assert {self.assert_kind}: {alvo} == "{self._escape(self.text or "")}"'

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
        self._armed_assert: Optional[str] = None   # "visible"|"text"|"value" quando armado
        # módulo -> {HWND vivo: alias} (resolução via child_window numa thread dedicada,
        # igual ao editor) e módulo -> {alias: rect} (fallback por posição).
        self._alias_cache: dict[str, dict[int, str]] = {}
        self._rect_cache: dict[str, dict] = {}
        self._aba_rect_cache: dict[str, dict] = {}   # módulo -> {alias: (aba, rect)}
        # worker dedicado (COM próprio) que resolve o alias-map -> {HWND: alias}.
        self._alias_req: queue.Queue = queue.Queue()
        self._alias_evt: dict[str, threading.Event] = {}   # módulo -> pronto
        self._alias_pedidos: set[str] = set()              # módulos já solicitados
        self._alias_worker: Optional[threading.Thread] = None

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
        self._alias_cache = {}   # nova sessão -> HWNDs novos -> recasa o mapa
        self._rect_cache = {}
        self._aba_rect_cache = {}
        self._alias_evt = {}
        self._alias_pedidos = set()
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

        # worker dedicado (COM próprio) que resolve o alias-map ao vivo, igual ao editor.
        self._alias_req = queue.Queue()
        self._alias_worker = threading.Thread(target=self._alias_worker_loop, daemon=True)
        self._alias_worker.start()

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
        if self._alias_worker:
            self._alias_req.put(_ALIAS_STOP)
            self._alias_worker.join(timeout=2)
            self._alias_worker = None

    def is_running(self) -> bool:
        return self._running

    # ── modo "assert" (estilo Playwright: arma o tipo, próximo clique = verificação) ──
    def arm_assertion(self, kind: str) -> None:
        """Arma uma verificação: o PRÓXIMO clique vira um assert (visible/text/value)."""
        self._armed_assert = kind

    def disarm_assertion(self) -> None:
        self._armed_assert = None

    def assertion_armed(self) -> Optional[str]:
        return self._armed_assert

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
        # Carimba JÁ a hora do clique: a resolução roda numa thread que pode
        # bloquear segundos (foco + cache de aliases), então não dá para usar a
        # hora em que a ação termina — senão o clique entra na lista DEPOIS da
        # digitação/Enter que vieram pelo teclado e o codegen perde a ordem.
        clicked_at = time.time()
        threading.Thread(
            target=self._resolve_click, args=(x, y, clicked_at), daemon=True
        ).start()

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

    def _resolve_click(self, x: int, y: int, clicked_at: Optional[float] = None) -> None:
        if clicked_at is None:
            clicked_at = time.time()
        if self._should_suppress_menu_click():
            return

        window, process_name = None, None

        if WIN32_AVAILABLE and PYWINAUTO_AVAILABLE:
            window, process_name = self._resolve_window_by_point(x, y)

        if window is None and WIN32_AVAILABLE and PYWINAUTO_AVAILABLE:
            window, process_name = self._resolve_window_foreground()

        # Ignora cliques fora do Formula Certa (recorder, IDE, explorer, etc.).
        if process_name and not self._eh_fcerta(process_name):
            return

        self._maybe_emit_process_change(process_name)

        info = None
        valor = None
        if window is not None:
            try:
                info, element = self._resolver_elemento_clicado(window, x, y)
                if self._armed_assert and element is not None:
                    valor = self._ler_valor(element)
                self._anexar_alias(window, process_name, info, element, x, y)
            except Exception:
                info = ElementInfo(process_name=process_name, strategy_used="failed")

        resolved = info is not None and info.is_resolved()

        # Modo assert: o clique vira uma verificação, não uma ação.
        kind = self._armed_assert
        if kind:
            self._armed_assert = None
            self._enqueue(DetectedAction(
                action_type="assert", assert_kind=kind, element=info, text=valor,
                process_name=process_name,
                window_title=info.window_title if info else None,
                timestamp=clicked_at, resolved=resolved, _x=x, _y=y,
            ))
            return

        action = DetectedAction(
            action_type="click",
            element=info,
            process_name=process_name,
            window_title=info.window_title if info else None,
            timestamp=clicked_at,
            resolved=resolved,
            _x=x,
            _y=y,
        )
        self._enqueue(action)

    def _resolver_elemento_clicado(self, window, x: int, y: int):
        """Resolve o elemento realmente clicado (ElementInfo, wrapper pywinauto).

        Em forms Delphi densos, `from_point(x, y)` pode cair num CAMPO VIZINHO.
        Após o clique, porém, o campo realmente clicado fica com o foco do teclado
        — essa é a fonte da verdade para Edit/Combo/Memo (igual à digitação).
        Para botões mantemos o `from_point`: nem sempre recebem foco, mas têm
        título único e não se sobrepõem a campos.

        Custo: decide alvo por leitura BARATA do wrapper (class/control_type, sem
        enumerar) e faz NO MÁXIMO UM `resolve()` (que varre descendants). Resolver
        duas vezes deixava o clique lento a ponto de chegar depois do Parar e ser
        descartado pelo `_enqueue` (gravava "0 ações").
        """
        elem_point = None
        try:
            elem_point = window.from_point(x, y)
        except Exception:
            elem_point = None

        # Botão: decide pelo ponto (barato) e nem espera o foco.
        if self._eh_botao_wrapper(elem_point):
            info = self._locator.resolve(window, elem_point)
            self._dbg_click(x, y, elem_point, None, elem_point, info, "botao/point")
            return info, elem_point

        # from_point já é um campo que CONTÉM o ponto -> é o clicado (rápido, sem foco).
        if self._eh_campo_wrapper(elem_point) and self._ponto_dentro(elem_point, x, y):
            info = self._locator.resolve(window, elem_point)
            self._dbg_click(x, y, elem_point, None, elem_point, info, "point/contains")
            return info, elem_point

        # Campo cujo from_point não contém o ponto: tenta o foco (apps onde é impreciso).
        elem_foco = self._ler_foco_estavel(window)
        alvo = self._escolher_alvo(elem_point, elem_foco, x, y)
        if alvo is None:
            self._dbg_click(x, y, elem_point, elem_foco, None, None, "nenhum")
            return ElementInfo(strategy_used="failed"), None
        info = self._locator.resolve(window, alvo)
        origem = "foco" if alvo is elem_foco else "point"
        self._dbg_click(x, y, elem_point, elem_foco, alvo, info, origem)
        return info, alvo

    def _dbg_click(self, x, y, elem_point, elem_foco, alvo, info, origem) -> None:
        if not _RECORDER_DEBUG:
            return
        try:
            linhas = [
                f"CLICK x={x} y={y} origem={origem}",
                f"  point: {self._desc_wrapper(elem_point, x, y)}",
                f"  foco : {self._desc_wrapper(elem_foco, x, y)}",
            ]
            if info is not None:
                linhas.append(
                    f"  alvo -> auto_id={getattr(info, 'automation_id', None)} "
                    f"class={getattr(info, 'class_name', None)} "
                    f"ctype={getattr(info, 'control_type', None)} "
                    f"strat={getattr(info, 'strategy_used', None)}"
                )
            _dbg("\n".join(linhas))
        except Exception:
            pass

    @staticmethod
    def _desc_wrapper(w, x, y) -> str:
        if w is None:
            return "None"
        sig = ActionDetector._wrapper_assinatura(w).strip()
        auto = None
        try:
            auto = w.automation_id()
        except Exception:
            auto = None
        rect = "?"
        try:
            r = w.rectangle()
            rect = f"({r.left},{r.top},{r.right},{r.bottom})"
        except Exception:
            pass
        return f"[{sig}] auto_id={auto} rect={rect} contains={ActionDetector._ponto_dentro(w, x, y)}"

    def _ler_foco_estavel(self, window):
        """Elemento focado depois do clique ter sido processado pelo app.

        O on_click do pynput dispara no mouse-down: quando esta thread roda, o
        Delphi muitas vezes AINDA não moveu o foco. Lê algumas vezes (~0,18 s) e
        fica com a última leitura válida — assim o foco já assentou no campo certo
        (ex.: Filial), em vez do foco antigo (ex.: Complemento)."""
        foco = None
        for espera in (0.06, 0.06, 0.06):
            time.sleep(espera)
            try:
                atual = window.get_focus()
            except Exception:
                atual = None
            if atual is not None:
                foco = atual
        return foco

    @classmethod
    def _escolher_alvo(cls, elem_point, elem_foco, x: int, y: int):
        """Wrapper que representa o clique, usando a GEOMETRIA como verdade.

        O campo clicado é aquele cujo retângulo contém (x, y). Prioriza o foco
        (modo edição: from_point cai no vizinho, mas o foco assenta no campo
        certo); se o foco não contém o ponto (modo consulta: foco fica no campo
        de busca), usa o elemento sob o cursor.
        """
        if cls._eh_botao_wrapper(elem_point):
            return elem_point
        for cand in (elem_foco, elem_point):
            if cls._eh_campo_wrapper(cand) and cls._ponto_dentro(cand, x, y):
                return cand
        return elem_point if elem_point is not None else elem_foco

    @staticmethod
    def _ponto_dentro(wrapper, x: int, y: int) -> bool:
        """True se (x, y) cai dentro do retângulo do wrapper (geometria = verdade)."""
        if wrapper is None:
            return False
        try:
            r = wrapper.rectangle()
            return r.left <= x <= r.right and r.top <= y <= r.bottom
        except Exception:
            return False

    @staticmethod
    def _wrapper_assinatura(element) -> str:
        """class_name + control_type do wrapper — leitura barata, sem enumerar filhos."""
        if element is None:
            return ""
        cls = tipo = ""
        try:
            cls = element.class_name() or ""
        except Exception:
            cls = ""
        try:
            tipo = str(element.element_info.control_type or "")
        except Exception:
            tipo = ""
        return f"{cls} {tipo}".lower()

    @classmethod
    def _eh_botao_wrapper(cls, element) -> bool:
        alvo = cls._wrapper_assinatura(element)
        return any(b in alvo for b in ("button", "bitbtn", "fagronbutton", "speedbutton"))

    @classmethod
    def _eh_campo_wrapper(cls, element) -> bool:
        alvo = cls._wrapper_assinatura(element)
        return any(k in alvo for k in ("edit", "combo", "memo", "spin", "date"))

    # ── casamento do clique ao alias-map (resolução ao vivo, thread dedicada) ──
    def _anexar_alias(self, window, process_name, info, wrapper, x: int, y: int) -> None:
        """Casa o clique a um alias do mapa.

        PRIMÁRIO: aba ativa (ancestrais do elemento clicado) + posição. O `rect` é
        único DENTRO de cada aba, então isso é determinístico e não depende de
        found_index (que reinicia por aba e colidia entre abas) nem de automation_id
        (volátil). FALLBACKS: cache {HWND: alias} resolvido ao vivo e, por fim,
        posição sem filtro de aba (mapas antigos sem `aba`).
        """
        if info is None:
            return
        modulo = self._modulo_do_processo(process_name)
        if not modulo:
            return

        origem = self._origem_janela(window)

        # PRIMÁRIO: aba ativa + posição (rect único por aba).
        if origem is not None:
            aba_ativa = self._aba_do_wrapper(wrapper)
            relx, rely = x - origem[0], y - origem[1]
            alias = self._alias_por_aba_posicao(modulo, aba_ativa, relx, rely)
            if alias:
                info.matched_alias = alias
                try:
                    info.handle = int(wrapper.handle)
                except Exception:
                    pass
                _dbg(f"  match aba={aba_ativa} pos=({relx},{rely}) -> alias={alias}")
                return

        # FALLBACK 1: cache {HWND: alias} resolvido ao vivo pelo worker dedicado.
        self._pedir_cache(modulo)
        h = None
        if wrapper is not None:
            try:
                h = int(wrapper.handle)
            except Exception:
                h = None
        if h:
            evt = self._alias_evt.get(modulo)
            if evt is not None:
                evt.wait(timeout=_ALIAS_WAIT_SEC)   # cobre os primeiros cliques
            alias = self._alias_cache.get(modulo, {}).get(h)
            if alias:
                info.handle = h
                info.matched_alias = alias
                _dbg(f"  match handle={h} -> alias={alias}")
                return

        # FALLBACK 2: posição sem filtro de aba (mapas antigos, sem `aba`).
        if origem is not None:
            relx, rely = x - origem[0], y - origem[1]
            alias = self._alias_em_posicao(modulo, relx, rely)
            if alias:
                info.matched_alias = alias
                _dbg(f"  match pos rel=({relx},{rely}) -> alias={alias}")
                return
        _dbg(f"  match: handle={h} sem alias (cache pronto={modulo in self._alias_cache})")

    def _aba_do_wrapper(self, wrapper) -> list[str]:
        """Caminho de abas (externa->interna) do elemento clicado, subindo pelos
        ancestrais até achar TcxTabSheet(s). Como só dá para clicar no que está
        visível, esse caminho é a aba ATIVA naquele ponto da tela."""
        path: list[str] = []
        cur = wrapper
        for _ in range(40):  # teto de segurança contra ciclos
            if cur is None:
                break
            try:
                cls = cur.class_name() or ""
            except Exception:
                cls = ""
            if cls == "TcxTabSheet":
                try:
                    titulo = (cur.window_text() or "").strip()
                except Exception:
                    titulo = ""
                if titulo:
                    path.append(titulo)
            try:
                cur = cur.parent()
            except Exception:
                break
        path.reverse()  # da aba externa para a interna
        return path

    @staticmethod
    def _aba_compativel(aba_json, aba_ativa: list[str]) -> bool:
        """True se o alias (com `aba` do mapa) pode casar com a aba ativa ao vivo.

        - alias sem aba (None/[]) = controle de janela -> só casa clique FORA de aba.
        - alias com aba = casa quando seu caminho é prefixo do caminho ativo (cobre
          campo na aba externa quando uma sub-aba está aberta)."""
        if not aba_json:
            return not aba_ativa
        a = list(aba_json)
        return a == aba_ativa[: len(a)]

    def _alias_por_aba_posicao(
        self, modulo: str, aba_ativa: list[str], relx: int, rely: int
    ) -> Optional[str]:
        """Alias cujo `rect` contém (relx, rely) ENTRE os da aba ativa (menor área
        vence em empate). Determinístico: cada campo tem posição única na sua aba."""
        melhor: Optional[str] = None
        melhor_area: Optional[int] = None
        for alias, (aba, rect) in self._mapa_aba_rect(modulo).items():
            if not self._aba_compativel(aba, aba_ativa):
                continue
            left, top, right, bottom = rect
            if left <= relx <= right and top <= rely <= bottom:
                area = max(1, right - left) * max(1, bottom - top)
                if melhor_area is None or area < melhor_area:
                    melhor, melhor_area = alias, area
        return melhor

    def _mapa_aba_rect(self, modulo: str) -> dict:
        """{alias: (aba|None, [l,t,r,b])} do módulo. Cache próprio."""
        cache = self._aba_rect_cache.get(modulo)
        if cache is not None:
            return cache
        cache = {}
        try:
            from fc import mapping_store
            mapa = mapping_store.carregar_modulo(modulo)
        except Exception:
            mapa = {}
        for alias, info_map in mapa.items():
            rect = info_map.get("rect")
            if isinstance(rect, (list, tuple)) and len(rect) == 4:
                cache[alias] = (info_map.get("aba"), [int(v) for v in rect])
        self._aba_rect_cache[modulo] = cache
        return cache

    def _pedir_cache(self, modulo: str) -> None:
        """Pede ao worker para resolver o alias-map do módulo (uma vez por módulo)."""
        if modulo in self._alias_pedidos:
            return
        self._alias_pedidos.add(modulo)
        self._alias_evt.setdefault(modulo, threading.Event())
        try:
            self._alias_req.put(modulo)
        except Exception:
            pass

    def _alias_worker_loop(self) -> None:
        """Thread única com COM próprio que resolve alias-maps -> {HWND: alias}.

        Espelha o `_hl_worker_loop` do editor: conecta num WindowSpecification (que
        tem child_window, ao contrário do wrapper do from_point) e resolve cada
        alias. Roda fora da thread do clique, então não trava a gravação.
        """
        if PYTHONCOM_AVAILABLE:
            try:
                pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
            except Exception:
                pass
        try:
            while True:
                modulo = self._alias_req.get()
                if modulo is _ALIAS_STOP:
                    break
                if modulo in self._alias_cache:
                    continue
                cache = self._construir_cache(modulo)
                self._alias_cache[modulo] = cache
                evt = self._alias_evt.get(modulo)
                if evt is not None:
                    evt.set()
                _dbg(f"handle-cache[{modulo}]: {len(cache)} aliases resolvidos ao vivo")
        finally:
            if PYTHONCOM_AVAILABLE:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    def _construir_cache(self, modulo: str) -> dict:
        """{HWND vivo: alias} para o módulo — conecta e resolve o mapa inteiro."""
        cache: dict = {}
        win = self._conectar_janela(modulo)
        if win is None:
            return cache
        try:
            from fc import mapping_store
            mapa = mapping_store.carregar_modulo(modulo)
        except Exception:
            mapa = {}
        for alias, info_map in mapa.items():
            wrapper = self._resolver_alias_vivo(win, info_map)
            if wrapper is None:
                continue
            try:
                h = int(wrapper.handle)
            except Exception:
                h = None
            if h:
                cache[h] = alias
        return cache

    @staticmethod
    def _conectar_janela(modulo: str):
        """WindowSpecification do módulo (suporta child_window) — como o editor."""
        try:
            from core.config import carregar_config
            from tools.mapear_janela import _conectar_app, _obter_janela
            proc = modulo if modulo.lower().endswith(".exe") else f"{modulo}.exe"
            cfg = carregar_config()
            app = _conectar_app(processo=proc, exe_path=cfg.get("exe_path", ""), timeout_janela=6)
            return _obter_janela(app, None, 6, proc)
        except Exception as e:  # noqa: BLE001
            _dbg(f"conectar janela [{modulo}] falhou: {e}")
            return None

    @staticmethod
    def _resolver_alias_vivo(win, info_map: dict):
        """Resolve um alias-map -> wrapper via child_window. SEM automation_id
        (volátil; pode colidir com o HWND vivo de outro controle). Prioridade:
        class+title, control_type+title, class+found_index — como o playback."""
        ctype = info_map.get("control_type")
        cls = info_map.get("class_name")
        title = info_map.get("title")
        fi = info_map.get("found_index")
        specs: list[dict] = []
        if cls and title:
            specs.append({"class_name": cls, "title": title})
        if title and ctype and not cls:
            specs.append({"control_type": ctype, "title": title})
        if cls and fi is not None:
            specs.append({"class_name": cls, "found_index": fi})
        for kw in specs:
            try:
                return win.child_window(**kw).wrapper_object()
            except Exception:
                continue
        return None

    def _alias_em_posicao(self, modulo: str, relx: int, rely: int) -> Optional[str]:
        """Fallback: alias cujo `rect` (relativo à janela) contém (relx, rely)."""
        mapa = self._mapa_com_rect(modulo)
        melhor: Optional[str] = None
        melhor_area: Optional[int] = None
        for alias, rect in mapa.items():
            left, top, right, bottom = rect
            if left <= relx <= right and top <= rely <= bottom:
                area = max(1, (right - left)) * max(1, (bottom - top))
                if melhor_area is None or area < melhor_area:
                    melhor, melhor_area = alias, area
        return melhor

    def _mapa_com_rect(self, modulo: str) -> dict:
        """{alias: [l,t,r,b]} do módulo (fallback por posição). Cache separado."""
        cache = self._rect_cache.get(modulo)
        if cache is not None:
            return cache
        cache = {}
        try:
            from fc import mapping_store
            mapa = mapping_store.carregar_modulo(modulo)
        except Exception:
            mapa = {}
        for alias, info_map in mapa.items():
            rect = info_map.get("rect")
            if isinstance(rect, (list, tuple)) and len(rect) == 4:
                cache[alias] = [int(v) for v in rect]
        self._rect_cache[modulo] = cache
        return cache

    @staticmethod
    def _origem_janela(window):
        """Canto (left, top) da janela — mesma origem que o mapeador usa p/ o rect."""
        try:
            r = window.rectangle()
            return int(r.left), int(r.top)
        except Exception:
            return None

    @staticmethod
    def _modulo_do_processo(process_name: Optional[str]) -> Optional[str]:
        """'FCFiliais.exe' -> 'FCFiliais'; None para fcerta/não-FC."""
        if not process_name:
            return None
        base = process_name[:-4] if process_name.lower().endswith(".exe") else process_name
        low = base.lower()
        if low == "fcerta" or not low.startswith("fc"):
            return None
        return base

    @staticmethod
    def _eh_fcerta(process_name: Optional[str]) -> bool:
        """True se o processo é do Formula Certa (fcerta.exe ou módulos FC*.exe)."""
        if not process_name:
            return False
        p = process_name.lower()
        return p.startswith("fc") and p.endswith(".exe")

    @staticmethod
    def _ler_valor(element) -> Optional[str]:
        """Lê o valor/texto atual do elemento (para o assert de text/value)."""
        for getter in ("get_value", "window_text"):
            try:
                v = getattr(element, getter)()
                if v not in (None, ""):
                    return str(v).strip()
            except Exception:
                continue
        try:
            v = element.legacy_properties().get("Value")
            return str(v).strip() if v else None
        except Exception:
            return None

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
            # adianta a resolução do alias-map assim que o módulo FC aparece.
            modulo = self._modulo_do_processo(process_name)
            if modulo:
                self._pedir_cache(modulo)

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
                # O alias da digitação vem do merge com o clique anterior (que já
                # casou por posição). Aqui só anexa o contexto de janela/processo.
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
        # Ignora digitação fora do Formula Certa (ex.: campo "Nome" do recorder).
        if action.process_name and not self._eh_fcerta(action.process_name):
            return
        if action.element and action.element.is_resolved():
            action.resolved = True
        self._enqueue(action)

    def _enqueue(self, action: DetectedAction) -> None:
        # Não descarta ao parar: um clique em campo leva ~0,18 s para resolver
        # (espera o foco assentar) e pode terminar logo depois do Parar — fica na
        # fila para o drain final. start() limpa a fila, então não vaza p/ a sessão seguinte.
        self._last_action_time = action.timestamp
        self._last_action_type = action.action_type
        try:
            self._queue.put(action)
            if self._running and self._callback:
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
