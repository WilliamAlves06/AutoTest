"""
flows/Filiais/consulta_filial.py
Consulta de Filial no Formula Certa — versão DSL (estilo Cypress).

Fluxo:
  1. login
  2. abrir módulo Filiais (anexa se já aberto; senão tentaria o menu)
  3. consultar a filial 10 (digita o código no campo de busca + Enter)
  4. finalizar validando a TELA × BANCO (Razão Social da tela == FC01000.RAZAO)

Pré-requisitos:
  - mappings/FCFiliais/Filiais.json (já existe, com os aliases curados)
  - database/queries/filial_consulta.sql (FC01000)
"""

import sys
from pathlib import Path

try:
    import pytest
except ImportError:
    pytest = None

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Um único import traz tudo: fc, logger, setup_logging, imprimir_*,
# screenshot_on_failure, comparar, todos_passaram.
from fc.kit import *  # noqa: F401,F403
from data import filiais as dados

# ─────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────
CODIGO_FILIAL = dados.CODIGO_CONSULTA


# ─────────────────────────────────────────
# FLUXO
# ─────────────────────────────────────────
def etapa_abrir_modulo() -> None:
    logger.info("Login + abrindo módulo Filiais...")
    fc.login()
    fc.open_module("FCFiliais")


def etapa_consultar() -> None:
    fc.field("Consulta_Campo").type(CODIGO_FILIAL).press("{ENTER}")
def etapa_validar() -> None:
    registro = fc.db.query("filial_consulta", {"codigo": CODIGO_FILIAL})
    if registro is None:
        raise AssertionError(f"Filial {CODIGO_FILIAL} não existe no banco (FC01000).")

    tela = {"RAZAO": fc.field("Razao_Social").get_value()}
    esperado = {"RAZAO": registro["RAZAO"]}

    resultados = comparar(tela, esperado)
    imprimir_resultado(resultados)

    if not todos_passaram(resultados):
        raise AssertionError("Tela divergente do banco — consulta NÃO trouxe a filial certa.")
    logger.success(f"✓ Consulta validada: filial {CODIGO_FILIAL} = '{registro['RAZAO'].strip()}'")


# ─────────────────────────────────────────
# PYTEST
# ─────────────────────────────────────────
if pytest is not None:

    @pytest.fixture(scope="module", autouse=True)
    def executar_fluxo():
        setup_logging(log_name="Filiais_consulta_test", json_output=True)
        etapa_abrir_modulo()
        etapa_consultar()
        logger.success("Fluxo concluído — iniciando validação.")
        yield
        fc.reset()

    @pytest.mark.e2e
    @pytest.mark.filiais
    def test_consulta_filial_bate_com_banco():
        etapa_validar()


# ─────────────────────────────────────────
# EXECUÇÃO DIRETA
# ─────────────────────────────────────────
def run() -> int:
    setup_logging(log_name="Filiais_consulta", json_output=True)
    imprimir_inicio("Consulta Filial", f"Consultar e validar a filial {CODIGO_FILIAL} (FCFiliais)")

    try:
        etapa_abrir_modulo()
        etapa_consultar()
        etapa_validar()

        logger.success("🎉 TESTE FINALIZADO COM SUCESSO (tela confere com o banco)")
        return 0

    except AssertionError as e:
        logger.error(f"❌ REPROVADO: {e}")
        screenshot_on_failure("filial_consulta_reprovada")
        return 1
    except Exception as e:
        import traceback
        logger.error(f"❌ FALHA NO FLUXO: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        screenshot_on_failure("filial_consulta_falha")
        return 1
    finally:
        fc.reset()


if __name__ == "__main__":
    sys.exit(run())
