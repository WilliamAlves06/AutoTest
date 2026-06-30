"""webapp/routes_testes.py — API da tela Testes (descoberta + execução)."""

from __future__ import annotations

import threading
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from core.config import carregar_config
from core.test_runner import discover_suites, nome_teste, run_many
from webapp import ws_hub

router = APIRouter(prefix="/api")

_running = False


@router.get("/suites")
def api_suites() -> dict:
    cfg = carregar_config()
    suites = discover_suites(cfg.get("base", ""))
    return {
        "suites": [
            {"name": nome, "tests": [nome_teste(c) for c in scripts]}
            for nome, scripts in suites.items()
        ],
        "running": _running,
    }


class RunRequest(BaseModel):
    scope: str  # "all" | "suite"
    suite: Optional[str] = None
    tests: Optional[list[str]] = None


@router.post("/run")
def api_run(req: RunRequest) -> dict:
    global _running
    if _running:
        return {"status": "already_running"}

    cfg = carregar_config()
    suites = discover_suites(cfg.get("base", ""))

    if req.scope == "all":
        alvos = [(c, nome) for nome, scripts in suites.items() for c in scripts]
    elif req.scope == "suite" and req.suite in suites:
        scripts = suites[req.suite]
        if req.tests:
            scripts = [c for c in scripts if nome_teste(c) in req.tests]
        alvos = [(c, req.suite) for c in scripts]
    else:
        return {"status": "error", "message": "suíte inválida"}

    if not alvos:
        return {"status": "error", "message": "nenhum teste encontrado"}

    _running = True
    ws_hub.broadcast_threadsafe({"type": "started", "total": len(alvos)})

    def worker() -> None:
        global _running
        run_many(alvos, lambda r: ws_hub.broadcast_threadsafe({"type": "result", **r}))
        _running = False
        ws_hub.broadcast_threadsafe({"type": "done"})

    threading.Thread(target=worker, daemon=True).start()
    return {"status": "started", "total": len(alvos)}
