"""core/test_runner.py — descoberta e execução de suítes de teste (subprocess).

Lógica pura (sem GUI, sem framework web): varre `base/<suite>/*.py` e executa
cada script em subprocesso, devolvendo PASS/FAIL + duração + log. Usado pela
web app local (webapp/server.py) e reutilizável por qualquer outra interface.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Optional

_ROOT = Path(__file__).resolve().parent.parent


def nome_teste(caminho: str) -> str:
    return os.path.splitext(os.path.basename(caminho))[0]


def discover_suites(base: str) -> dict[str, list[str]]:
    """Varre `base/<suite>/*.py` e devolve {suite: [caminhos dos scripts]}."""
    suites: dict[str, list[str]] = {}
    if not base or not os.path.isdir(base):
        return suites
    for pasta in sorted(os.listdir(base)):
        caminho = os.path.join(base, pasta)
        if not os.path.isdir(caminho):
            continue
        scripts = [
            os.path.join(caminho, f) for f in sorted(os.listdir(caminho))
            if f.endswith(".py") and not f.startswith("__")
        ]
        if scripts:
            suites[pasta] = scripts
    return suites


def run_one(caminho: str, modulo: Optional[str]) -> dict:
    """Executa um script de teste via subprocesso e devolve o resultado."""
    nome = nome_teste(caminho)
    inicio = time.time()
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    try:
        proc = subprocess.run(
            [sys.executable, "-u", caminho],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", cwd=str(_ROOT), env=env, timeout=600,
        )
        saida, rc = proc.stdout, proc.returncode
    except Exception as exc:  # noqa: BLE001
        saida, rc = f"{type(exc).__name__}: {exc}", 1
    dur = time.time() - inicio
    status = "PASS" if rc == 0 else "FAIL"
    return {"suite": modulo or "—", "name": nome, "status": status, "dur": dur, "log": saida or ""}


def run_many(alvos: list[tuple[str, Optional[str]]], on_result: Callable[[dict], None]) -> None:
    """Executa cada (caminho, módulo) em sequência, chamando on_result a cada um."""
    for caminho, modulo in alvos:
        on_result(run_one(caminho, modulo))
