"""webapp/routes_modulos.py — API da tela Módulos (cadastro de abertura + gravador)."""

from __future__ import annotations

import threading
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from fc.modules import info_modulo, listar_modulos, remover_modulo, salvar_modulo
from webapp import ws_hub
from webapp.modulos_engine import MenuRecorder

router = APIRouter(prefix="/api/modulos")

_recorder = MenuRecorder()


@router.get("")
def api_listar() -> dict:
    modulos = []
    for nome in listar_modulos():
        info = info_modulo(nome) or {}
        modulos.append({"name": nome, "exe": info.get("exe", ""), "menu": info.get("menu", [])})
    return {"modulos": modulos, "gravando": _recorder.is_running()}


class ModuloPayload(BaseModel):
    nome: str
    exe: str
    menu: list[str] = []


@router.post("")
def api_salvar(payload: ModuloPayload) -> dict:
    nome, exe = payload.nome.strip(), payload.exe.strip()
    if not nome or not exe:
        return {"status": "error", "message": "Informe o nome do módulo e o executável."}
    salvar_modulo(nome, exe, payload.menu)
    return {"status": "ok"}


@router.delete("/{nome}")
def api_remover(nome: str) -> dict:
    remover_modulo(nome)
    return {"status": "ok"}


class TestarPayload(BaseModel):
    nome: str


@router.post("/testar")
def api_testar(payload: TestarPayload) -> dict:
    nome = payload.nome.strip()
    if not nome:
        return {"status": "error", "message": "Informe um módulo."}

    def worker() -> None:
        import pythoncom
        pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
        try:
            from fc import fc
            fc.reset()
            fc.open_module(nome)
            ws_hub.broadcast_threadsafe({"type": "modulo_teste", "ok": True, "nome": nome})
        except Exception as exc:  # noqa: BLE001
            ws_hub.broadcast_threadsafe(
                {"type": "modulo_teste", "ok": False, "nome": nome, "erro": str(exc)[:200]}
            )
        finally:
            pythoncom.CoUninitialize()

    threading.Thread(target=worker, daemon=True).start()
    return {"status": "started"}


@router.post("/gravar/start")
def api_gravar_start() -> dict:
    if _recorder.is_running():
        return {"status": "already_running"}
    _recorder.start(lambda token: ws_hub.broadcast_threadsafe({"type": "modulo_token", "token": token}))
    return {"status": "started"}


@router.post("/gravar/stop")
def api_gravar_stop() -> dict:
    _recorder.stop()
    return {"status": "stopped"}
