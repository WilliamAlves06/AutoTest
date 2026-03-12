import sys
import time
from pathlib import Path
from pywinauto import Application
from loguru import logger
 
# Adiciona raiz no path para imports relativos funcionarem
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
 
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

# ─────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────

EXE_PATH   = r"C:\Fcerta\fcerta.exe"
WIN_LOGIN  = "FórmulaCerta Autenticação de Usuário"
USUARIO    = "FAGRONTECH"
SENHA      = "123"

# ─────────────────────────────────────────
# ETAPAS DO FLUXO
# ─────────────────────────────────────────

def etapa_conectar_ou_iniciar() -> Application:
    """Conecta ao processo em execução ou inicia um novo."""
    try:
        app = Application(backend="uia").connect(path=EXE_PATH, timeout=3)
        logger.info("Conectado ao sistema já aberto.")
        return app
    except Exception:
        logger.info("Sistema não estava aberto — iniciando...")
        app = Application(backend="uia").start(EXE_PATH)
        return app

def etapa_login(app: Application):
    """Aguarda tela de login, preenche usuário e senha."""
    logger.info("Aguardando tela de login...")
    login = wait_window_exact(app, WIN_LOGIN, timeout=25, label="Login")
    login.set_focus()
 
    # Pywinauto navega por Tab/Enter na maioria dos formulários Delphi/VCL
    safe_type(login, USUARIO, label="usuário")
    login.type_keys("{ENTER}")
 
    safe_type(login, SENHA, label="senha")
    login.type_keys("{ENTER}{ENTER}")
    logger.success("Login enviado.")

def etapa_abrir_menu_produtos(main) -> None:
    """Abre menu Arquivo → Produtos via atalho de teclado."""
    logger.info("Abrindo menu Arquivo (ALT+A)...")
    main.set_focus()
    time.sleep(0.3)  # foco precisa estabilizar antes do ALT
    main.type_keys("%a")   # ALT + A
 
    # Aguarda menu aparecer antes de navegar
    time.sleep(0.4)
    main.type_keys("{DOWN}{DOWN}{ENTER}")
    logger.info("Menu Produtos acionado.")

def etapa_preencher_produtos() -> None:
    logger.info("Aguardando processo FCProdutos.exe...")
    app_produtos = wait_app_by_exe("FCProdutos.exe", timeout=20)

    time.sleep(0.3)
    produtos = app_produtos.top_window()
    logger.info(f"Janela capturada: '{produtos.window_text()}'")
    produtos.set_focus()

    campo_codigo = wait_element(
        produtos,
        class_name="TwwDBEdit",
        found_index=0,
        label="Campo Código"
    )

    safe_type(campo_codigo, "38177", label="Código")
    campo_codigo.type_keys("{ENTER}")

    # ── CTRL+TAB (5x) ────────────────────────────────────
    logger.debug("Navegando com CTRL+TAB (5x)...")
    for i in range(5):
        produtos.type_keys("^{TAB}")
        time.sleep(0.15)

    # ── F3 — abre dialog "Produto a alterar" ─────────────
    produtos.type_keys("{F3}")
    logger.info("F3 enviado — aguardando dialog...")
    time.sleep(0.7)

    # Pega a janela do dialog pelo título exato
    dialog = wait_window_exact(app_produtos, "Produto a alterar", timeout=10, label="Dialog Alterar")
    dialog.set_focus()

    # Busca o campo Alterar
    btn_alterar = wait_element(
        app_produtos.top_window(),
        class_name="TFagronButton",
        found_index=1,
        label="Botão Alterar #1",
    )
    safe_click(btn_alterar, label="Botão Alterar #1")
    logger.info("Clicou em sim para Alterar!")
    time.sleep(0.5)

    # Verifica foco
    if not produtos.set_focus():
        logger.warning("Janela perdeu foco — tentando recuperar...")
        produtos.set_focus()
        time.sleep(0.3)
        if not produtos.set_focus():
            raise RuntimeError("Janela Produtos perdeu o foco e não foi possível recuperar.")

    # ── Botão índice 4 ────────────────────────────────────
    botao_5 = wait_element(produtos, class_name="TFagronButton", found_index=4, label="Botão Alterar #2")
    safe_click(botao_5, label="Botão Alterar #2")
    logger.info("Cliclou em Alterar novamente...")
    time.sleep(0.2)

    # ── Campo CBS/IBS ────────────────────────────────
    campo_cbs = wait_element(produtos, class_name="TwwDBComboBox", found_index=2, label="Campo CBS/IBS")
    safe_type(campo_cbs, "011005", label="Campo CBS/IBS")
    campo_cbs.type_keys("{ENTER}")
    logger.info("Selecionou em Campo CBS/IBS novamente...")
    time.sleep(0.2)

    # ── Botão índice 5 ────────────────────────────────────
    botao6 = wait_element(produtos, class_name="TFagronButton", found_index=5, label="Botão Salvar")
    safe_click(botao6, label="Botão Salvar")
    time.sleep(0.4)

    # ── Fechar ────────────────────────────────────────────
    logger.info("Fechando janela Produtos...")
    produtos.close()
    try:
        produtos.wait_not("visible", timeout=10)
    except Exception:
        pass
    logger.success("Janela Produtos fechada.")

# ─────────────────────────────────────────
# ORQUESTRADOR PRINCIPAL
# ─────────────────────────────────────────

def run():
    setup_logging(log_name="produtos_flow", json_output=True)
    logger.info("=" * 50)
    logger.info("INÍCIO DO FLUXO: Produtos")
    logger.info("=" * 50)
 
    try:
        app = etapa_conectar_ou_iniciar()
 
        # Verifica se já está na tela principal ou precisa logar
        try:
            main = wait_window(app, r".*FórmulaCerta.*", timeout=5, label="Principal")
            logger.info("Sistema já autenticado, pulando login.")
        except TimeoutError:
            etapa_login(app)
            main = wait_window(app, r".*FórmulaCerta.*", timeout=20, label="Principal")
 
        etapa_abrir_menu_produtos(main)
        etapa_preencher_produtos()
 
        logger.success("FLUXO FINALIZADO COM SUCESSO.")
        return 0
 
    except Exception as e:
        import traceback
        logger.error(f"FALHA NO FLUXO: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())  # mostra a linha exata
        screenshot_on_failure("falha_geral")
        return 1
 
if __name__ == "__main__":
    sys.exit(run())