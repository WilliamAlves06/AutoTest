"""
fc/locator_engine.py
Resolve um localizador (info do alias-map) para um elemento pywinauto VIVO.

Prioridade (FASE 3) — sem TAB, sem coordenadas:
  1. automation_id            (o mais estável nos forms Delphi — ex.: "134018")
  2. class_name + title       (botões/labels com texto)
  3. control_type + title     (botões "desenhados" sem class_name nem auto_id)
  4. class_name + found_index
  5. class_name + instance    (ordem depth-first estilo AutoIt)

Toda espera reaproveita wait_element() de core.actions (polling + screenshot).
"""

from __future__ import annotations

from loguru import logger

from core.actions import wait_element
from core.recorder.locator import ElementLocator


class ElementoNaoLocalizado(Exception):
    pass


def resolver(window, info: dict, timeout: float = 10.0, label: str | None = None):
    """Tenta as estratégias em ordem. Retorna o elemento ou levanta ElementoNaoLocalizado."""
    alias = info.get("alias", "?")
    label = label or alias

    auto_id     = info.get("automation_id")
    class_name  = info.get("class_name")
    title       = info.get("title")
    ctype       = info.get("control_type")
    found_index = info.get("found_index")
    instance    = info.get("instance")

    tentativas: list[tuple[str, dict]] = []

    # 1) automation_id
    if auto_id:
        kw = {"auto_id": str(auto_id)}
        if ctype:
            kw["control_type"] = ctype
        tentativas.append(("automation_id", kw))

    # 2) class_name + title
    # (No alias-map, `title` só é gravado quando é um rótulo estável — campos de
    #  edição entram com title vazio e são descartados; então usar title aqui é seguro.)
    if class_name and title:
        tentativas.append(("class_title", {"class_name": class_name, "title": title}))

    # 3) control_type + title  (botões desenhados, sem class_name)
    if title and ctype and not class_name:
        tentativas.append(("controltype_title", {"control_type": ctype, "title": title}))

    # 4) class_name + found_index
    if class_name and found_index is not None:
        tentativas.append(("class_index", {"class_name": class_name, "found_index": found_index}))

    # tempo dividido entre as tentativas rápidas; a última recebe o resto
    for i, (estrategia, kwargs) in enumerate(tentativas):
        restante = max(2.0, timeout / max(1, len(tentativas)))
        try:
            el = wait_element(window, timeout=restante, label=f"{label}[{estrategia}]", **kwargs)
            logger.debug(f"Alias '{alias}' resolvido via {estrategia}: {kwargs}")
            return el
        except Exception as e:  # noqa: BLE001 - tenta a próxima estratégia
            logger.debug(f"Estratégia {estrategia} falhou para '{alias}': {e}")

    # 5) class_name + instance (fallback depth-first)
    if class_name and instance:
        el = _por_instancia(window, class_name, int(instance))
        if el is not None:
            logger.debug(f"Alias '{alias}' resolvido via instance={instance}")
            return el

    raise ElementoNaoLocalizado(
        f"Não foi possível localizar o elemento '{alias}' (info={info})"
    )


def _por_instancia(window, class_name: str, instance: int):
    """instance é 1-based (estilo AutoIt) sobre a ordem depth-first dos descendentes."""
    try:
        matches = ElementLocator._enumerate_by_class(window, class_name)
        if 1 <= instance <= len(matches):
            return matches[instance - 1]
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Fallback por instância falhou: {e}")
    return None
