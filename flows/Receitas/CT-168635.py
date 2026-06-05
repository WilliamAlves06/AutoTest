import sys
import time
from pathlib import Path

try:
    import pytest
except ImportError:
    pytest = None
from loguru import logger

try:
    import fdb
except ImportError:
    fdb = None

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.logging_setup import setup_logging
from core.login_flow import login_ou_obter_principal
from core.actions import (
    wait_element,
    wait_window,
    wait_app_by_exe,
    safe_click,
    safe_type,
    screenshot_on_failure,
)
from core.reporter import imprimir_inicio, imprimir_etapa, imprimir_resultado

# ─────────────────────────────────────────
# CONFIGURAÇÃO — Receita
# ─────────────────────────────────────────
NUMERO_NOTA    = "8484"
CDPRO_ESPERADO = "51639"
NRLOT_ESPERADO = "123"

# ─────────────────────────────────────────
# FIXTURES PYTEST
# ─────────────────────────────────────────
if pytest is not None:

    @pytest.fixture(scope="module", autouse=True)
    def executar_fluxo():
        setup_logging(log_name="Receitas_flow_test", json_output=True)
        main = login_ou_obter_principal()
        etapa_abrir_menu_receitas(main)
        app_receitas, receitas = etapa_obter_janela_receitas()
        etapa_incluir_receitas(app_receitas, receitas)
        etapa_preencher_receita(app_receitas, receitas)
        logger.success("Fluxo concluido — iniciando validacoes.")

# ─────────────────────────────────────────
# FLUXO
# ─────────────────────────────────────────
def etapa_abrir_menu_receitas(main) -> None:
    """Abre menu Arquivo → Receitas via atalho de teclado."""
    logger.info("Abrindo menu Arquivo (ALT+A)...")
    main.set_focus()
    time.sleep(0.3)
    main.type_keys("%a")
    time.sleep(0.4)
    main.type_keys("{RIGHT}{RIGHT}{ENTER}")
    logger.info("Módulo Receitas acionado.")


def etapa_obter_janela_receitas():
    """Aguarda o processo FCReceitas.exe e retorna (app_receitas, receitas)."""
    logger.info("Aguardando processo FCReceitas.exe...")
    app_receitas = wait_app_by_exe("FCReceitas.exe", timeout=20)
    logger.success("✓ Processo FCReceitas.exe encontrado")
    time.sleep(0.3)
    receitas = app_receitas.top_window()
    receitas.set_focus()
    logger.info(f"Janela capturada: '{receitas.window_text()}'")
    return app_receitas, receitas


def etapa_incluir_receitas(app_receitas, receitas) -> None:
    logger.info("=" * 60)
    logger.info("INICIANDO ETAPA: Incluir Receitas")
    logger.info("=" * 60)

    logger.info("📍 [1/4] Tentando fechar sub-tela de Histórico do Cliente...")
    time.sleep(0.5)
    try:
        historico = wait_window(app_receitas, "Histórico do Cliente", timeout=5, label="TfrHistorico")
        historico.set_focus()
        historico.type_keys("%{F4}")
        logger.success("✓ Sub-tela de Histórico fechada com sucesso")
        time.sleep(0.3)
    except TimeoutError:
        logger.warning("⚠ Sub-tela de Histórico não encontrada (timeout)")

    logger.info("📍 [2/4] Abrindo tela de inclusão (F2)...")
    receitas.type_keys("{F2}")
    criacao_req = wait_window(app_receitas, "Requisição", timeout=10, label="TfrVisual")
    logger.success("✓ Tela de Consulta aberta")
    criacao_req.set_focus()

    logger.info("📍 [3/4] Clicando em 'Próxima Requisição'...")
    btn_proximo = wait_element(
        criacao_req,
        title="Próxima",
        class_name="TFagronButton",
        timeout=5,
        label="Botão Próxima Requisição",
    )
    btn_proximo.set_focus()
    btn_proximo.double_click_input()
    logger.success("✓ Clique realizado com sucesso")

    logger.info("📍 [4/4] Clicando em OK...")
    btn_ok = wait_element(
        criacao_req,
        class_name="TFagronButton",
        found_index=1,
        timeout=5,
        label="Botão OK",
    )
    btn_ok.set_focus()
    safe_click(btn_ok)
    logger.success("✓ Clique no botão OK realizado com sucesso")


def etapa_preencher_receita(app_receitas, receitas) -> bool:
    """Preenche os dados da requisição no módulo de receitas."""
    receitas.set_focus()

    receitas.type_keys("{TAB 2}")
    time.sleep(0.2)
    safe_type(receitas, "1", label="Campo Cliente")
    receitas.type_keys("{TAB}")
    time.sleep(1)

    cad_cli = wait_window(app_receitas, "Cadastro de Clientes", timeout=10, label="TfrVisual")
    logger.success("✓ Cadastro de Clientes aberto")
    cad_cli.set_focus()
    cad_cli.type_keys("%{F4}")
    receitas.set_focus()
    time.sleep(1)

    receitas.type_keys("{TAB 3}")

    func_rec = wait_window(app_receitas, "Funcionário Recepção", timeout=10, label="TfrVisual")
    logger.success("✓ Funcionário Recepção aberto")
    func_rec.set_focus()
    func_rec.type_keys("%{F4}")
    receitas.set_focus()

    receitas.type_keys("{TAB}")
    time.sleep(0.5)
    safe_type(receitas, "1", label="Campo Médico")
    receitas.type_keys("{TAB}")

    cad_med = wait_window(app_receitas, "Cadastro de Médicos", timeout=10, label="TfrVisual")
    logger.success("✓ Cadastro de Médicos aberto")
    cad_med.set_focus()
    cad_med.type_keys("%{F4}")
    receitas.set_focus()

    receitas.type_keys("{TAB 2}")
    safe_type(receitas, "30", label="Campo Dias")
    receitas.type_keys("{TAB 10}")
    safe_type(receitas, "51639", label="Campo Produto")
    receitas.type_keys("{ENTER}")

    alert = wait_window(app_receitas, "Atenção!", timeout=10, label="TfrVisual")
    logger.success("✓ Alerta exibido")
    alert.set_focus()
    alert.type_keys("%{F4}")
    receitas.set_focus()

    safe_type(receitas, "200", label="Campo Quantidade")
    receitas.type_keys("{ENTER 3}")
    alert.set_focus()
    alert.type_keys("%{F4}")
    receitas.set_focus()

    confirmacao = wait_window(app_receitas, "Confirmação", timeout=10)
    confirmacao.set_focus()
    confirmacao.type_keys("{ENTER}")

    componente = wait_window(app_receitas, "Componente", timeout=2)
    componente.set_focus()
    componente.type_keys("{ENTER}")

    embalagem = wait_window(app_receitas, "Embalagem", timeout=2)
    embalagem.set_focus()
    btn_ok = wait_element(
        embalagem,
        title="Ok",
        class_name="TFagronButton",
        timeout=5,
        label="Botão Ok",
    )
    btn_ok.set_focus()
    btn_ok.double_click_input()

    try:
        wait_window(app_receitas, "Atenção!", timeout=10, label="TfrVisual")
        logger.success("🎉 RECEITA PREENCHIDA COM SUCESSO - ALERTA EXIBIDO")
        return True
    except TimeoutError:
        logger.error("❌ ALERTA NÃO FOI ENCONTRADO - VALIDAÇÃO FALHOU")
        return False


def run():
    setup_logging(log_name="Receitas_flow", json_output=True)
    logger.info("=" * 60)
    logger.info("🚀 INÍCIO DO FLUXO: RECEITAS")
    logger.info("=" * 60)

    try:
        main = login_ou_obter_principal()
        etapa_abrir_menu_receitas(main)

        app_receitas, receitas = etapa_obter_janela_receitas()
        etapa_incluir_receitas(app_receitas, receitas)
        alerta_validado = etapa_preencher_receita(app_receitas, receitas)

        logger.info("=" * 60)
        logger.success("🎉 FLUXO FINALIZADO COM SUCESSO")
        logger.info("=" * 60)
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