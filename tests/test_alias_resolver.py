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


def test_casa_botao_owner_drawn_por_control_type_e_titulo():
    rec = {"title": "Incluir", "control_type": "Button"}
    mapeado = {"title": "Incluir", "control_type": "Button", "found_index": 0, "instance": 35}
    assert casa(rec, mapeado)


def test_reusa_alias_de_botao_sem_class_name():
    existentes = {"incluir": {"alias": "incluir", "title": "Incluir",
                              "control_type": "Button", "found_index": 0}}
    r = AliasResolver("FCFiliais", existentes=existentes)
    alias = r.alias_para(_ei(title="Incluir", control_type="Button", strategy_used="control_title"))
    assert alias == "incluir"
    assert r.novos == {}


def test_filtro_fcerta():
    from core.recorder.action_detector import ActionDetector
    assert ActionDetector._eh_fcerta("FCFiliais.exe")
    assert ActionDetector._eh_fcerta("fcerta.exe")
    assert not ActionDetector._eh_fcerta("python.exe")
    assert not ActionDetector._eh_fcerta("Code.exe")
    assert not ActionDetector._eh_fcerta(None)


def test_alias_novo_a_partir_do_titulo_e_unico():
    r = AliasResolver("FCFiliais", existentes={"consultar": {"alias": "consultar", "automation_id": "1"}})
    alias = r.alias_para(_ei(title="Consultar", class_name="TFagronButton"))
    assert alias == "consultar_2"       # 'consultar' já existe -> sufixo


# ── escolha do elemento clicado (from_point x foco) ──────────────────────────
def test_clique_em_campo_prefere_foco_sobre_from_point_vizinho():
    from core.recorder.action_detector import ActionDetector
    # from_point caiu no vizinho (Complemento); o foco é o campo certo (Filial).
    vizinho = _ei(automation_id="919938", class_name="TDBEdit", control_type="Edit")
    focado = _ei(automation_id="658194", class_name="TDBEdit", control_type="Edit")
    assert ActionDetector._escolher_clicado(vizinho, focado) == "foco"


def test_clique_em_botao_mantem_from_point():
    from core.recorder.action_detector import ActionDetector
    # Botão pelo ponto vence — botão nem sempre recebe foco (foco fica no edit anterior).
    botao = _ei(title="Salvar", class_name="TcxButton", control_type="Button")
    edit_focado = _ei(automation_id="658194", class_name="TDBEdit", control_type="Edit")
    assert ActionDetector._escolher_clicado(botao, edit_focado) == "point"


def test_clique_sem_foco_resolvido_cai_no_from_point():
    from core.recorder.action_detector import ActionDetector
    campo = _ei(automation_id="658194", class_name="TDBEdit", control_type="Edit")
    sem_foco = ElementInfo(strategy_used="failed")
    assert ActionDetector._escolher_clicado(campo, sem_foco) == "point"
