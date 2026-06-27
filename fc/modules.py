"""
fc/modules.py
Registro de como abrir cada módulo do Formula Certa a partir da janela principal.

A configuração fica em **modulos.json** (na raiz do projeto), editável sem mexer
no código. Cada módulo tem:
    "exe":  nome do processo (ex.: "FCFiliais.exe")
    "menu": lista de teclas enviadas na janela principal p/ abrir o módulo
            (sintaxe type_keys; [] = apenas anexar ao processo já aberto)

Assim dá para guardar a inicialização de TODOS os módulos num só lugar e
chamá-los com fc.open_module("FCFiliais").
"""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

# modulos.json fica na raiz do projeto (.../V1)
_ARQ = Path(__file__).resolve().parent.parent / "modulos.json"

# Defaults embutidos (fallback caso o JSON não exista / não tenha o módulo).
_BUILTIN: dict[str, dict] = {
    "FCReceitas": {"exe": "FCReceitas.exe", "menu": ["%a", "{RIGHT}{RIGHT}{ENTER}"]},
    "FCFiliais":  {"exe": "FCFiliais.exe",  "menu": []},
    "FCProdutos": {"exe": "FCProdutos.exe", "menu": ["%a", "{DOWN}{DOWN}{ENTER}"]},
}


def _chave(nome: str) -> str:
    return nome[:-4] if nome.lower().endswith(".exe") else nome


def _carregar() -> dict[str, dict]:
    """Lê modulos.json (sobrepondo os defaults). Lido a cada chamada — edições
    no arquivo passam a valer sem reiniciar."""
    dados = dict(_BUILTIN)
    if _ARQ.exists():
        try:
            arq = json.loads(_ARQ.read_text(encoding="utf-8"))
            for removido in arq.get("_removidos", []):
                dados.pop(removido, None)
            for k, v in arq.items():
                if k.startswith("_") or not isinstance(v, dict):
                    continue
                dados[k] = v
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Falha ao ler modulos.json: {exc} — usando defaults.")
    return dados


def info_modulo(nome: str) -> dict | None:
    """Retorna {exe, menu} do módulo (ou None se não registrado)."""
    return _carregar().get(_chave(nome))


def listar_modulos() -> list[str]:
    return sorted(_carregar().keys())


def salvar_modulo(nome: str, exe: str, menu: list[str]) -> Path:
    """Grava/atualiza a inicialização de um módulo em modulos.json."""
    chave = _chave(nome)
    arq: dict = {}
    if _ARQ.exists():
        try:
            arq = json.loads(_ARQ.read_text(encoding="utf-8"))
        except Exception:
            arq = {}
    arq[chave] = {"exe": exe, "menu": list(menu)}
    # se o módulo havia sido removido antes (e é um default embutido), tira da lista de removidos
    removidos = set(arq.get("_removidos", []))
    removidos.discard(chave)
    if removidos:
        arq["_removidos"] = sorted(removidos)
    else:
        arq.pop("_removidos", None)
    _ARQ.write_text(json.dumps(arq, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.success(f"Módulo '{chave}' salvo em {_ARQ}")
    return _ARQ


def remover_modulo(nome: str) -> None:
    """Remove um módulo do modulos.json. Se o módulo for um default embutido
    (_BUILTIN), marca como removido em '_removidos' — senão ele reapareceria
    na lista por causa do fallback embutido."""
    chave = _chave(nome)
    arq: dict = {}
    if _ARQ.exists():
        try:
            arq = json.loads(_ARQ.read_text(encoding="utf-8"))
        except Exception:
            arq = {}
    arq.pop(chave, None)
    if chave in _BUILTIN:
        removidos = set(arq.get("_removidos", []))
        removidos.add(chave)
        arq["_removidos"] = sorted(removidos)
    _ARQ.write_text(json.dumps(arq, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.success(f"Módulo '{chave}' removido de {_ARQ}")
