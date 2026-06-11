# borabill.py
# Gerado pelo Recorder (DSL fc) em 2026-06-11 12:34
"""Teste gerado automaticamente — revise os aliases e preencha a validação no banco."""

import sys
from pathlib import Path

try:
    import pytest
except ImportError:
    pytest = None

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Um único import traz fc, logger, setup_logging, imprimir_*, screenshot_on_failure.
from fc.kit import *  # noqa: F401,F403

def executar() -> None:
    """Fluxo gravado. Foco direto por alias — sem TAB/coordenadas."""
    fc.login()
    fc.open_module("FCFiliais")
    # clique não mapeado (prefira teclado / mapeie o elemento)
    fc.button("Complemento").click()  # erro click em incluir
    fc.button("Endereço").click()  # era o campo filial
    # digitou "teste" (campo não identificado — mapear manualmente) erro: era o campo filial
    fc.button("Municipío").click()  # era o campo complemento
    fc.button("CNPJ").click()  # era o campo município
    fc.button("Filial").click()  # era o campo bairro
    # digitou "teste" (campo não identificado — mapear manualmente)
    fc.button("salvar").click() #correto
    fc.open_module("python")

    # TODO: validação OBRIGATÓRIA no banco (a tela não basta):
    # fc.db.assert_saved(query="<sql>", params={...}, expected={...})


if pytest is not None:

    @pytest.fixture(scope="module", autouse=True)
    def _fluxo():
        setup_logging(log_name="borabill_test", json_output=True)
        executar()
        yield
        fc.reset()

    @pytest.mark.e2e
    def test_borabill():
        # TODO: asserts de validação no banco aqui (fc.db.assert_saved / comparar).
        pass


def run() -> int:
    setup_logging(log_name="borabill", json_output=True)
    imprimir_inicio("boraBill", "Teste gerado pelo Recorder (DSL fc)")
    try:
        executar()
        logger.success("FLUXO FINALIZADO (revise a validação no banco).")
        return 0
    except Exception as e:
        import traceback
        logger.error(f"FALHA NO FLUXO: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        screenshot_on_failure("borabill_falha")
        return 1
    finally:
        fc.reset()


if __name__ == "__main__":
    sys.exit(run())
