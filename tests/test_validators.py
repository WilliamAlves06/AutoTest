"""Testes unitários do comparador tela × banco (database/validators.py)."""

import pytest

from database.validators import comparar, todos_passaram

pytestmark = pytest.mark.unit


def test_comparar_tudo_igual_passa():
    res = comparar({"CDPRO": "51639", "QTD": "200"}, {"CDPRO": "51639", "QTD": "200"})
    assert todos_passaram(res)
    assert {r["status"] for r in res} == {"PASS"}


def test_comparar_normaliza_padding_e_tipos():
    # Firebird devolve CHAR com padding e números como int/Decimal.
    res = comparar({"CDPRO": "51639   ", "QTD": 200}, {"CDPRO": "51639", "QTD": "200"})
    assert todos_passaram(res)


def test_comparar_valor_diferente_reprova():
    res = comparar({"CDPRO": "999"}, {"CDPRO": "51639"})
    assert not todos_passaram(res)
    assert res[0]["status"] == "FAIL"
    assert res[0]["obtido"] == "999"


def test_comparar_sem_registro_reprova_tudo():
    res = comparar(None, {"CDPRO": "51639", "QTD": "200"})
    assert not todos_passaram(res)
    assert all(r["status"] == "FAIL" for r in res)
    assert all(r["obtido"] == "(sem registro)" for r in res)


def test_comparar_none_vira_string_vazia():
    res = comparar({"RAZAO": None}, {"RAZAO": ""})
    assert todos_passaram(res)
