"""
database/validators.py
Compara a linha obtida do banco contra os valores esperados.

Produz a lista de dicts no formato exato que core/reporter.py:imprimir_resultado()
já consome: {"campo", "esperado", "obtido", "status"} com status "PASS"/"FAIL".
"""

from __future__ import annotations


def _normalizar(valor) -> str:
    """Normaliza para comparação textual robusta (banco x tela)."""
    if valor is None:
        return ""
    # Firebird devolve CHAR com padding à direita; números podem vir como int/Decimal.
    return str(valor).strip()


def comparar(obtido: dict | None, esperado: dict) -> list[dict]:
    """Compara campo a campo.

    `obtido`   = dict {COLUNA: valor} vindo do banco (ou None se nada encontrado).
    `esperado` = dict {COLUNA: valor} esperado pelo teste.
    Retorna lista no formato de imprimir_resultado().
    """
    resultados: list[dict] = []

    if obtido is None:
        # Nenhum registro encontrado -> tudo reprova.
        for campo, valor_esp in esperado.items():
            resultados.append({
                "campo":    campo,
                "esperado": _normalizar(valor_esp),
                "obtido":   "(sem registro)",
                "status":   "FAIL",
            })
        return resultados

    for campo, valor_esp in esperado.items():
        valor_obt = obtido.get(campo)
        esp_norm = _normalizar(valor_esp)
        obt_norm = _normalizar(valor_obt)
        resultados.append({
            "campo":    campo,
            "esperado": esp_norm,
            "obtido":   obt_norm,
            "status":   "PASS" if esp_norm == obt_norm else "FAIL",
        })

    return resultados


def todos_passaram(resultados: list[dict]) -> bool:
    return all(r["status"] == "PASS" for r in resultados)
