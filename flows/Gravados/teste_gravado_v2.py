# teste_gravado_v2.py
# Gerado automaticamente pelo Recorder em 2026-06-01 11:40
import sys
import time
from pathlib import Path
from pywinauto import Application
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.config import LOGIN, SENHA, EXE_PATH
from core.logging_setup import setup_logging
from core.actions import (
    wait_element,
    wait_window,
    wait_app_by_exe,
    wait_window_exact,
    safe_click,
    safe_type,
    screenshot_on_failure,
)

WIN_LOGIN = "FórmulaCerta Autenticação de Usuário"
USUARIO   = LOGIN
SENHA_CFG = SENHA


def etapa_conectar_ou_iniciar() -> Application:
    """Conecta ao processo em execucao ou inicia pelo caminho do exe."""
    try:
        app = Application(backend="uia").connect(path=EXE_PATH, timeout=3)
        logger.info("Conectado ao sistema ja aberto.")
        return app
    except Exception:
        logger.info("Sistema nao estava aberto — iniciando...")
        return Application(backend="uia").start(EXE_PATH)


def etapa_login(app: Application):
    """Aguarda tela de login, preenche usuario e senha."""
    logger.info("Aguardando tela de login...")
    login = wait_window_exact(app, WIN_LOGIN, timeout=25, label="Login")
    login.set_focus()
    safe_type(login, USUARIO, label="usuario")
    login.type_keys("{ENTER}")
    safe_type(login, SENHA_CFG, label="senha")
    login.type_keys("{ENTER}{ENTER}")
    logger.success("Login enviado.")

def etapa_gravada_1(main):
    """Etapa gravada 1: Interagir com controles (fcerta.exe)"""
    win = main
    win.set_focus()
    time.sleep(0.2)


def etapa_gravada_2(main):
    """Etapa gravada 2: Interagir com controles (FCProdutos.exe)"""
    app_sub = wait_app_by_exe("FCProdutos.exe", timeout=20)
    win = app_sub.top_window()
    win.set_focus()
    time.sleep(0.2)

    _el = wait_element(win, class_name="TFagronButton", found_index=15, label="Salvar")
    safe_click(_el, label="Salvar")
    _el = wait_element(win, class_name="TFagronButton", found_index=1, label="Cancelar")
    safe_click(_el, label="Cancelar")
    _el = wait_element(win, class_name="TButton", found_index=1, label="Sim")
    safe_click(_el, label="Sim")


def run():
    setup_logging(log_name="teste_gravado_v2", json_output=True)
    logger.info("=" * 65)
    logger.info("INICIO DO FLUXO — Teste_Gravado v2")
    logger.info("=" * 65)

    try:
        logger.info("Etapa 1: Conectando ao sistema...")
        app = etapa_conectar_ou_iniciar()

        logger.info("Etapa 2: Autenticando...")
        try:
            main = wait_window(app, r".*FórmulaCerta.*", timeout=5, label="Principal")
            logger.info("Sistema ja autenticado.")
        except TimeoutError:
            etapa_login(app)
            main = wait_window(app, r".*FórmulaCerta.*", timeout=20, label="Principal")
            logger.success("Login realizado.")
        main.set_focus()

        logger.info("Etapa 3: Interagir com controles (fcerta.exe)")
        etapa_gravada_1(main)
        logger.info("Etapa 4: Interagir com controles (FCProdutos.exe)")
        etapa_gravada_2(main)

        logger.success("FLUXO FINALIZADO COM SUCESSO.")
        return 0

    except Exception as e:
        import traceback
        logger.error(f"FALHA NO FLUXO: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        screenshot_on_failure("falha_teste_gravado_v2")
        return 1


if __name__ == "__main__":
    sys.exit(run())
