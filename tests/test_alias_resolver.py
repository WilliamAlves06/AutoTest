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


# ── escolha do elemento clicado (geometria: from_point x foco) ───────────────
class _FakeWrapper:
    """Imita o mínimo do wrapper pywinauto: class_name(), control_type, rectangle()."""
    def __init__(self, cls="", control_type="", rect=None):
        self._cls = cls
        self.element_info = types.SimpleNamespace(control_type=control_type)
        self._rect = rect   # (left, top, right, bottom) ou None

    def class_name(self):
        return self._cls

    def rectangle(self):
        if self._rect is None:
            raise RuntimeError("sem retângulo")
        left, top, right, bottom = self._rect
        return types.SimpleNamespace(left=left, top=top, right=right, bottom=bottom)


def test_modo_edicao_foco_contem_ponto_vence_o_vizinho():
    from core.recorder.action_detector import ActionDetector
    # Clique em (50,210): from_point caiu no vizinho, mas o foco (campo certo)
    # também contém o ponto -> prioriza o foco.
    vizinho = _FakeWrapper("TDBEdit", "Edit", rect=(0, 200, 100, 220))
    focado = _FakeWrapper("TDBEdit", "Edit", rect=(0, 200, 100, 220))
    assert ActionDetector._escolher_alvo(vizinho, focado, 50, 210) is focado


def test_modo_consulta_foco_fora_do_ponto_usa_from_point():
    from core.recorder.action_detector import ActionDetector
    # Modo consulta: foco fica no campo de busca lá em cima (não contém o ponto);
    # o elemento sob o cursor (from_point) é quem vale.
    busca = _FakeWrapper("TEdit", "Edit", rect=(0, 100, 100, 120))
    sob_cursor = _FakeWrapper("TDBEdit", "Edit", rect=(0, 200, 100, 220))
    assert ActionDetector._escolher_alvo(sob_cursor, busca, 50, 210) is sob_cursor


def test_clique_em_botao_mantem_from_point():
    from core.recorder.action_detector import ActionDetector
    botao = _FakeWrapper("TcxButton", "Button", rect=(0, 0, 80, 30))
    edit_focado = _FakeWrapper("TDBEdit", "Edit", rect=(0, 200, 100, 220))
    assert ActionDetector._escolher_alvo(botao, edit_focado, 40, 15) is botao
    assert ActionDetector._eh_botao_wrapper(botao)
    assert not ActionDetector._eh_campo_wrapper(botao)


def test_clique_sem_foco_util_cai_no_from_point():
    from core.recorder.action_detector import ActionDetector
    campo = _FakeWrapper("TDBEdit", "Edit", rect=(0, 200, 100, 220))
    assert ActionDetector._escolher_alvo(campo, None, 50, 210) is campo
    assert ActionDetector._ponto_dentro(campo, 50, 210)
    assert not ActionDetector._ponto_dentro(campo, 50, 999)


# ── casamento ao vivo (matched_alias) vence o índice volátil ─────────────────
def test_matched_alias_vence_found_index():
    # found_index aponta p/ Complemento, mas o casamento ao vivo (handle) diz Filial.
    existentes = {
        "Filial": {"alias": "Filial", "class_name": "TDBEdit", "found_index": 5},
        "Complemento": {"alias": "Complemento", "class_name": "TDBEdit", "found_index": 4},
    }
    r = AliasResolver("FCFiliais", existentes=existentes)
    info = _ei(class_name="TDBEdit", found_index=4, matched_alias="Filial")
    assert r.alias_existente(info) == "Filial"
    assert r.alias_para(info) == "Filial"
    assert r.novos == {}          # não cria alias novo — é o curado


def test_modulo_do_processo():
    from core.recorder.action_detector import ActionDetector
    assert ActionDetector._modulo_do_processo("FCFiliais.exe") == "FCFiliais"
    assert ActionDetector._modulo_do_processo("fcerta.exe") is None
    assert ActionDetector._modulo_do_processo("python.exe") is None
    assert ActionDetector._modulo_do_processo(None) is None


# ── cruzamento por POSIÇÃO (geometria estável) ───────────────────────────────
def test_alias_em_posicao_menor_caixa_vence():
    from core.recorder.action_detector import ActionDetector
    d = ActionDetector()
    d._rect_cache["FCFiliais"] = {
        "geral": [0, 0, 500, 400],        # pane grande que também contém o ponto
        "Filial": [10, 10, 100, 30],
        "Razao_Social": [10, 50, 300, 70],
    }
    # ponto dentro de Filial E do pane -> Filial (menor caixa)
    assert d._alias_em_posicao("FCFiliais", 50, 20) == "Filial"
    assert d._alias_em_posicao("FCFiliais", 150, 60) == "Razao_Social"
    assert d._alias_em_posicao("FCFiliais", 400, 380) == "geral"   # só o pane
    assert d._alias_em_posicao("FCFiliais", 999, 999) is None      # fora de tudo


# ── resolução ao vivo do alias-map (thread dedicada, igual ao editor) ────────
class _SpecFalsa:
    def __init__(self, ok):
        self._ok = ok

    def wrapper_object(self):
        if not self._ok:
            raise RuntimeError("não localizado")
        return "WRAPPER"


def test_resolver_alias_vivo_ignora_auto_id_e_usa_found_index():
    from core.recorder.action_detector import ActionDetector

    chamadas = []

    class _Win:
        def child_window(self, **kw):
            chamadas.append(kw)
            return _SpecFalsa("found_index" in kw)   # só resolve por class+found_index

    info = {"automation_id": "658194", "class_name": "TDBEdit",
            "control_type": "Edit", "found_index": 5}
    assert ActionDetector._resolver_alias_vivo(_Win(), info) == "WRAPPER"
    assert all("auto_id" not in kw for kw in chamadas)            # nunca usa o id volátil
    assert {"class_name": "TDBEdit", "found_index": 5} in chamadas


def test_resolver_alias_vivo_botao_por_control_type_e_titulo():
    from core.recorder.action_detector import ActionDetector

    chamadas = []

    class _Win:
        def child_window(self, **kw):
            chamadas.append(kw)
            return _SpecFalsa(True)

    info = {"title": "Incluir", "control_type": "Button"}   # owner-drawn (sem class_name)
    assert ActionDetector._resolver_alias_vivo(_Win(), info) == "WRAPPER"
    assert chamadas[0] == {"control_type": "Button", "title": "Incluir"}


def test_anexar_alias_casa_pelo_handle_do_cache():
    import threading
    import types

    from core.recorder.action_detector import ActionDetector
    from core.recorder.locator import ElementInfo

    d = ActionDetector()
    d._alias_cache["FCFiliais"] = {12345: "Filial"}
    evt = threading.Event()
    evt.set()
    d._alias_evt["FCFiliais"] = evt   # cache pronto -> wait retorna na hora

    info = ElementInfo(class_name="TDBEdit", strategy_used="class_instance")
    wrapper = types.SimpleNamespace(handle=12345)
    window = types.SimpleNamespace(
        rectangle=lambda: types.SimpleNamespace(left=0, top=0, right=1, bottom=1)
    )
    d._anexar_alias(window, "FCFiliais.exe", info, wrapper, 50, 60)
    assert info.matched_alias == "Filial"
    assert info.handle == 12345


def test_anexar_rect_relativo_subtrai_a_origem_da_janela():
    import types

    from tools.mapear_janela import _anexar_rect_relativo

    class _Janela:
        def rectangle(self):
            return types.SimpleNamespace(left=100, top=200, right=900, bottom=800)

    els = [
        {"rectangle": [150, 250, 260, 274]},
        {"rectangle": [150, 290, 460, 314]},
        {"sem": "rectangle"},
    ]
    _anexar_rect_relativo(_Janela(), els)
    assert els[0]["rect"] == [50, 50, 160, 74]
    assert els[1]["rect"] == [50, 90, 360, 114]
    assert "rect" not in els[2]
