"""Testes unitários da fonte única de configuração (core/config.py)."""

import importlib

import pytest

pytestmark = pytest.mark.unit


def test_env_sobrepoe_json(monkeypatch):
    monkeypatch.setenv("FC_LOGIN", "usuario_env")
    monkeypatch.setenv("FC_SENHA", "senha_env")
    import core.config as cfg
    importlib.reload(cfg)
    dados = cfg.carregar_config()
    assert dados["login"] == "usuario_env"
    assert dados["senha"] == "senha_env"


def test_config_json_versionado_nao_tem_segredos():
    import json

    from core.config import _CONFIG_PATH
    if not _CONFIG_PATH.exists():
        pytest.skip("config.json ausente")
    bruto = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    assert "login" not in bruto, "config.json não pode versionar 'login'"
    assert "senha" not in bruto, "config.json não pode versionar 'senha'"


def test_salvar_config_remove_segredos(tmp_path, monkeypatch):
    import json

    import core.config as cfg
    importlib.reload(cfg)

    monkeypatch.setattr(cfg, "_CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(cfg, "_ENV_PATH", tmp_path / ".env")

    cfg.salvar_config({"base": "X", "login": "u", "senha": "p"})

    salvo = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert salvo == {"base": "X"}
    # Segredos foram para o .env.
    env_txt = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "FC_LOGIN" in env_txt and "FC_SENHA" in env_txt
