"""webapp/routes_recorder.py — API da tela Recorder (gravação ao vivo -> DSL fc).

A captura roda nas threads internas do ActionDetector (mouse/teclado/COM); um
laço assíncrono único, criado no startup do servidor, drena a fila a cada
~180ms e transmite o feed + o código fc gerado via WebSocket.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from core.config import carregar_config
from core.recorder.action_detector import ActionDetector, DetectedAction
from core.recorder.fc_codegen import FCCodeGenerator
from webapp import ws_hub

router = APIRouter(prefix="/api/recorder")

_detector = ActionDetector()
_codegen = FCCodeGenerator()
_actions: list[DetectedAction] = []
_test_name = "Teste_Gravado"
_poll_started = False


def _ordenar_acoes() -> None:
    """Reordena as ações pela hora REAL do evento (timestamp).

    Um clique em campo é resolvido numa thread que pode bloquear segundos (foco +
    cache de aliases ao vivo), então sua ação chega à fila depois da digitação e do
    Enter que vieram pelo teclado. Sem reordenar, o codegen perde o vínculo
    clique→digitação e descarta o texto. O clique já é carimbado com a hora do
    clique (não a do fim da resolução), e o sort estável preserva o desempate
    natural digitação→Enter quando os timestamps empatam.
    """
    _actions.sort(key=lambda a: a.timestamp)


def _feed_item(action: DetectedAction) -> dict:
    t = action.action_type
    el = action.element
    if t == "process_changed":
        return {"code": f"# módulo: {action.process_name}", "sub": "mudança de processo"}
    if t == "type":
        alvo = (el.title if el and el.title else None) or "campo"
        return {"code": f'type("{(action.text or "")[:40]}")', "sub": alvo}
    if t == "click":
        if not action.resolved or el is None or not el.is_resolved():
            return {"code": "click (não mapeado)", "sub": "prefira teclado / mapeie o elemento"}
        alvo = el.title or el.class_name or "elemento"
        return {"code": "click()", "sub": alvo}
    if t == "special_key":
        return {"code": f'press("{action.key}")', "sub": ""}
    if t == "assert":
        alvo = (el.title if el and el.title else "elemento")
        return {"code": f"assert {action.assert_kind}", "sub": alvo}
    return {"code": t, "sub": ""}


def _broadcast_estado() -> None:
    try:
        codigo = _codegen.generate_function(_actions, _test_name)
    except Exception as exc:  # noqa: BLE001
        codigo = f"# erro ao gerar codigo: {exc}"
    visiveis = [a for a in _actions if a.action_type != "process_changed"]
    feed = [_feed_item(a) for a in visiveis[-40:]]
    ws_hub.broadcast_threadsafe({
        "type": "recorder_update", "code": codigo, "count": len(visiveis),
        "feed": feed, "recording": _detector.is_running(),
        "process": _detector._current_process,
    })


async def poll_loop() -> None:
    """Tarefa única (criada no startup do servidor) que drena a fila do detector."""
    global _poll_started
    if _poll_started:
        return
    _poll_started = True
    while True:
        await asyncio.sleep(0.18)
        if not _detector.is_running():
            continue
        novos = _detector.drain_queue()
        if novos:
            _actions.extend(novos)
            _ordenar_acoes()
            _broadcast_estado()


@router.get("/state")
def api_state() -> dict:
    try:
        codigo = _codegen.generate_function(_actions, _test_name)
    except Exception:
        codigo = ""
    visiveis = [a for a in _actions if a.action_type != "process_changed"]
    return {
        "recording": _detector.is_running(), "count": len(visiveis), "code": codigo,
        "feed": [_feed_item(a) for a in visiveis[-40:]],
        "process": _detector._current_process,
    }


class StartPayload(BaseModel):
    test_name: str = "Teste_Gravado"


@router.post("/start")
def api_start(payload: StartPayload) -> dict:
    global _test_name
    if _detector.is_running():
        return {"status": "already_running"}
    _test_name = payload.test_name.strip() or "Teste_Gravado"
    _actions.clear()
    try:
        _detector.start()
    except RuntimeError as exc:
        return {"status": "error", "message": str(exc)}
    _broadcast_estado()
    return {"status": "started"}


@router.post("/stop")
def api_stop() -> dict:
    if not _detector.is_running():
        return {"status": "not_running"}
    _detector.stop()
    _actions.extend(_detector.drain_queue())
    _ordenar_acoes()
    _broadcast_estado()
    return {"status": "stopped"}


@router.post("/clear")
def api_clear() -> dict:
    _actions.clear()
    _broadcast_estado()
    return {"status": "ok"}


@router.post("/undo")
def api_undo() -> dict:
    """Remove a última ação VISÍVEL (ignora `process_changed`, que não entra no
    feed nem na contagem). Descarta também `process_changed` que sobrar no fim.
    Funciona gravando ou parado, igual ao /clear."""
    idx = next(
        (i for i in range(len(_actions) - 1, -1, -1)
         if _actions[i].action_type != "process_changed"),
        None,
    )
    if idx is None:
        return {"status": "empty"}
    del _actions[idx]
    while _actions and _actions[-1].action_type == "process_changed":
        _actions.pop()
    _broadcast_estado()
    return {"status": "ok"}


class AssertPayload(BaseModel):
    kind: str  # visible|text|value


@router.post("/assert")
def api_assert(payload: AssertPayload) -> dict:
    if not _detector.is_running():
        return {"status": "error", "message": "Inicie a gravação antes de adicionar verificação."}
    _detector.arm_assertion(payload.kind)
    return {"status": "ok"}


class SavePayload(BaseModel):
    test_name: str = "Teste_Gravado"


@router.post("/save")
def api_save(payload: SavePayload) -> dict:
    test_name = payload.test_name.strip() or _test_name
    cfg = carregar_config()
    output_dir = Path(
        cfg.get("recorder", {}).get(
            "output_dir",
            os.path.join(os.path.dirname(cfg.get("base", "flows")), "flows", "Gravados"),
        )
    )
    try:
        path = _codegen.save(
            actions=_actions, test_name=test_name, output_dir=output_dir, persistir_aliases=True
        )
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": str(exc)}
    return {"status": "ok", "path": str(path), "novos_aliases": _codegen.novos_aliases}
