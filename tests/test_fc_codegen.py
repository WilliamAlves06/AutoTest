"""Testes unitários do gerador de testes na DSL fc (core/recorder/fc_codegen.py)."""

import pytest

from core.recorder.action_detector import DetectedAction
from core.recorder.fc_codegen import FCCodeGenerator
from core.recorder.locator import ElementInfo

pytestmark = pytest.mark.unit


def _ei(**kw):
    kw.setdefault("strategy_used", "class_instance")
    return ElementInfo(**kw)


def _act(action_type, **kw):
    return DetectedAction(action_type=action_type, **kw)


def _campo_filial():
    return _ei(
        automation_id="264934", class_name="TwwDBEdit", found_index=3,
        instance=4, control_type="Edit", window_title="Filiais",
        process_name="FCFiliais.exe", strategy_used="automation_id",
    )


def test_gera_login_open_module_e_field():
    actions = [
        _act("type", element=_campo_filial(), text="10", process_name="FCFiliais.exe"),
        _act("special_key", key="{ENTER}"),
    ]
    code = FCCodeGenerator().generate(actions, "Consulta Filial 10")

    assert "from fc.kit import *" in code
    assert "fc.login()" in code
    assert 'fc.open_module("FCFiliais")' in code
    assert '.type("10").press("{ENTER}")' in code
    assert "def test_consulta_filial_10" in code
    # O código gerado tem que ser Python válido.
    compile(code, "<gerado>", "exec")


def test_reusa_alias_existente_no_codigo():
    existentes = {"FCFiliais": {"Consulta_Campo": {"alias": "Consulta_Campo", "automation_id": "264934"}}}
    gen = FCCodeGenerator()
    actions = [_act("type", element=_campo_filial(), text="10", process_name="FCFiliais.exe")]
    code = gen.generate(actions, "x", aliases_por_modulo=existentes)
    assert 'fc.field("Consulta_Campo").type("10")' in code
    assert gen.novos_aliases == {}          # nenhum alias novo criado


def test_cria_e_reporta_alias_novo():
    gen = FCCodeGenerator()
    campo = _ei(class_name="TwwDBEdit", found_index=5, process_name="FCReceitas.exe")
    actions = [_act("type", element=campo, text="51639", process_name="FCReceitas.exe")]
    code = gen.generate(actions, "y", aliases_por_modulo={"FCReceitas": {}})
    assert 'fc.open_module("FCReceitas")' in code
    assert "FCReceitas" in gen.novos_aliases
    alias = gen.novos_aliases["FCReceitas"][0]["alias"]
    assert f'fc.field("{alias}").type("51639")' in code


def test_clique_em_botao_vira_fc_button():
    gen = FCCodeGenerator()
    btn = _ei(title="Consultar", class_name="TFagronButton", control_type="Button",
              strategy_used="class_title", process_name="FCFiliais.exe")
    actions = [_act("click", element=btn, process_name="FCFiliais.exe", resolved=True)]
    code = gen.generate(actions, "z", aliases_por_modulo={"FCFiliais": {}})
    assert 'fc.button("consultar").click()' in code


def test_campos_de_login_sao_ignorados():
    gen = FCCodeGenerator()
    login = _ei(class_name="TwwDBEdit", found_index=2, process_name="fcerta.exe")
    actions = [
        _act("type", element=login, text="fagrontech", process_name="fcerta.exe"),
        _act("type", element=_campo_filial(), text="10", process_name="FCFiliais.exe"),
        _act("special_key", key="{ENTER}"),
    ]
    code = gen.generate(actions, "w", aliases_por_modulo={"FCFiliais": {}})
    assert "fagrontech" not in code          # campo de login coberto por fc.login()
    assert '.type("10")' in code


def test_inclui_todo_de_validacao_no_banco():
    code = FCCodeGenerator().generate([], "vazio")
    assert "assert_saved" in code
    compile(code, "<gerado>", "exec")


def test_clique_em_campo_mais_type_vira_field_type():
    gen = FCCodeGenerator()
    campo = _ei(automation_id="111", class_name="TwwDBEdit", control_type="Edit",
                process_name="FCFiliais.exe")
    actions = [
        _act("click", element=campo, process_name="FCFiliais.exe", resolved=True),
        _act("type", element=campo, text="10", process_name="FCFiliais.exe"),
    ]
    code = gen.generate(actions, "x", aliases_por_modulo={"FCFiliais": {}})
    assert "fc.button(" not in code              # campo não vira botão
    assert code.count('.type("10")') == 1        # clique absorvido pelo type
    assert "fc.field(" in code


def test_clique_em_campo_sem_type_vira_field_click():
    gen = FCCodeGenerator()
    campo = _ei(automation_id="222", class_name="TwwDBEdit", control_type="Edit",
                process_name="FCFiliais.exe")
    actions = [_act("click", element=campo, process_name="FCFiliais.exe", resolved=True)]
    code = gen.generate(actions, "x", aliases_por_modulo={"FCFiliais": {}})
    assert "fc.field(" in code and ".click()" in code
    assert "fc.button(" not in code


def test_clique_botao_owner_drawn_resolve_alias_mapeado():
    gen = FCCodeGenerator()
    btn = _ei(title="Incluir", control_type="Button", strategy_used="control_title",
              process_name="FCFiliais.exe")
    existentes = {"FCFiliais": {"incluir": {"alias": "incluir", "title": "Incluir",
                                            "control_type": "Button"}}}
    actions = [_act("click", element=btn, process_name="FCFiliais.exe", resolved=True)]
    code = gen.generate(actions, "x", aliases_por_modulo=existentes)
    assert 'fc.button("incluir").click()' in code


def test_processo_nao_fcerta_nao_vira_open_module():
    assert FCCodeGenerator._modulo_de("python.exe") is None
    assert FCCodeGenerator._modulo_de("Code.exe") is None
    assert FCCodeGenerator._modulo_de("fcerta.exe") is None
    assert FCCodeGenerator._modulo_de("FCFiliais.exe") == "FCFiliais"


def test_gera_assertions_should():
    gen = FCCodeGenerator()
    campo = _ei(automation_id="854414", class_name="TDBEdit", process_name="FCFiliais.exe")
    existentes = {"FCFiliais": {"Razao_Social": {"alias": "Razao_Social", "automation_id": "854414"}}}
    actions = [
        _act("assert", element=campo, assert_kind="value", text="VITACORPUS", process_name="FCFiliais.exe"),
        _act("assert", element=campo, assert_kind="visible", process_name="FCFiliais.exe"),
        _act("assert", element=campo, assert_kind="text", text="ACME", process_name="FCFiliais.exe"),
    ]
    code = gen.generate(actions, "verif", aliases_por_modulo=existentes)
    assert 'fc.field("Razao_Social").should_have_value("VITACORPUS")' in code
    assert 'fc.field("Razao_Social").should_be_visible()' in code
    assert 'fc.field("Razao_Social").should_have_text("ACME")' in code
    compile(code, "<gerado>", "exec")
