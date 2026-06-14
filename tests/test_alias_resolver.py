"""Testes unitários do AliasResolver (core/recorder/alias_resolver.py)."""

import types

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
class _FakeWrapper:
    """Imita o mínimo do wrapper pywinauto: class_name() e element_info.control_type."""
    def __init__(self, cls="", control_type=""):
        self._cls = cls
        self.element_info = types.SimpleNamespace(control_type=control_type)

    def class_name(self):
        return self._cls


def test_clique_em_campo_prefere_foco_sobre_from_point_vizinho():
    from core.recorder.action_detector import ActionDetector
    # from_point caiu no vizinho (edit); o foco é o campo certo (outro edit).
    vizinho = _FakeWrapper("TDBEdit", "Edit")
    focado = _FakeWrapper("TDBEdit", "Edit")
    assert ActionDetector._alvo_do_clique(vizinho, focado) is focado


def test_clique_em_botao_mantem_from_point():
    from core.recorder.action_detector import ActionDetector
    # Botão pelo ponto vence — botão nem sempre recebe foco (foco fica no edit anterior).
    botao = _FakeWrapper("TcxButton", "Button")
    edit_focado = _FakeWrapper("TDBEdit", "Edit")
    assert ActionDetector._alvo_do_clique(botao, edit_focado) is botao
    assert ActionDetector._eh_botao_wrapper(botao)
    assert not ActionDetector._eh_campo_wrapper(botao)


def test_clique_sem_foco_util_cai_no_from_point():
    from core.recorder.action_detector import ActionDetector
    campo = _FakeWrapper("TDBEdit", "Edit")
    assert ActionDetector._alvo_do_clique(campo, None) is campo
    assert ActionDetector._eh_campo_wrapper(campo)
