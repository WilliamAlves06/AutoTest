"""webapp/ws_hub.py — hub de WebSocket compartilhado entre todas as telas.

Um único endpoint `/ws` é usado por Testes/Recorder/Mapear/Módulos; cada
evento traz um campo "type" para o front-end rotear. `broadcast_threadsafe`
é a única porta de entrada usada por código que roda fora do loop asyncio
(threads de subprocess, pynput, pywinauto).
"""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import WebSocket

clients: set[WebSocket] = set()
_loop: Optional[asyncio.AbstractEventLoop] = None


def capturar_loop() -> None:
    global _loop
    _loop = asyncio.get_running_loop()


async def registrar(ws: WebSocket) -> None:
    await ws.accept()
    clients.add(ws)


def remover(ws: WebSocket) -> None:
    clients.discard(ws)


async def _broadcast(payload: dict) -> None:
    mortos = []
    for ws in clients:
        try:
            await ws.send_json(payload)
        except Exception:  # noqa: BLE001
            mortos.append(ws)
    for ws in mortos:
        clients.discard(ws)


def broadcast_threadsafe(payload: dict) -> None:
    """Publica um evento vindo de fora do loop asyncio (thread de execução/recorder)."""
    if _loop is not None:
        asyncio.run_coroutine_threadsafe(_broadcast(payload), _loop)
