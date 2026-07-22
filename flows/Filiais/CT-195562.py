import sys
from autotest import *
from data import filiais as dados

def teste() -> None:
    logger.info("Login + abrindo módulo Filiais...")
    fc.login()
    fc.open_module("FCFiliais")
    fc.field("incluir").click()
    fc.field("Filial").type("teste automatizado")
    fc.field("razão social").type("teste automatizado razao social")
    fc.tab("Livros/Mapas")
    fc.field("farmaceutico responsavel").type("teste farmaceutico")
    fc.field("nºCRF").type("1232")
    fc.field("Salvar").click()

def validação() -> None:
    fc.login()
    fc.open_module("FCFiliais")
    fc.field("CONSULTA").type("TESTE AUTOMATIZADO")
    fc.field("Filial").should_have_value("TESTE AUTOMATIZADO")


def run() -> int:
    try:
        teste()
        validação()
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
