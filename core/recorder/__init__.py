"""
Módulo de gravação e inspeção de testes desktop.

Componentes:
- locator: Identificação de elementos Windows (sem coordenadas)
- action_detector: Captura de eventos do usuário em tempo real
- codegen: Geração de código Pywinauto automaticamente
"""

from .locator import ElementLocator, ElementInfo
from .action_detector import ActionDetector, DetectedAction
from .codegen import CodeGenerator

__all__ = [
    "ElementLocator",
    "ElementInfo",
    "ActionDetector",
    "DetectedAction",
    "CodeGenerator",
]
