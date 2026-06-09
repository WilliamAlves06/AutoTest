"""
fc/context.py
Estado da sessão da DSL: janela principal, módulo ativo e seu alias-map.
"""

from __future__ import annotations

import time

from loguru import logger

import psutil

from core.login_flow import login_ou_obter_principal
from core.actions import wait_app_by_exe
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

    # Acionar item de menu por ÍNDICE (Win32 .select) — livre de resolução, sem texto.
    if s.lower().startswith("@menuitem:"):
        try:
            indices = [int(p) for p in s.split(":", 1)[1].split(",") if p.strip() != ""]
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Passo de menu inválido '{s}': {exc}")
            return
        _selecionar_menu(main, indices)
        logger.info(f"Menu: item {indices} acionado (Win32 .select)")
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
    """Aciona o item de menu pelo caminho de índices (ex.: [1, 4]) via Win32 .select()."""
    from pywinauto import Application

    hwnd = getattr(main, "handle", None) or _achar_main_hwnd()
    if not hwnd:
        raise RuntimeError("Janela principal do Formula Certa não encontrada para o menu.")

    win = Application(backend="win32").connect(handle=hwnd).window(handle=hwnd)
    item = win.menu().item(indices[0])
    for idx in indices[1:]:
        item = item.sub_menu().item(idx)
    item.select()


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

    def reset(self):
        self.__init__()
