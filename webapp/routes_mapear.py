"""webapp/routes_mapear.py — API da tela Mapear (varredura + editor de aliases)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from core.config import carregar_config
from fc.mapping_store import carregar_mapa, salvar_mapa
from fc.modules import listar_modulos
from webapp import mapear_engine, ws_hub

router = APIRouter(prefix="/api/mapear")

_capture = mapear_engine.CaptureRecorder()


def _exe_path() -> Optional[str]:
    return carregar_config().get("exe_path") or None


@router.get("/targets")
def api_targets() -> dict:
    return {"targets": listar_modulos()}


class ScanPayload(BaseModel):
    modulo: str
    existing: Optional[list[dict]] = None


@router.post("/scan")
def api_scan(payload: ScanPayload) -> dict:
    modulo = payload.modulo.strip()
    if not modulo:
        return {"status": "error", "message": "Informe o módulo."}

    def on_progress(msg: str) -> None:
        ws_hub.broadcast_threadsafe({"type": "scan_progress", "msg": msg})

    def on_done(elementos: list[dict]) -> None:
        janela = modulo[2:] if modulo.upper().startswith("FC") else modulo
        ws_hub.broadcast_threadsafe({
            "type": "scan_done", "modulo": modulo, "janela": janela,
            "elements": elementos, "total": len(elementos),
        })

    def on_error(msg: str) -> None:
        ws_hub.broadcast_threadsafe({"type": "scan_error", "message": msg})

    ws_hub.broadcast_threadsafe({"type": "scan_started", "modulo": modulo})
    mapear_engine.escanear_async(
        modulo, _exe_path(), on_progress, on_done, on_error, existing=payload.existing
    )
    return {"status": "started"}


@router.get("/map")
def api_get_map(modulo: str, janela: str) -> dict:
    try:
        dados = carregar_mapa(modulo, janela)
    except FileNotFoundError:
        return {"elements": []}
    return {"elements": dados.get("elements", [])}


class SavePayload(BaseModel):
    modulo: str
    janela: str
    elements: list[dict]


@router.post("/save")
def api_save(payload: SavePayload) -> dict:
    modulo, janela = payload.modulo.strip(), payload.janela.strip()
    if not modulo or not janela:
        return {"status": "error", "message": "Informe módulo e janela."}
    salvar_mapa(modulo, janela, payload.elements)
    com_alias = sum(1 for e in payload.elements if str(e.get("alias", "")).strip())
    return {"status": "ok", "total": com_alias}


class DeleteAliasPayload(BaseModel):
    modulo: str
    janela: str
    alias: str


@router.post("/alias/delete")
def api_delete_alias(payload: DeleteAliasPayload) -> dict:
    try:
        dados = carregar_mapa(payload.modulo, payload.janela)
    except FileNotFoundError:
        return {"status": "error", "message": "Mapa não encontrado."}
    restantes = [e for e in dados.get("elements", []) if e.get("alias") != payload.alias]
    salvar_mapa(payload.modulo, payload.janela, restantes)
    return {"status": "ok"}


class HighlightPayload(BaseModel):
    modulo: str
    element: dict


@router.post("/highlight")
def api_highlight(payload: HighlightPayload) -> dict:
    mapear_engine.pedir_realce(payload.modulo, payload.element, _exe_path())
    return {"status": "started"}


class CapturePayload(BaseModel):
    modulo: str


@router.post("/capture/start")
def api_capture_start(payload: CapturePayload) -> dict:
    if _capture.is_running():
        return {"status": "already_running"}

    def on_capture(info: dict) -> None:
        ws_hub.broadcast_threadsafe({"type": "capture_candidate", "element": info})

    _capture.start(payload.modulo.strip(), _exe_path(), on_capture)
    return {"status": "started"}


@router.post("/capture/stop")
def api_capture_stop() -> dict:
    _capture.stop()
    return {"status": "stopped"}
