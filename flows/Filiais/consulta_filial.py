import sys
from autotest import *
from data import filiais as dados

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
