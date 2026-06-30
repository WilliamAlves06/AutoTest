"""
webapp/server.py — AutoTest QA Studio como app web local (FastAPI).

Serve a SPA estática (webapp/static) e inclui as APIs de cada tela
(Testes/Recorder/Mapear/Módulos/Configurações) — sem build step, sem
servidor remoto. Um único WebSocket (`webapp/ws_hub.py`) é compartilhado
por todas elas.

    python run_web.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from webapp import ws_hub
from webapp.routes_config import router as config_router
from webapp.routes_mapear import router as mapear_router
from webapp.routes_modulos import router as modulos_router
from webapp.routes_recorder import router as recorder_router
from webapp.routes_recorder import poll_loop as recorder_poll_loop
from webapp.routes_testes import router as testes_router

_STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="AutoTest QA Studio")


@app.middleware("http")
async def _no_cache_estaticos(request, call_next):
    """Sem build step: o navegador não pode cachear js/css entre edições."""
    response = await call_next(request)
    if request.url.path.startswith(("/js/", "/css/")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.on_event("startup")
async def _startup() -> None:
    ws_hub.capturar_loop()
    asyncio.create_task(recorder_poll_loop())


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await ws_hub.registrar(websocket)
    try:
        while True:
            await websocket.receive_text()  # mantém viva; cliente não envia nada de útil
    except WebSocketDisconnect:
        pass
    finally:
        ws_hub.remover(websocket)


app.include_router(testes_router)
app.include_router(modulos_router)
app.include_router(mapear_router)
app.include_router(recorder_router)
app.include_router(config_router)

# Servida por último: cobre "/" e qualquer caminho estático (index.html, css, js).
app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
