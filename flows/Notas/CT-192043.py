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
SENHA     = "123"

# ─────────────────────────────────────────
# CONFIGURAÇÃO — NOTA
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
    setup_logging(log_name="Notas_flow_test", json_output=True)
    logger.info("Iniciando fluxo via pytest...")

    app = etapa_conectar_ou_iniciar()

    try:
        main = wait_window(app, r".*FórmulaCerta.*", timeout=5, label="Principal")
        logger.info("Já autenticado, pulando login.")
    except TimeoutError:
        etapa_login(app)
        main = wait_window(app, r".*FórmulaCerta.*", timeout=20, label="Principal")

    etapa_abrir_menu_notas(main)
    etapa_incluir_notas()
    logger.success("Fluxo concluído — iniciando validações.")

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

def etapa_abrir_menu_notas(main) -> None:
    """Abre menu Arquivo → Notas via atalho de teclado."""
    logger.info("Abrindo menu Arquivo (ALT+A)...")
    main.set_focus()
    time.sleep(0.3)
    main.type_keys("%a")
    time.sleep(0.4)
    main.type_keys("{RIGHT}{DOWN}{DOWN}{ENTER}")
    logger.info("Módulo Notas acionado.")

def etapa_incluir_notas() -> None:
    logger.info("Aguardando processo FCNotas.exe...")
    app_notas = wait_app_by_exe("FCNotas.exe", timeout=20)

    time.sleep(0.3)
    notas = app_notas.top_window()
    logger.info(f"Janela capturada: '{notas.window_text()}'")
    notas.set_focus()

    notas.type_keys("{F5}")
    consulta_nota = wait_window(app_notas, "Consulta de Notas Fiscais", timeout=10, label="TfrVisual")
    consulta_nota.set_focus()

    numero_nota = wait_element(
        consulta_nota,
        class_name="TwwDBEdit",
        found_index=4,
        label="Número da Nota"
    )
    safe_type(numero_nota, NUMERO_NOTA, label="Número da Nota")

    btn_pesquisar = wait_element(
        app_notas.top_window(),
        class_name="TFagronButton",
        found_index=1,
        label="Botão Pesquisar",
    )
    safe_click(btn_pesquisar, label="Pesquisar")
    logger.info("Pesquisa realizada!")
    time.sleep(0.5)

    grid = wait_element(
        app_notas.top_window(),
        class_name="TwwDBGrid",
        found_index=1,
        label="Grid Notas",
    )
    grid.set_focus()
    grid.double_click_input()
    logger.info("Primeira nota selecionada.")
    time.sleep(0.5)

# ─────────────────────────────────────────
# TESTES / VALIDAÇÕES
# ─────────────────────────────────────────
class TestNotaFiscal:

    def test_nota_existe_no_banco(self, db_cursor):
        imprimir_inicio("CT-192043", "Validação de Nota Fiscal - FC11100")
        imprimir_etapa(f"Verificando se nota {NUMERO_NOTA} existe na FC11100...")

        db_cursor.execute(
            "SELECT COUNT(*) FROM FC11100 WHERE NRNOT = ?", (NUMERO_NOTA,)
        )
        count = db_cursor.fetchone()[0]

        imprimir_resultado([{
            "campo":    "NOTA EXISTS",
            "esperado": "> 0",
            "obtido":   str(count),
            "status":   "PASS" if count > 0 else "FAIL"
        }])
        assert count > 0, f"Nota {NUMERO_NOTA} não encontrada na FC11100"

    def test_cdpro_valor_esperado(self, db_cursor):
        imprimir_etapa(f"Validando CDPRO da nota {NUMERO_NOTA}...")

        db_cursor.execute(
            "SELECT CDPRO FROM FC11100 WHERE NRNOT = ?", (NUMERO_NOTA,)
        )
        row = db_cursor.fetchone()
        obtido = str(row[0]).strip() if row else "NULL"

        imprimir_resultado([{
            "campo":    "CDPRO",
            "esperado": CDPRO_ESPERADO,
            "obtido":   obtido,
            "status":   "PASS" if obtido == CDPRO_ESPERADO else "FAIL"
        }])
        assert obtido == CDPRO_ESPERADO, \
            f"CDPRO esperado '{CDPRO_ESPERADO}', obtido '{obtido}'"

    def test_nrlot_valor_esperado(self, db_cursor):
        imprimir_etapa(f"Validando NRLOT da nota {NUMERO_NOTA}...")

        db_cursor.execute(
            "SELECT NRLOT FROM FC11100 WHERE NRNOT = ?", (NUMERO_NOTA,)
        )
        row = db_cursor.fetchone()
        obtido = str(row[0]).strip() if row else "NULL"

        imprimir_resultado([{
            "campo":    "NRLOT",
            "esperado": NRLOT_ESPERADO,
            "obtido":   obtido,
            "status":   "PASS" if obtido == NRLOT_ESPERADO else "FAIL"
        }])
        assert obtido == NRLOT_ESPERADO, \
            f"NRLOT esperado '{NRLOT_ESPERADO}', obtido '{obtido}'"

# ─────────────────────────────────────────
# EXECUÇÃO DIRETA (sem pytest)
# ─────────────────────────────────────────
def run():
    setup_logging(log_name="Notas_flow", json_output=True)
    logger.info("=" * 50)
    logger.info("INÍCIO DO FLUXO: Notas")
    logger.info("=" * 50)

    try:
        app = etapa_conectar_ou_iniciar()

        try:
            main = wait_window(app, r".*FórmulaCerta.*", timeout=5, label="Principal")
            logger.info("Sistema já autenticado, pulando login.")
        except TimeoutError:
            etapa_login(app)
            main = wait_window(app, r".*FórmulaCerta.*", timeout=20, label="Principal")

        etapa_abrir_menu_notas(main)
        etapa_incluir_notas()
        logger.success("FLUXO FINALIZADO COM SUCESSO.")
        return 0

    except Exception as e:
        import traceback
        logger.error(f"FALHA NO FLUXO: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        screenshot_on_failure("falha_geral")
        return 1

if __name__ == "__main__":
    sys.exit(run())