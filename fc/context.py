"""
fc/context.py
Estado da sessão da DSL: janela principal, módulo ativo e seu alias-map.
"""

from __future__ import annotations

import time

import psutil
from loguru import logger

from core.actions import wait_app_by_exe
from core.login_flow import login_ou_obter_principal

from . import mapping_store
from .modules import info_modulo


def _processo_aberto(exe_name: str) -> bool:
    """True se houver um processo com esse nome de executável rodando."""
    alvo = (exe_name or "").lower()
    if not alvo:
        return False
    for proc in psutil.process_iter(["name"]):
        try:
            if (proc.info.get("name") or "").lower() == alvo:
                return True
        except Exception:
            continue
    return False


def _executar_passo_menu(main, passo) -> None:
    """Executa um passo da sequência de abertura: teclas ou clique de mouse.

    - "@click:X,Y"  -> simula um clique de mouse na coordenada (para menus Delphi
      owner-drawn que só aceitam clique, não Enter).
    - qualquer outra string -> enviada como teclas (type_keys), ex.: "%a", "{DOWN 3}".
    """
    s = str(passo).strip()

    # Acionar item de menu por ÍNDICE (clique real calculado) — livre de resolução, sem texto.
    if s.lower().startswith("@menuitem:"):
        try:
            indices = [int(p) for p in s.split(":", 1)[1].split(",") if p.strip() != ""]
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Passo de menu inválido '{s}': {exc}")
            return
        _selecionar_menu(main, indices)
        logger.info(f"Menu: item {indices} acionado (clique real por coordenada calculada)")
        return

    # Clique de mouse por coordenada (fallback).
    if s.lower().startswith("@click:"):
        try:
            x_str, y_str = s.split(":", 1)[1].split(",")
            x, y = int(x_str), int(y_str)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Passo de clique inválido '{s}': {exc}")
            return
        from pywinauto import mouse
        mouse.click(button="left", coords=(x, y))
        logger.info(f"Menu: clique de mouse simulado em ({x}, {y})")
        return

    main.type_keys(s)


def _checar_dialogo_erro(titulo: str = "Atenção!") -> str | None:
    """Verifica rapidamente (sem esperar) se um diálogo de erro do FórmulaCerta
    (ex.: "Atenção! Modulo nao esta cadastrado...") apareceu, fecha-o (clica OK)
    e retorna o texto da mensagem — ou None se não houver diálogo.

    Chamada logo após os passos de menu: sem isso, um menu mal configurado só
    falha 20s depois com um TimeoutError genérico de wait_app_by_exe."""
    try:
        import win32con
        import win32gui
    except Exception:
        return None

    hwnd = win32gui.FindWindow(None, titulo)
    if not hwnd:
        return None

    textos: list[str] = []

    def _coletar(h, _):
        try:
            cls = win32gui.GetClassName(h)
            txt = win32gui.GetWindowText(h)
            if txt and "static" in cls.lower():
                textos.append(txt)
            elif txt and "button" in cls.lower() and txt.strip().lower() in ("ok", "&ok"):
                win32gui.PostMessage(h, win32con.WM_LBUTTONDOWN, 0, 0)
                win32gui.PostMessage(h, win32con.WM_LBUTTONUP, 0, 0)
        except Exception:
            pass
        return True

    try:
        win32gui.EnumChildWindows(hwnd, _coletar, None)
    except Exception:
        pass
    try:
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    except Exception:
        pass
    return " ".join(textos) if textos else "(diálogo de erro sem texto legível)"


def _achar_main_hwnd() -> int | None:
    """Localiza o HWND da janela principal do Formula Certa (a que tem menu)."""
    try:
        import win32gui
    except Exception:
        return None
    achados: list[int] = []

    def _cb(h, _):
        try:
            if win32gui.IsWindowVisible(h) and "rmulaCerta" in win32gui.GetWindowText(h):
                if win32gui.GetMenu(h):
                    achados.append(h)
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(_cb, None)
    except Exception:
        pass
    return achados[0] if achados else None


def _selecionar_menu(main, indices: list[int]) -> None:
    """Aciona o item de menu pelo caminho de índices (ex.: [1, 4]) com CLIQUE real
    nas coordenadas do item (calculadas via GetMenuItemRect — livre de resolução,
    sem coordenada fixa).

    Não usa Win32 `.select()`/`WM_COMMAND`: alguns itens do FórmulaCerta (menu
    owner-drawn) validam permissão de módulo de um jeito que só passa com clique
    físico — `.select()` e `{ENTER}` caem num caminho que dispara "Modulo nao esta
    cadastrado para esse usuario" mesmo no item certo (índice confirmado correto).
    """
    import ctypes
    import time as _time
    from ctypes import wintypes

    import win32gui
    from pywinauto import mouse

    hwnd = getattr(main, "handle", None) or _achar_main_hwnd()
    if not hwnd:
        raise RuntimeError("Janela principal do Formula Certa não encontrada para o menu.")

    user32 = ctypes.windll.user32

    def _centro(hmenu, idx) -> tuple[int, int]:
        rc = wintypes.RECT()
        if not user32.GetMenuItemRect(hwnd, hmenu, idx, ctypes.byref(rc)):
            raise RuntimeError(
                f"GetMenuItemRect falhou para índice {idx} (menu fechado ou índice inválido)."
            )
        return ((rc.left + rc.right) // 2, (rc.top + rc.bottom) // 2)

    hmenu_atual = win32gui.GetMenu(hwnd)
    if not hmenu_atual:
        raise RuntimeError("Janela principal sem menu (GetMenu retornou 0).")

    for nivel, idx in enumerate(indices):
        x, y = _centro(hmenu_atual, idx)
        mouse.click(button="left", coords=(x, y))
        _time.sleep(0.3)
        if nivel < len(indices) - 1:
            hmenu_atual = win32gui.GetSubMenu(hmenu_atual, idx)
            if not hmenu_atual:
                raise RuntimeError(f"Sem submenu sob o índice {idx}.")


def _norm_titulo_aba(s: str) -> str:
    return (s or "").replace("&", "").strip().lower()


def _abas_visiveis(pagecontrol_hwnd: int) -> list[tuple[int, str]]:
    """[(hwnd, título)] dos TcxTabSheet VISÍVEIS (IsWindowVisible) dentro do
    page control — verdade do Win32, não da árvore UIA (que não expõe headers
    para TFagronPageControl/TcxPageControl: são owner-drawn, sem TabItem nem
    SysTabControl32 nativo)."""
    import win32gui

    achados: list[tuple[int, str]] = []

    def _cb(h, _):
        try:
            if win32gui.GetClassName(h) == "TcxTabSheet" and win32gui.IsWindowVisible(h):
                achados.append((h, win32gui.GetWindowText(h)))
        except Exception:
            pass
        return True

    win32gui.EnumChildWindows(pagecontrol_hwnd, _cb, None)
    return achados


def _ciclar_aba_por_titulo(janela, pagecontrol, titulo: str, max_ciclos: int = 12) -> None:
    """Seleciona a aba `titulo` ciclando Ctrl+Tab no page control.

    Esses controles (TFagronPageControl com TcxTabSheet) não expõem o header de
    cada aba como elemento clicável — nem via UIA (sem TabItem) nem via Win32
    (não é um SysTabControl32, é desenhado pelo próprio componente). Sem
    coordenada fixa nem clique, a única forma robusta e livre de resolução é
    ciclar Ctrl+Tab e ler o título do TcxTabSheet que ficou visível
    (win32gui.IsWindowVisible — verificado ao vivo: cada Ctrl+Tab troca a aba
    e o título corresponde exatamente ao nome mostrado na UI).
    """
    alvo = _norm_titulo_aba(titulo)
    pc_hwnd = pagecontrol.handle

    if any(_norm_titulo_aba(t) == alvo for _, t in _abas_visiveis(pc_hwnd)):
        return  # já está na aba certa

    pagecontrol.set_focus()
    for _ in range(max_ciclos):
        janela.type_keys("^{TAB}")
        time.sleep(0.25)
        visiveis = _abas_visiveis(pc_hwnd)
        if any(_norm_titulo_aba(t) == alvo for _, t in visiveis):
            return
    raise RuntimeError(
        f"Aba '{titulo}' não encontrada após {max_ciclos} Ctrl+Tab "
        f"(últimas abas vistas: {[t for _, t in visiveis]})."
    )


def _selecionar_aba(janela, titulos: list[str]) -> None:
    """Seleciona uma aba pelo caminho de títulos (ex.: ["Estoques"]; aninhado:
    ["Livros/Mapas", "Anvisa"] — o de fora primeiro, depois a sub-aba que
    aparece dentro dele). Cada nível corresponde a um PageControl diferente
    (TFagronPageControl/TcxPageControl); todos já existem na árvore da janela
    independente de qual aba está ativa (criados eagerly pelo Delphi)."""
    pagecontrols = [
        c for c in janela.descendants() if "pagecontrol" in (c.class_name() or "").lower()
    ]
    for nivel, titulo in enumerate(titulos):
        if nivel >= len(pagecontrols):
            raise RuntimeError(
                f"Aba: nível {nivel} sem PageControl correspondente "
                f"({len(pagecontrols)} encontrado(s) na janela)."
            )
        _ciclar_aba_por_titulo(janela, pagecontrols[nivel], titulo)


class FCContext:
    def __init__(self):
        self.main = None                # janela principal do FórmulaCerta
        self.modulo: str | None = None  # ex.: "FCReceitas"
        self.app_modulo = None          # pywinauto Application do módulo
        self.janela_modulo = None       # top_window() do módulo
        self.aliases: dict[str, dict] = {}

    # ── login ────────────────────────────────────────────────────
    def login(self):
        logger.info("fc.login() — obtendo janela principal...")
        self.main = login_ou_obter_principal()
        return self.main

    def garantir_main(self):
        if self.main is None:
            self.login()
        return self.main

    # ── abertura de módulo ───────────────────────────────────────
    def open_module(self, nome: str, *, exe: str | None = None,
                    menu: list[str] | None = None, timeout: float = 20.0):
        """Abre o módulo via menu (sem coordenadas) e captura sua janela.

        exe/menu podem ser passados explicitamente; senão são lidos de fc/modules.py.
        """
        cfg = info_modulo(nome) or {}
        exe = exe or cfg.get("exe")
        menu = menu if menu is not None else cfg.get("menu")
        if not exe:
            raise ValueError(f"Módulo '{nome}' sem 'exe' definido (registre em fc/modules.py).")

        main = self.garantir_main()
        if _processo_aberto(exe):
            logger.info(f"{exe} já está aberto — anexando (sem navegar menu).")
        elif menu:
            logger.info(f"Abrindo módulo {nome} via menu {menu}...")
            main.set_focus()
            time.sleep(0.3)
            for passo in menu:
                _executar_passo_menu(main, passo)
                time.sleep(0.4)
            erro = _checar_dialogo_erro()
            if erro:
                raise RuntimeError(
                    f"Diálogo inesperado ao abrir módulo '{nome}' via menu {menu}: {erro}"
                )
        else:
            logger.warning(
                f"{exe} não está aberto e não há menu configurado em fc/modules.py — "
                f"abra o módulo no Fcerta (ou preencha 'menu') antes."
            )

        logger.info(f"Aguardando processo {exe}...")
        self.app_modulo = wait_app_by_exe(exe, timeout=timeout)
        time.sleep(0.3)
        self.janela_modulo = self.app_modulo.top_window()
        self.janela_modulo.set_focus()
        self.modulo = nome[:-4] if nome.lower().endswith(".exe") else nome

        self.aliases = mapping_store.carregar_modulo(self.modulo)
        logger.success(
            f"Módulo {self.modulo} aberto — janela '{self.janela_modulo.window_text()}', "
            f"{len(self.aliases)} aliases carregados."
        )
        return self.janela_modulo

    # ── lookup de alias ──────────────────────────────────────────
    def info_de(self, alias: str) -> dict:
        if alias not in self.aliases:
            raise KeyError(
                f"Alias '{alias}' não existe no módulo '{self.modulo}'. "
                f"Disponíveis: {sorted(self.aliases)}"
            )
        return self.aliases[alias]

    def janela_ativa(self):
        if self.janela_modulo is None:
            raise RuntimeError("Nenhum módulo aberto. Chame fc.open_module(...) antes.")
        return self.janela_modulo

    def focar_modulo(self):
        """Traz a janela do módulo ativo pro foreground (restaura + foco).

        Chamada antes de cada ação: entre passos o FC fica atrás e o Windows
        bloqueia o foco no controle. Robusto e silencioso — devolve a janela."""
        janela = self.janela_ativa()
        try:
            if janela.is_minimized():
                janela.restore()
        except Exception:
            pass
        try:
            janela.set_focus()
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"focar_modulo: set_focus falhou ({exc})")
        return janela

    # ── abas ─────────────────────────────────────────────────────
    def selecionar_aba(self, *titulos: str):
        """Seleciona uma aba do módulo ativo pelo caminho de títulos (ciclando
        Ctrl+Tab — essas abas não têm header clicável). Ex.: selecionar_aba("Estoques");
        aninhado: selecionar_aba("Livros/Mapas", "Anvisa")."""
        janela = self.focar_modulo()
        _selecionar_aba(janela, list(titulos))
        return janela

    def reset(self):
        self.__init__()
