"""Testes unitários do AliasResolver (core/recorder/alias_resolver.py)."""

import pytest

from core.recorder.alias_resolver import AliasResolver, casa, info_para_localizador
from core.recorder.locator import ElementInfo

pytestmark = pytest.mark.unit


def _ei(**kw):
    kw.setdefault("strategy_used", "class_instance")
    return ElementInfo(**kw)


def test_localizador_descarta_vazios():
    loc = info_para_localizador(_ei(automation_id="1", class_name="TEdit", title=""))
    assert loc == {"automation_id": "1", "class_name": "TEdit"}


def test_casa_por_automation_id():
    assert casa({"automation_id": "9"}, {"automation_id": "9", "class_name": "X"})
    assert not casa({"automation_id": "9"}, {"automation_id": "8"})


def test_casa_por_classe_e_indice():
    assert casa({"class_name": "TEdit", "found_index": 3}, {"class_name": "TEdit", "found_index": 3})
    assert not casa({"class_name": "TEdit", "found_index": 3}, {"class_name": "TEdit", "found_index": 4})


def test_reusa_alias_existente_por_automation_id():
    existentes = {"Consulta_Campo": {"alias": "Consulta_Campo", "automation_id": "264934"}}
    r = AliasResolver("FCFiliais", existentes=existentes)
    alias = r.alias_para(_ei(automation_id="264934", class_name="TwwDBEdit", found_index=3))
    assert alias == "Consulta_Campo"
    assert r.novos == {}   # nada novo registrado


def test_cria_alias_novo_quando_desconhecido():
    r = AliasResolver("FCReceitas", existentes={})
    alias = r.alias_para(_ei(class_name="TwwDBEdit", found_index=5))
    assert alias == "dbedit_5"          # prefixo Delphi removido
    assert alias in r.novos
    assert r.novos[alias]["found_index"] == 5


def test_alias_novo_a_partir_do_titulo_e_unico():
    r = AliasResolver("FCFiliais", existentes={"consultar": {"alias": "consultar", "automation_id": "1"}})
    alias = r.alias_para(_ei(title="Consultar", class_name="TFagronButton"))
    assert alias == "consultar_2"       # 'consultar' já existe -> sufixo
