"""webapp/routes_config.py — API da tela Configurações."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from core.config import carregar_config, salvar_config

router = APIRouter(prefix="/api/config")


@router.get("")
def api_get_config() -> dict:
    cfg = carregar_config()
    return {
        "base": cfg.get("base", ""),
        "exe_path": cfg.get("exe_path", ""),
        "login": cfg.get("login", ""),
        "senha": cfg.get("senha", ""),
        "recorder_output_dir": cfg.get("recorder", {}).get("output_dir", "flows/Gravados"),
    }


class ConfigPayload(BaseModel):
    base: str = ""
    exe_path: str = ""
    login: str = ""
    senha: str = ""
    recorder_output_dir: str = "flows/Gravados"


@router.post("")
def api_save_config(payload: ConfigPayload) -> dict:
    cfg = carregar_config()
    cfg["base"] = payload.base.strip()
    cfg["exe_path"] = payload.exe_path.strip()
    cfg["login"] = payload.login.strip()
    cfg["senha"] = payload.senha
    cfg.setdefault("recorder", {})["output_dir"] = payload.recorder_output_dir.strip()
    salvar_config(cfg)
    return {"status": "ok"}
