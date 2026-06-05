# core/login_flow.py
from __future__ import annotations

import time

from loguru import logger
from pywinauto import Application
from pywinauto.keyboard import send_keys

from core.config import carregar_config
from core.actions import (
    aguardar_login_ou_none,
    obter_janela_login_visivel,
    obter_janela_principal_habilitada,
    safe_press_keys,
    safe_type,
    wait_element,
    wait_main_window,
    wait_window_exact,
)

WIN_LOGIN = "FórmulaCerta Autenticação de Usuário"


def focar_janela_login(login) -> None:
    """Traz a tela de autenticacao para o primeiro plano."""
    login.set_focus()
    try:
        import win32gui
        hwnd = login.handle
        win32gui.SetForegroundWindow(hwnd)
    except Exception as exc:
        logger.debug(f"SetForegroundWindow indisponivel: {exc}")
    time.sleep(0.3)


def focar_campo(campo) -> None:
    """Foca e clica no controle TwwDBEdit."""
    campo.set_focus()
    try:
        campo.click_input()
    except Exception:
        pass
    time.sleep(0.15)


def _tentar_login_por_campos(login, usuario: str, senha: str, timeout: float = 5) -> bool:
    """Tenta login nos TwwDBEdit (INSTANCE 3/4). Retorna True se concluir."""
    try:
        campo_user = wait_element(
            login, class_name="TwwDBEdit", found_index=2, timeout=timeout, label="usuario"
        )
        focar_campo(campo_user)
        safe_type(campo_user, usuario, label="usuario")
        safe_press_keys(campo_user, "{ENTER}", label="usuario_enter")

        campo_senha = wait_element(
            login, class_name="TwwDBEdit", found_index=3, timeout=timeout, label="senha"
        )
        focar_campo(campo_senha)
        safe_type(campo_senha, senha, label="senha")
        safe_press_keys(campo_senha, "{ENTER}{ENTER}", label="senha_confirmar")
        return True
    except TimeoutError:
        return False


def _etapa_login_janela(login, usuario: str, senha: str) -> None:
    """
    Fluxo simples na janela de login (padrao CT-168635).
    Senha via send_keys no controle focado apos ENTER no usuario.
    """
    focar_janela_login(login)
    safe_type(login, usuario, label="usuario")
    login.type_keys("{ENTER}")
    time.sleep(0.3)
    logger.info("Digitando senha no controle focado")
    send_keys(senha, with_spaces=True)
    time.sleep(0.15)
    login.type_keys("{ENTER}{ENTER}")


def etapa_login(app: Application, usuario: str, senha: str) -> None:
    """Aguarda tela de login e preenche usuario/senha."""
    logger.info("Aguardando tela de login...")
    login = wait_window_exact(app, WIN_LOGIN, timeout=25, label="Login")
    focar_janela_login(login)

    if _tentar_login_por_campos(login, usuario, senha, timeout=5):
        logger.success("Login enviado.")
        return

    logger.info("Campos TwwDBEdit indisponiveis — fluxo na janela de login")
    _etapa_login_janela(login, usuario, senha)
    logger.success("Login enviado.")


# Alias para codigo que ainda importa realizar_login
realizar_login = etapa_login


def obter_janela_principal(app: Application):
    """Retorna a janela principal habilitada, se existir."""
    return obter_janela_principal_habilitada(app)


def login_ou_obter_principal(
    timeout_principal: float = 30,
    timeout_aguardar_login: float = 15,
) -> object:
    """
    Conecta ou inicia o Fcerta, faz login se necessario
    e retorna o handle da janela principal pronta pra uso.
    Credenciais e exe_path lidos automaticamente do config.json.
    """
    cfg = carregar_config()
    exe_path = cfg.get("exe_path", r"C:\Fcerta\fcerta.exe")
    usuario  = cfg.get("login", "")
    senha    = cfg.get("senha", "")

    # ── conectar ou iniciar ──────────────────────────────────
    try:
        app = Application(backend="uia").connect(path=exe_path, timeout=3)
        logger.info("Conectado ao sistema ja aberto.")
    except Exception:
        logger.info("Iniciando Fcerta...")
        app = Application(backend="uia").start(exe_path)

    # ── login se necessario ──────────────────────────────────
    if obter_janela_login_visivel(app) is not None:
        logger.info("Tela de login aberta — realizando autenticacao.")
        etapa_login(app, usuario, senha)
        time.sleep(0.5)
        return wait_main_window(app, timeout=timeout_principal, label="Principal")

    main = obter_janela_principal_habilitada(app)
    if main is not None:
        logger.info("Sistema ja autenticado.")
        return main

    login = aguardar_login_ou_none(app, timeout=timeout_aguardar_login)
    if login is not None:
        logger.info("Tela de login detectada apos aguardar — realizando autenticacao.")
        etapa_login(app, usuario, senha)
        time.sleep(0.5)
        return wait_main_window(app, timeout=timeout_principal, label="Principal")

    main = obter_janela_principal_habilitada(app)
    if main is not None:
        logger.info("Sistema ja autenticado.")
        return main

    logger.info("Principal nao detectada — tentando login.")
    etapa_login(app, usuario, senha)
    time.sleep(0.5)
    return wait_main_window(app, timeout=timeout_principal, label="Principal")