import sys
import time
import pytest
from pathlib import Path
from pywinauto import Application
from loguru import logger
import fdb

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
from core.reporter import imprimir_inicio, imprimir_etapa, imprimir_resultado

# ─────────────────────────────────────────
# CONFIGURAÇÃO — SISTEMA
# ─────────────────────────────────────────
EXE_PATH  = r"C:\Fcerta\fcerta.exe"
WIN_LOGIN = "FórmulaCerta Autenticação de Usuário"
USUARIO   = "FAGRONTECH"
SENHA     = "321"

# ─────────────────────────────────────────
# CONFIGURAÇÃO — Receita
# ─────────────────────────────────────────
NUMERO_NOTA    = "8484"
CDPRO_ESPERADO = "51639"
NRLOT_ESPERADO = "123"

# ─────────────────────────────────────────
# CONFIGURAÇÃO — BANCO
# ─────────────────────────────────────────
DB_CONFIG = {
    "host":     "localhost",
    "database": r"C:\bancoDeDados\NFCE-205607\alterdb.ib",
    "user":     "SYSDBA",
    "password": "masterkey",
}

# ─────────────────────────────────────────
# VARIÁVEIS GLOBAIS PARA RASTREAMENTO
# ─────────────────────────────────────────
alerta_exibido = False
alerta_texto = ""

# ─────────────────────────────────────────
# FIXTURES PYTEST
# ─────────────────────────────────────────
@pytest.fixture(scope="module")
def db_cursor():
    conn = fdb.connect(
        host=DB_CONFIG["host"],
        database=DB_CONFIG["database"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )
    cur = conn.cursor()
    yield cur
    cur.close()
    conn.close()

@pytest.fixture(scope="module", autouse=True)
def executar_fluxo():
    """Roda o fluxo completo antes dos testes do módulo."""
    setup_logging(log_name="Receitas_flow_test", json_output=True)
    
    logger.info("=" * 60)
    logger.info("🚀 INICIANDO FLUXO DE TESTES: RECEITAS")
    logger.info("=" * 60)

    logger.info("📍 Etapa 1: Conectando ao sistema...")
    app = etapa_conectar_ou_iniciar()

    try:
        logger.info("📍 Etapa 2: Verificando autenticação...")
        main = wait_window(app, r".*FórmulaCerta.*", timeout=5, label="Principal")
        logger.info("✓ Já autenticado, pulando login.")
    except TimeoutError:
        logger.info("✓ Aguardando tela de login...")
        etapa_login(app)
        main = wait_window(app, r".*FórmulaCerta.*", timeout=20, label="Principal")
        logger.success("✓ Login realizado com sucesso")

    logger.info("📍 Etapa 3: Abrindo menu de Receitas...")
    etapa_abrir_menu_receitas(main)
    
    logger.info("📍 Etapa 4: Iniciando fluxo de Receitas...")
    etapa_incluir_receitas()
    
    logger.info("📍 Etapa 5: Preenchendo dados da Receita...")
    etapa_preencher_receita()
    
    logger.info("=" * 60)
    logger.success("🎉 FLUXO CONCLUÍDO COM SUCESSO - Iniciando validações...")
    logger.info("=" * 60)

# ─────────────────────────────────────────
# FLUXO
# ─────────────────────────────────────────
def etapa_conectar_ou_iniciar() -> Application:
    """Conecta ao processo em execução ou inicia um novo."""
    try:
        app = Application(backend="uia").connect(path=EXE_PATH, timeout=3)
        logger.info("Conectado ao sistema já aberto.")
        return app
    except Exception:
        logger.info("Sistema não estava aberto — iniciando...")
        return Application(backend="uia").start(EXE_PATH)

def etapa_login(app: Application):
    """Aguarda tela de login, preenche usuário e senha."""
    logger.info("Aguardando tela de login...")
    login = wait_window_exact(app, WIN_LOGIN, timeout=25, label="Login")
    login.set_focus()
    safe_type(login, USUARIO, label="usuário")
    login.type_keys("{ENTER}")
    safe_type(login, SENHA, label="senha")
    login.type_keys("{ENTER}{ENTER}")
    logger.success("Login enviado.")

def etapa_detectar_e_focar_receitas(app_receitas: Application):
    """Varre janelas abertas e garante foco na janela principal de Receitas."""
    logger.info("Detectando janela de Receitas...")
    time.sleep(2)  # Aguarda sistema ficar pronto
    
    receitas = None
    # Varre todas as janelas visíveis
    for win in app_receitas.windows(visible_only=True):
        title = win.window_text()
        logger.info(f"Janela encontrada: '{title}'")
        if "Receitas" in title or "FórmulaCerta" in title:
            receitas = win
            break
    
    if not receitas:
        receitas = app_receitas.top_window()
    
    # GARANTE FOCO
    receitas.set_focus()
    time.sleep(0.3)
    logger.success("✓ Janela de Receitas focada")
    return receitas

def etapa_abrir_menu_receitas(main) -> None:
    """Abre menu Arquivo → Receitas via atalho de teclado."""
    logger.info("Abrindo menu Arquivo (ALT+A)...")
    main.set_focus()
    time.sleep(0.3)
    main.type_keys("%a")
    time.sleep(0.4)
    main.type_keys("{RIGHT}{RIGHT}{ENTER}")
    logger.info("Módulo Receitas acionado.")

def etapa_incluir_receitas() -> None:
    logger.info("=" * 60)
    logger.info("INICIANDO ETAPA: Incluir Receitas")
    logger.info("=" * 60)
    
    logger.info("📍 [1/6] Aguardando processo FCReceitas.exe...")
    app_receitas = wait_app_by_exe("FCReceitas.exe", timeout=20)
    logger.success("✓ Processo FCReceitas.exe encontrado")

    time.sleep(0.3)
    receitas = app_receitas.top_window()
    logger.info(f"📍 [2/6] Janela capturada: '{receitas.window_text()}'")
    receitas.set_focus()
    logger.info("✓ Foco definido na janela principal")

    # Fechar sub-tela de Histórico do Cliente
    logger.info("📍 [3/6] Tentando fechar sub-tela de Histórico do Cliente...")
    time.sleep(0.5)
    try:
        historico = wait_window(app_receitas, "Histórico do Cliente", timeout=5, label="TfrHistorico")
        historico.set_focus()
        historico.type_keys("%{F4}")  # Alt+F4 para fechar a sub-tela
        logger.success("✓ Sub-tela de Histórico fechada com sucesso")
        time.sleep(0.3)
    except TimeoutError:
        logger.warning("⚠ Sub-tela de Histórico não foi encontrada (timeout)")

    logger.info("📍 [4/6] Abrindo tela de Consulta (F2)...")
    receitas.type_keys("{F2}")
    criacao_req = wait_window(app_receitas, "Requisição", timeout=10, label="TfrVisual")
    logger.success("✓ Tela de Consulta aberta")
    criacao_req.set_focus()
    logger.info("✓ Foco definido na tela de consulta")

    logger.info("📍 [5/6] Procurando botão 'Próxima Requisição'...")
    btn_proximo = wait_element(
        criacao_req,  # Procurar na tela de Requisição, não na janela principal
        title="Próxima",
        class_name="TFagronButton",
        timeout=5,
        label="Botão Próxima Requisição",
    )
    btn_proximo.set_focus()
    
    btn_proximo.double_click_input()
    logger.success("✓ Clique realizado com sucesso")
    
    btn_ok = wait_element(
        criacao_req,  # Procurar na tela de Requisição, não na janela principal
        class_name="TFagronButton",
        found_index=1,
        timeout=5,
        label="Botão Próxima Requisição",
    )

    btn_ok.set_focus()

    safe_click(btn_ok)
    logger.success("✓ Clique no botão OK realizado com sucesso")
  


def etapa_preencher_receita() -> bool:
    """Preenche os dados da requisição no módulo de receitas."""
    app_receitas = wait_app_by_exe("FCReceitas.exe", timeout=10)
    
    receitas = etapa_detectar_e_focar_receitas(app_receitas)

    receitas.type_keys("{TAB 2}")
    time.sleep(0.2)

    safe_type(receitas, "1", label="Campo Cliente")

    receitas.type_keys("{TAB}")
    time.sleep(1)

    logger.info("📍 [5/10] Verificando alertas...")

    time.sleep(0.5)

    cad_cli = wait_window(app_receitas, "Cadastro de Clientes", timeout=10, label="TfrVisual")
    logger.success("✓ Tela de Consulta aberta")
    cad_cli.set_focus()
    cad_cli.type_keys("%{F4}")
    receitas.set_focus()
    time.sleep(1)

    # =====================================================
    # FINALIZAÇÃO
    # =====================================================

    logger.info("📍 [9/10] Finalizando receita...")

   

    receitas.type_keys("{TAB 3}")
    

    cad_cli = wait_window(app_receitas, "Funcionário Recepção", timeout=10, label="TfrVisual")
    logger.success("✓ Tela de Consulta aberta")
    cad_cli.set_focus()
    cad_cli.type_keys("%{F4}")
    receitas.set_focus()

    logger.success("✓ Receita finalizada")

    receitas.type_keys("{TAB}")
    time.sleep(0.5)
    safe_type(receitas, "1", label="Campo Cliente")
    receitas.type_keys("{TAB}")

    cad_med = wait_window(app_receitas, "Cadastro de Médicos", timeout=10, label="TfrVisual")
    logger.success("✓ Tela de Consulta aberta")
    cad_med.set_focus()
    cad_med.type_keys("%{F4}")
    receitas.set_focus()
    receitas.type_keys("{TAB 2}")
    safe_type(receitas, "30", label="Campo Cliente")
    receitas.type_keys("{TAB 10}")
    safe_type(receitas, "51639", label="Campo Cliente")
    receitas.type_keys("{ENTER}")
    alert = wait_window(app_receitas, "Atenção!", timeout=10, label="TfrVisual")
    logger.success("✓ Alerta exibido")
    alert.set_focus()
    alert.type_keys("%{F4}")
    receitas.set_focus()        
    safe_type(receitas, "200", label="Campo Cliente")
    receitas.type_keys("{ENTER 3}")
    alert.set_focus()
    alert.type_keys("%{F4}")
    receitas.set_focus()
    confirmacao = wait_window(app_receitas, "Confirmação", timeout=10,)
    confirmacao.set_focus()
    
    confirmacao.type_keys("{ENTER}")

    componente = wait_window(app_receitas, "Componente", timeout=2,)
    componente.set_focus()
    componente.type_keys("{ENTER}")

    embalagem = wait_window(app_receitas, "Embalagem", timeout=2,)
    embalagem.set_focus()
    btn_ok = wait_element(
        embalagem,  # Procurar na tela de Requisição, não na janela principal
        title="Ok",
        class_name="TFagronButton",
        timeout=5,
        label="Botão ok",
    )
    btn_ok.set_focus()
    
    btn_ok.double_click_input()
    
    # Validar se o alerta final aparece
    try:
        alert = wait_window(app_receitas, "Atenção!", timeout=10, label="TfrVisual")
        logger.success("✓ Alerta exibido")
        logger.info("=" * 60)
        logger.success("🎉 RECEITA PREENCHIDA COM SUCESSO - VALIDAÇÃO PASSOU")
        logger.info("=" * 60)
        return True  # Teste passa
    except TimeoutError:
        logger.error("❌ ALERTA NÃO FOI ENCONTRADO - VALIDAÇÃO FALHOU")
        logger.info("=" * 60)
        return False  # Teste falha


def run():
    setup_logging(log_name="Receitas_flow", json_output=True)
    logger.info("=" * 60)
    logger.info("🚀 INÍCIO DO FLUXO: RECEITAS")
    logger.info("=" * 60)

    try:
        logger.info("📍 [1/5] Conectando ao sistema...")
        app = etapa_conectar_ou_iniciar()
        logger.success("✓ Conectado")

        try:
            logger.info("📍 [2/5] Verificando autenticação...")
            main = wait_window(app, r".*FórmulaCerta.*", timeout=5, label="Principal")
            logger.info("Sistema já autenticado, pulando login.")
        except TimeoutError:
            logger.info("Autenticação necessária. Realizando login...")
            etapa_login(app)
            main = wait_window(app, r".*FórmulaCerta.*", timeout=20, label="Principal")
            logger.success("✓ Login concluído")

        logger.info("📍 [3/5] Abrindo menu de Receitas...")
        etapa_abrir_menu_receitas(main)
        logger.success("✓ Menu aberto")
        
        logger.info("📍 [4/4] Executando fluxo de Receitas...")
        etapa_incluir_receitas()
        
        logger.info("📍 [5/5] Preenchendo dados da Receita...")
        alerta_validado = etapa_preencher_receita()
        
        logger.info("=" * 60)
        logger.success("🎉 FLUXO FINALIZADO COM SUCESSO")
        logger.info("=" * 60)
        
        # Retorna sucesso apenas se o alerta foi validado
        return 0 if alerta_validado else 1

    except Exception as e:
        import traceback
        logger.info("=" * 60)
        logger.error(f"❌ FALHA NO FLUXO: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        logger.info("=" * 60)
        screenshot_on_failure("falha_geral")
        return 1

if __name__ == "__main__":
    sys.exit(run())