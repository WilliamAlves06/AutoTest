"""Testes unitários do armazenamento de alias-maps (fc/mapping_store.py)."""

import pytest

from fc import mapping_store

pytestmark = pytest.mark.unit


def test_extrair_mantem_alias_e_descarta_vazios():
    el = {
        "alias": "  produto ",
        "automation_id": "134018",
        "class_name": "TwwDBEdit",
        "title": "",            # vazio -> descartado
        "found_index": 18,
        "rectangle": "(...)",   # não é localizador -> descartado
    }
    out = mapping_store._extrair(el)
    assert out["alias"] == "produto"
    assert out["automation_id"] == "134018"
    assert "title" not in out
    assert "rectangle" not in out


def test_norm_modulo_remove_exe():
    assert mapping_store._norm_modulo("FCReceitas.exe") == "FCReceitas"
    assert mapping_store._norm_modulo("FCFiliais") == "FCFiliais"


def test_salvar_e_carregar_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(mapping_store, "MAPPINGS_DIR", tmp_path)
    elementos = [
        {"alias": "produto", "automation_id": "1", "class_name": "TwwDBEdit"},
        {"alias": "", "automation_id": "2"},  # sem alias -> não persiste
    ]
    mapping_store.salvar_mapa("FCReceitas", "Receitas", elementos)

    dados = mapping_store.carregar_mapa("FCReceitas", "Receitas")
    assert dados["module"] == "FCReceitas"
    aliases = [e["alias"] for e in dados["elements"]]
    assert aliases == ["produto"]

    mesclado = mapping_store.carregar_modulo("FCReceitas")
    assert "produto" in mesclado
