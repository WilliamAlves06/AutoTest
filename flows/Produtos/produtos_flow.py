import sys
import time

from pywinauto import Application

from autotest import *
from core.actions import wait_element, wait_window, wait_app_by_exe, safe_click, safe_type
from data import produtos as dados

# ========================= CONFIGURAÇÕES =========================
# Códigos do cenário em data/produtos.py. (Login deste fluxo usa o usuário
# SUPERVISOR — confirmar se é intencional; senão migrar para core.config.)
EXE_PATH   = r"C:\Fcerta\fcerta.exe"
USUARIO    = "SUPERVISOR"
SENHA      = "321"


# ========================= FUNÇÕES =========================
def etapa_conectar_ou_iniciar() -> Application:
    try:
        app = Application(backend="uia").connect(path=EXE_PATH, timeout=3)
        logger.info("Conectado ao sistema já aberto.")
        return app
    except Exception:
        logger.info("Sistema não estava aberto — iniciando...")
        return Application(backend="uia").start(EXE_PATH)


def etapa_login_e_detectar_main(app: Application):
    """
    Detecta se precisa logar e garante retorno da janela principal.
    """
    logger.info("Detectando estado do sistema...")

    time.sleep(5)  # tempo pro sistema abrir

    login_win = None
    main = None

    # 🔍 Varre todas as janelas abertas
    for win in app.windows(visible_only=True):
        title = win.window_text()
        logger.info(f"Janela encontrada: '{title}'")

        if "Autenticação" in title:
            login_win = win

        elif "FórmulaCerta" in title:
            main = win

    # 🚨 CASO 1: precisa logar
    if login_win:
        logger.info("Tela de login detectada → fazendo login")

        login_win.set_focus()

        safe_type(login_win, USUARIO)
        time.sleep(0.4)
        login_win.type_keys("{ENTER}")

        safe_type(login_win, SENHA)
        time.sleep(0.4)
        login_win.type_keys("{ENTER}{ENTER}")

        logger.success("Login enviado")

        # Aguarda a principal real
        main = wait_window(app, r".*FórmulaCerta.*", timeout=30)

    # 🚨 CASO 2: já logado
    elif main:
        logger.info("Sistema já autenticado")

    else:
        raise Exception("Nenhuma janela válida encontrada")

    return main


def etapa_abrir_menu_produtos(main):
  
    main.set_focus()
    time.sleep(0.3)
    main.type_keys("%a")
    time.sleep(0.4)
    main.type_keys("{DOWN}{DOWN}{ENTER}")
    logger.info("Módulo Produtos acionado.")


def etapa_preencher_produtos():
    logger.info("Aguardando processo FCProdutos.exe...")
    app_prod = wait_app_by_exe("FCProdutos.exe", timeout=20)
    time.sleep(0.3)
    prod = app_prod.top_window()
    prod.set_focus()
    campo_codigo = wait_element(prod, class_name="TwwDBEdit", found_index=0, timeout=10)
    safe_type(campo_codigo, dados.CODIGO)
    campo_codigo.type_keys("{ENTER}")

    # Navegação
    logger.info("Navegando com CTRL + TAB (5x)...")
    for _ in range(5):
        prod.type_keys("^{TAB}")
    time.sleep(0.3)

    # F3
    prod.type_keys("{F3}")
    wait_window(app_prod, r".*Produto a alterar.*", timeout=10)

    # Botões alterar
    btn1 = wait_element(app_prod.top_window(), class_name="TFagronButton", found_index=1, timeout=10)
    safe_click(btn1)

    time.sleep(0.1)

    btn2 = wait_element(prod, class_name="TFagronButton", found_index=4, timeout=3)
    safe_click(btn2)

    # Campo CBS/IBS
    campo_cbs = wait_element(prod, class_name="TwwDBComboBox", found_index=2, timeout=3)
    safe_type(campo_cbs, dados.CBS_IBS)
    campo_cbs.type_keys("{ENTER}")

    # Salvar
    btn_salvar = wait_element(prod, class_name="TFagronButton", found_index=5, timeout=3)
    safe_click(btn_salvar)

    logger.success("Alteração salva com sucesso")

    # Fechar
    prod.close()
    prod.wait_not("visible", timeout=10)


# ========================= EXECUÇÃO =========================
def run():
    setup_logging(log_name="produtos_flow", json_output=True)
    logger.info("=" * 65)
    logger.info("INÍCIO DO FLUXO - PRODUTOS")
    logger.info("=" * 65)

    try:
        app = etapa_conectar_ou_iniciar()

        # 🔥 NOVA LÓGICA (resolve teu problema)
        main = etapa_login_e_detectar_main(app)
        main.set_focus()

        etapa_abrir_menu_produtos(main)
        etapa_preencher_produtos()

        logger.success("FLUXO FINALIZADO COM SUCESSO.")
        return 0

    except Exception as e:
        import traceback
        logger.error(f"FALHA NO FLUXO: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        screenshot_on_failure("falha_produtos")
        return 1


if __name__ == "__main__":
    sys.exit(run())