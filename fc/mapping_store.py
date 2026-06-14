"""
fc/mapping_store.py
Carrega e salva os alias-maps curados (FASE 2 — padronização).

Formato do arquivo `mappings/<modulo>/<janela>.json`:
{
  "module":  "FCReceitas",
  "window":  "Receitas",
  "elements": [
    {
      "alias":         "produto",
      "automation_id": "134018",
      "class_name":    "TwwDBEdit",
      "title":         "",
      "control_type":  "Edit",
      "found_index":   18,
      "instance":      20
    }
  ]
}

O QA referencia apenas o `alias`; nunca precisa conhecer found_index/instance/etc.
"""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

# Raiz do repo: .../V1
_ROOT = Path(__file__).resolve().parent.parent
MAPPINGS_DIR = _ROOT / "mappings"

# Campos de localização preservados por elemento no alias-map.
_CAMPOS_LOCALIZADOR = (
    "automation_id", "class_name", "title", "control_type", "found_index", "instance",
)


def _norm_modulo(module: str) -> str:
    """'FCReceitas.exe' -> 'FCReceitas'."""
    return module[:-4] if module.lower().endswith(".exe") else module


def caminho_mapa(module: str, window: str) -> Path:
    return MAPPINGS_DIR / _norm_modulo(module) / f"{window}.json"


def salvar_mapa(module: str, window: str, elementos: list[dict]) -> Path:
    """Grava o alias-map. `elementos` = lista de dicts já com a chave 'alias'.

    Só persiste elementos que tenham um alias não-vazio.
    """
    module = _norm_modulo(module)
    com_alias = [_extrair(e) for e in elementos if str(e.get("alias", "")).strip()]

    caminho = caminho_mapa(module, window)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    payload = {"module": module, "window": window, "elements": com_alias}
    caminho.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.success(f"Alias-map salvo: {caminho} ({len(com_alias)} elementos)")
    return caminho


def _extrair(elemento: dict) -> dict:
    """Mantém alias + localizadores + `rect` (posição relativa à janela, p/ o recorder)."""
    out = {"alias": str(elemento["alias"]).strip()}
    for campo in _CAMPOS_LOCALIZADOR:
        if campo in elemento and elemento[campo] not in (None, ""):
            out[campo] = elemento[campo]
    rect = elemento.get("rect")
    if isinstance(rect, (list, tuple)) and len(rect) == 4:
        out["rect"] = [int(v) for v in rect]
    return out


def mesclar_window(module: str, window: str, novos_elementos: list[dict]) -> Path:
    """Mescla `novos_elementos` (dicts com 'alias') no mapa <module>/<window>.json.

    Preserva os aliases já existentes (não sobrescreve) — usado pelo gravador para
    registrar campos novos descobertos durante a gravação.
    """
    module = _norm_modulo(module)
    caminho = caminho_mapa(module, window)

    por_alias: dict[str, dict] = {}
    if caminho.exists():
        atual = json.loads(caminho.read_text(encoding="utf-8"))
        for el in atual.get("elements", []):
            if el.get("alias"):
                por_alias[el["alias"]] = el

    for el in novos_elementos:
        extraido = _extrair(el)
        por_alias.setdefault(extraido["alias"], extraido)  # não sobrescreve

    return salvar_mapa(module, window, list(por_alias.values()))


def carregar_mapa(module: str, window: str) -> dict:
    caminho = caminho_mapa(module, window)
    if not caminho.exists():
        raise FileNotFoundError(f"Alias-map não encontrado: {caminho}")
    return json.loads(caminho.read_text(encoding="utf-8"))


def carregar_modulo(module: str) -> dict[str, dict]:
    """Mescla todos os alias-maps de `mappings/<module>/*.json` em {alias: info}.

    Em caso de alias repetido entre janelas, o último vence (com aviso).
    """
    module = _norm_modulo(module)
    pasta = MAPPINGS_DIR / module
    aliases: dict[str, dict] = {}
    if not pasta.exists():
        logger.warning(f"Pasta de mapeamento inexistente: {pasta}")
        return aliases

    for arquivo in sorted(pasta.glob("*.json")):
        if arquivo.name.startswith("_"):
            continue  # reservado para metadados de módulo
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        for el in dados.get("elements", []):
            alias = el.get("alias")
            if not alias:
                continue
            if alias in aliases:
                logger.warning(f"Alias duplicado '{alias}' — sobrescrito por {arquivo.name}")
            aliases[alias] = el
    return aliases
