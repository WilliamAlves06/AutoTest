"""
flows/Receitas/CT-168635.py
Incluir Receita no Formula Certa — versão DSL (estilo Cypress).

Princípios aplicados:
  - foco DIRETO no componente por alias (fc.field/fc.button) — sem TAB de navegação,
    sem coordenadas, sem found_index espalhado no teste;
  - ENTER é usado apenas como COMMIT de valor (dispara o lookup do Delphi),
    nunca para navegar entre campos;
  - aprovação OBRIGATÓRIA no banco (fc.db.assert_saved) — a mensagem visual de
    sucesso não basta.

Pré-requisitos para rodar em produção:
  1. mappings/FCReceitas/Receitas.json com os localizadores REAIS dos campos
     (gerar pela aba "Mapear" + "Editar aliases"; o template atual marca os
     campos com found_index provisório);
  2. database/queries/receita_salva.sql apontando para a tabela/colunas reais
     da receita (ver seção "Verificação" do plano).
"""

import sys
from pathlib import Path

try:
    import pytest
except ImportError:
    pytest = None
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.logging_setup import setup_logging
from core.actions import screenshot_on_failure
from fc import fc

# ─────────────────────────────────────────
# CONFIGURAÇÃO — Receita
# ─────────────────────────────────────────
CLIENTE    = "1"
MEDICO     = "1"
DIAS       = "30"
PRODUTO    = "51639"
QUANTIDADE = "200"

# Valores que DEVEM estar persistidos no banco para o teste passar.
EXPECTED_DB = {
    "CDCLI": CLIENTE,
    "CDMED": MEDICO,
    "CDPRO": PRODUTO,
    "QTD":   QUANTIDADE,
    "DIAS":  DIAS,
}


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────
def _fechar_se_aparecer(titulo: str, timeout: float = 8.0) -> None:
    """Fecha um modal de lookup/alerta se ele surgir; ignora se não aparecer."""
    try:
        fc.window(titulo, timeout=timeout).close()
        logger.success(f"✓ Janela '{titulo}' fechada")
    except Exception:
        logger.warning(f"⚠ Janela '{titulo}' não apareceu (seguindo)")


# ─────────────────────────────────────────
# FLUXO
# ─────────────────────────────────────────
def etapa_abrir_modulo() -> None:
    logger.info("Login + abrindo módulo Receitas...")
    fc.login()
    fc.open_module("FCReceitas")


def etapa_incluir() -> None:
    logger.info("=" * 60)
    logger.info("ETAPA: Incluir Receita")
    logger.info("=" * 60)

    # Sub-tela de Histórico do Cliente costuma abrir junto — fecha se vier.
    _fechar_se_aparecer("Histórico do Cliente", timeout=5)

    # F2 abre a tela de inclusão (ação de comando, não navegação).
    fc.context.janela_ativa().type_keys("{F2}")
    fc.window("Requisição", timeout=10).should_exist()

    fc.button("Próxima").double_click()
    fc.button("ok_requisicao").click()
    logger.success("✓ Requisição criada")


def etapa_preencher() -> None:
    logger.info("ETAPA: Preencher receita (foco direto por alias)")

    fc.field("cliente").type(CLIENTE).press("{ENTER}")
    _fechar_se_aparecer("Cadastro de Clientes")
    _fechar_se_aparecer("Funcionário Recepção")

    fc.field("medico").type(MEDICO).press("{ENTER}")
    _fechar_se_aparecer("Cadastro de Médicos")

    fc.field("dias").type(DIAS)

    fc.field("produto").type(PRODUTO).press("{ENTER}")
    _fechar_se_aparecer("Atenção!")

    fc.field("quantidade").type(QUANTIDADE).press("{ENTER}")
    _fechar_se_aparecer("Atenção!")

    # Cadeia de confirmação até a embalagem.
    try:
        fc.window("Confirmação", timeout=10).ok()
    except Exception:
        logger.warning("⚠ 'Confirmação' não apareceu")
    try:
        fc.window("Componente", timeout=4).ok()
    except Exception:
        logger.warning("⚠ 'Componente' não apareceu")

    fc.window("Embalagem", timeout=10).should_exist()
    fc.button("ok_embalagem").double_click()
    logger.success("✓ Receita preenchida e salva na tela")


def etapa_validar_banco() -> None:
    """Regra Oficial de Aprovação: só passa se persistiu no banco."""
    logger.info("ETAPA: Validação obrigatória no banco")
    fc.db.assert_saved(
        query="receita_salva",
        params={"produto": PRODUTO},
        expected=EXPECTED_DB,
    )


# ─────────────────────────────────────────
# PYTEST
# ─────────────────────────────────────────
if pytest is not None:

    @pytest.fixture(scope="module", autouse=True)
    def executar_fluxo():
        setup_logging(log_name="Receitas_flow_test", json_output=True)
        etapa_abrir_modulo()
        etapa_incluir()
        etapa_preencher()
        logger.success("Fluxo concluído — iniciando validação no banco.")
        yield
        fc.reset()

    def test_receita_persistida_no_banco():
        etapa_validar_banco()


# ─────────────────────────────────────────
# EXECUÇÃO DIRETA
# ─────────────────────────────────────────
def run() -> int:
    setup_logging(log_name="Receitas_flow", json_output=True)
    logger.info("=" * 60)
    logger.info("🚀 INÍCIO DO FLUXO: RECEITAS (DSL)")
    logger.info("=" * 60)

    try:
        etapa_abrir_modulo()
        etapa_incluir()
        etapa_preencher()
        etapa_validar_banco()

        logger.info("=" * 60)
        logger.success("🎉 FLUXO FINALIZADO COM SUCESSO (tela + banco)")
        logger.info("=" * 60)
        return 0

    except AssertionError as e:
        logger.error(f"❌ REPROVADO NA VALIDAÇÃO DE BANCO: {e}")
        screenshot_on_failure("receita_reprovada_banco")
        return 1
    except Exception as e:
        import traceback
        logger.error(f"❌ FALHA NO FLUXO: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        screenshot_on_failure("receita_falha_geral")
        return 1
    finally:
        fc.reset()


if __name__ == "__main__":
    sys.exit(run())
