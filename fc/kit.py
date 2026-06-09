"""
fc/kit.py
Atalho único para escrever testes. Em vez de vários imports:

    from core.logging_setup import setup_logging
    from core.reporter import imprimir_inicio, imprimir_resultado
    from core.actions import screenshot_on_failure
    from database.validators import comparar, todos_passaram
    from fc import fc
    from loguru import logger

basta uma linha:

    from fc.kit import *

Isso traz: fc, logger, setup_logging, imprimir_inicio, imprimir_etapa,
imprimir_resultado, screenshot_on_failure, comparar, todos_passaram.
"""

from loguru import logger

from fc import fc
from core.logging_setup import setup_logging
from core.reporter import imprimir_inicio, imprimir_etapa, imprimir_resultado
from core.actions import screenshot_on_failure
from database.validators import comparar, todos_passaram

__all__ = [
    "fc",
    "logger",
    "setup_logging",
    "imprimir_inicio",
    "imprimir_etapa",
    "imprimir_resultado",
    "screenshot_on_failure",
    "comparar",
    "todos_passaram",
]
