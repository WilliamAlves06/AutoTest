"""
database/assertions.py
A "Regra Oficial de Aprovação": um teste só passa quando os dados estão
efetivamente persistidos no banco — a mensagem visual de sucesso não basta.

`assert_saved(...)`:
  1. roda a query nomeada,
  2. compara campo a campo com o esperado,
  3. imprime a tabela de resultado (reusa core/reporter.imprimir_resultado),
  4. levanta AssertionError se QUALQUER campo reprovar.
"""

from __future__ import annotations

from loguru import logger

from core.reporter import imprimir_resultado

from .firebird_client import FirebirdClient
from .validators import comparar, todos_passaram


def assert_saved(
    query: str,
    expected: dict,
    params: dict | None = None,
    *,
    client: FirebirdClient | None = None,
) -> list[dict]:
    """Valida a persistência no banco. Levanta AssertionError se reprovar.

    query    = nome do arquivo em database/queries/<query>.sql
    expected = {COLUNA: valor_esperado}
    params   = parâmetros nomeados da query (ex.: {"produto": "51639"})
    client   = FirebirdClient opcional (reutiliza conexão); senão cria um efêmero.
    """
    proprio = client is None
    cli = client or FirebirdClient()
    try:
        obtido = cli.query(query, params)
    finally:
        if proprio:
            cli.close()

    resultados = comparar(obtido, expected)
    imprimir_resultado(resultados)

    if not todos_passaram(resultados):
        falhas = [r["campo"] for r in resultados if r["status"] == "FAIL"]
        msg = f"Validação no banco REPROVADA — campos divergentes: {falhas}"
        logger.error(msg)
        raise AssertionError(msg)

    logger.success("Validação no banco APROVADA — todos os campos conferem.")
    return resultados
