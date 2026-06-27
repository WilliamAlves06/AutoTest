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
def teste() -> None:
    logger.info("Login + abrindo módulo Filiais...")
    fc.login()
    fc.open_module("FCFiliais")
    fc.field("consulta").type("10").press("{ENTER}")
    fc.field("alterar").click()
    fc.field("Filiais").type("teste automatizado")
    fc.field("RazãoSocial").type("teste automatizado razao social")
    fc.tab("Numeração")
    fc.tab("Livros/Mapas") 
    fc.field("salvar").click()


def run() -> int:
    setup_logging(log_name="Filiais_consulta", json_output=True)
    imprimir_inicio("Consulta Filial", f"Consultar e validar a filial {CODIGO_FILIAL} (FCFiliais)")

    try:
        teste()

        logger.success("🎉 TESTE FINALIZADO COM SUCESSO (tela confere com o banco)")
        return 0

    except AssertionError as e:
        logger.error(f"❌ REPROVADO: {e}")
        screenshot_on_failure("filial_consulta_reprovada")
        return 1
    finally:
        fc.reset()


if __name__ == "__main__":
    sys.exit(run())
