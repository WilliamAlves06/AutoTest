# teste_gravado.py
# Gerado automaticamente pelo Recorder em 2026-06-01 12:02
import sys
import time
from pathlib import Path
from pywinauto import Application
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.config import LOGIN, SENHA, EXE_PATH
from core.logging_setup import setup_logging
from core.login_flow import login_ou_obter_principal
from core.actions import (
    wait_element,
    wait_app_by_exe,
    safe_click,
    safe_type,
    screenshot_on_failure,
)


def etapa_conectar_ou_iniciar() -> Application:
    """Conecta ao processo em execucao ou inicia pelo caminho do exe."""
    try:
        app = Application(backend="uia").connect(path=EXE_PATH, timeout=3)
        logger.info("Conectado ao sistema ja aberto.")
        return app
    except Exception:
        logger.info("Sistema nao estava aberto — iniciando...")
        return Application(backend="uia").start(EXE_PATH)


def etapa_abrir_menu_gravado_1(main):
    """Abrir menu por teclado."""
    win = main
    logger.info("Abrindo menu Arquivo (ALT+A)...")
    win.set_focus()
    time.sleep(0.3)
    win.type_keys("%a")
    time.sleep(0.4)
    win.type_keys("{DOWN}{DOWN}{ENTER}")

def etapa_interagir_gravado_2(main):
    """Interagir com controles (FCProdutos.exe)"""
    logger.info("Aguardando processo FCProdutos.exe...")
    app_sub = wait_app_by_exe("FCProdutos.exe", timeout=20)
    time.sleep(0.3)
    win = app_sub.top_window()
    logger.info(f"Janela capturada: '{win.window_text()}'")
    win.set_focus()
    time.sleep(0.2)




def run():
    setup_logging(log_name="teste_gravado", json_output=True)
    logger.info("=" * 65)
    logger.info("INICIO DO FLUXO — Teste_Gravado")
    logger.info("=" * 65)

    try:
        logger.info("Etapa 1: Conectando ao sistema...")
        app = etapa_conectar_ou_iniciar()

        logger.info("Etapa 2: Autenticando...")
        main = login_ou_obter_principal(app, LOGIN, SENHA)
        main.set_focus()

        logger.info("Etapa 3: Abrir menu por teclado")
        etapa_abrir_menu_gravado_1(main)
        logger.info("Etapa 4: Interagir com controles (FCProdutos.exe)")
        etapa_interagir_gravado_2(main)
        

        logger.success("FLUXO FINALIZADO COM SUCESSO.")
        return 0

    except Exception as e:
        import traceback
        logger.error(f"FALHA NO FLUXO: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        screenshot_on_failure("falha_teste_gravado")
        return 1


if __name__ == "__main__":
    sys.exit(run())
