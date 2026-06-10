# core/config.py
"""Fonte ÚNICA de configuração do AutoTest.

Precedência (maior primeiro):
  1. Ambiente / arquivo `.env`  → segredos (`FC_LOGIN`, `FC_SENHA`) e `FC_EXE_PATH`
  2. `config.json` (versionado, **sem** segredos)
  3. defaults internos

Credenciais NUNCA são gravadas no `config.json` versionado: `salvar_config()`
roteia `login`/`senha` para o `.env` (ignorado pelo git). Veja `.env.example`.

API pública:
    carregar_config() -> dict      # config.json + segredos do .env, pronto p/ uso
    salvar_config(cfg)             # grava paths no json e segredos no .env
    get(chave, default)            # acesso pontual
    LOGIN, SENHA, EXE_PATH, BASE   # constantes de conveniência (compat)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv, set_key
except ImportError:  # python-dotenv ausente — degrada para só-json
    load_dotenv = None
    set_key = None

BASE_DIR = Path(__file__).resolve().parent.parent
_CONFIG_PATH = BASE_DIR / "config.json"
_ENV_PATH = BASE_DIR / ".env"

_DEFAULTS = {
    "base": str(BASE_DIR / "flows"),
    "exe_path": r"C:\Fcerta\fcerta.exe",
    "login": "",
    "senha": "",
}

# Carrega o .env uma vez na importação (se a lib estiver disponível).
if load_dotenv is not None:
    load_dotenv(_ENV_PATH)


def carregar_config() -> dict:
    """Lê `config.json` e sobrepõe segredos vindos do ambiente (`.env`).

    Sempre devolve `login`/`senha`/`exe_path` resolvidos, para que o restante
    do código (login_flow etc.) continue usando `cfg['login']` sem saber a origem.
    """
    dados = dict(_DEFAULTS)
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, encoding="utf-8") as f:
                dados.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass

    dados["login"] = os.getenv("FC_LOGIN") or dados.get("login", "")
    dados["senha"] = os.getenv("FC_SENHA") or dados.get("senha", "")
    dados["exe_path"] = (
        os.getenv("FC_EXE_PATH") or dados.get("exe_path") or _DEFAULTS["exe_path"]
    )
    return dados


# Alias histórico usado por pages/recorder_ui.py.
carregar = carregar_config


def _gravar_env(login: str | None, senha: str | None) -> None:
    """Persiste credenciais no `.env` (gitignored), sem tocar no `config.json`."""
    if login is None and senha is None:
        return

    if set_key is not None:
        if not _ENV_PATH.exists():
            _ENV_PATH.write_text("", encoding="utf-8")
        if login is not None:
            set_key(str(_ENV_PATH), "FC_LOGIN", login)
        if senha is not None:
            set_key(str(_ENV_PATH), "FC_SENHA", senha)
    else:
        # Fallback sem python-dotenv: merge linha-a-linha.
        linhas: dict[str, str] = {}
        if _ENV_PATH.exists():
            for ln in _ENV_PATH.read_text(encoding="utf-8").splitlines():
                if "=" in ln and not ln.strip().startswith("#"):
                    chave, _, val = ln.partition("=")
                    linhas[chave.strip()] = val
        if login is not None:
            linhas["FC_LOGIN"] = login
        if senha is not None:
            linhas["FC_SENHA"] = senha
        _ENV_PATH.write_text(
            "".join(f"{k}={v}\n" for k, v in linhas.items()), encoding="utf-8"
        )

    # Reflete no processo atual para quem já chamou carregar_config().
    if login is not None:
        os.environ["FC_LOGIN"] = login
    if senha is not None:
        os.environ["FC_SENHA"] = senha


def salvar_config(cfg: dict) -> None:
    """Grava `config.json` **sem** segredos; `login`/`senha` vão para o `.env`."""
    _gravar_env(cfg.get("login"), cfg.get("senha"))
    seguro = {k: v for k, v in cfg.items() if k not in ("login", "senha")}
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(seguro, f, indent=2, ensure_ascii=False)


def get(chave: str, default=None):
    """Acesso pontual a uma chave de configuração."""
    return carregar_config().get(chave, default)


# ── Compat: `from core.config import LOGIN, SENHA, EXE_PATH, BASE` ──
_cfg = carregar_config()
LOGIN: str = _cfg["login"]
SENHA: str = _cfg["senha"]
EXE_PATH: str = _cfg["exe_path"]
BASE: str = _cfg.get("base", _DEFAULTS["base"])
