"""
core/recorder/alias_resolver.py
Resolve um elemento gravado (ElementInfo) para um ALIAS estável.

É a peça que aproxima o gravador do `codegen` do Playwright: em vez de gravar
coordenadas/índices crus, cada elemento vira um alias — reaproveitando o
alias-map do módulo quando o campo já é conhecido, ou registrando um alias novo
(para ser persistido no mapping) quando é a primeira vez que o vemos.
"""

from __future__ import annotations

import re
from typing import Optional

from fc import mapping_store

# Campos de localização considerados (mesmos do alias-map).
_LOCALIZADOR = ("automation_id", "class_name", "title", "control_type", "found_index", "instance")


def _slug(texto: str) -> str:
    s = re.sub(r"[^\w]+", "_", str(texto).strip().lower()).strip("_")
    return s or "campo"


def info_para_localizador(info) -> dict:
    """ElementInfo (ou dict) -> dict apenas com os campos de localização não-vazios."""
    if isinstance(info, dict):
        ler = info.get
    else:
        ler = lambda k: getattr(info, k, None)  # noqa: E731
    out: dict = {}
    for campo in _LOCALIZADOR:
        valor = ler(campo)
        if valor not in (None, ""):
            out[campo] = valor
    return out


def casa(a: dict, b: dict) -> bool:
    """True se dois localizadores apontam para o mesmo elemento.

    automation_id é prova forte; senão class_name + (found_index | instance | title).
    """
    if a.get("automation_id") and a["automation_id"] == b.get("automation_id"):
        return True
    # control_type + título — botões owner-drawn (Incluir/Alterar/…) sem class_name
    if (a.get("title") and a["title"] == b.get("title")
            and a.get("control_type") and a["control_type"] == b.get("control_type")):
        return True
    if a.get("class_name") and a["class_name"] == b.get("class_name"):
        if a.get("found_index") is not None and a.get("found_index") == b.get("found_index"):
            return True
        if a.get("instance") is not None and a.get("instance") == b.get("instance"):
            return True
        if a.get("title") and a["title"] == b.get("title"):
            return True
    return False


class AliasResolver:
    """Mapeia ElementInfo -> alias para um módulo, reaproveitando ou criando aliases."""

    def __init__(self, module: str, existentes: Optional[dict] = None):
        self.module = mapping_store._norm_modulo(module) if module else module
        if existentes is not None:
            self._existentes = dict(existentes)
        else:
            try:
                self._existentes = mapping_store.carregar_modulo(self.module) if self.module else {}
            except Exception:
                self._existentes = {}
        self.novos: dict[str, dict] = {}   # alias -> {alias, ...localizador} a persistir

    def alias_para(self, info) -> Optional[str]:
        """Devolve o alias do elemento — existente ou recém-criado. None se irreconhecível."""
        loc = info_para_localizador(info)
        if not loc:
            return None

        for alias, registro in {**self._existentes, **self.novos}.items():
            if casa(loc, registro):
                return alias

        alias = self._nome_novo(loc)
        self.novos[alias] = {"alias": alias, **loc}
        return alias

    def _nome_novo(self, loc: dict) -> str:
        titulo = loc.get("title")
        if titulo:
            base = _slug(titulo)
        else:
            classe = re.sub(r"^Tww?|^T", "", loc.get("class_name") or "campo").lower() or "campo"
            base = _slug(classe)
            if loc.get("found_index") is not None:
                base = f"{base}_{loc['found_index']}"

        usados = set(self._existentes) | set(self.novos)
        nome, i = base, 2
        while nome in usados:
            nome, i = f"{base}_{i}", i + 1
        return nome

    def persistir(self, window: str):
        """Grava os aliases novos no mapping <module>/<window>.json (merge)."""
        if not self.novos or not self.module:
            return None
        return mapping_store.mesclar_window(self.module, window, list(self.novos.values()))
