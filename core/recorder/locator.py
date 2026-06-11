"""
core/recorder/locator.py
Resolve um elemento pywinauto para um ElementInfo sem coordenadas de tela.

Estratégias em ordem de confiabilidade (VCL/Delphi):
  1. class + instance (AutoIt) — descendentes da janela, INSTANCE 1-based
  2. class + title
  3. automation_id (quando disponível)
  4. class + found_index entre filhos diretos
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import psutil


@dataclass
class ElementInfo:
    """Representação portável de um elemento de UI — sem coordenadas de tela."""
    automation_id:  Optional[str] = None
    class_name:     Optional[str] = None
    title:          Optional[str] = None
    control_type:   Optional[str] = None
    found_index:    Optional[int] = None   # 0-based para pywinauto wait_element
    instance:       Optional[int] = None   # 1-based estilo AutoIt
    window_class:   Optional[str] = None   # ex: TFrAutenticacao
    process_name:   Optional[str] = None
    window_title:   Optional[str] = None
    strategy_used:  str = "failed"

    def is_resolved(self) -> bool:
        return self.strategy_used != "failed"

    def to_autoit_string(self) -> str:
        """Formato Advanced Mode do AutoIt."""
        if self.class_name and self.instance is not None:
            return f"[CLASS:{self.class_name}; INSTANCE:{self.instance}]"
        if self.class_name:
            return f"[CLASS:{self.class_name}]"
        return "[elemento nao resolvido]"

    def to_wait_element_call(self, win_var: str = "win") -> str:
        """Gera a string da chamada wait_element() correspondente."""
        label = self._label_for_wait()
        if self.strategy_used in ("class_instance", "class_index") and self.class_name:
            parts = [win_var, f'class_name="{self.class_name}"']
            if self.found_index is not None:
                parts.append(f"found_index={self.found_index}")
            parts.append(f'label="{label}"')
            return f'wait_element({", ".join(parts)})'
        if self.strategy_used == "class_title":
            parts = [win_var, f'class_name="{self.class_name}"']
            if self.title:
                parts.append(f'title="{self.title}"')
            parts.append(f'label="{label}"')
            return f'wait_element({", ".join(parts)})'
        if self.strategy_used == "automation_id" and self.class_name and self.found_index is not None:
            parts = [win_var, f'class_name="{self.class_name}"', f"found_index={self.found_index}"]
            parts.append(f'label="{label}"')
            return f'wait_element({", ".join(parts)})'
        return f'wait_element({win_var}, label="elemento")  # REVISAR: {self.to_autoit_string()}'

    def _label_for_wait(self) -> str:
        if self.title:
            return self.title.replace('"', "'")[:40]
        if self.class_name:
            if self.instance is not None:
                return f"{self.class_name}_{self.instance}"
            return self.class_name
        return "elemento"


class ElementLocator:
    """
    Resolve um elemento pywinauto (wrapper) para ElementInfo.
    Nunca expõe coordenadas de tela no output.
    """

    _CLASSES_SEM_TITULO = {
        "TwwDBEdit", "TDBEdit", "TEdit", "TMemo",
        "TwwDBGrid", "TDBGrid", "TStringGrid",
        "TComboBox", "TDBComboBox", "TwwDBComboBox",
        "TFagronButton", "TButton", "TBitBtn",
    }

    def find_by_class_instance(self, window, element) -> Optional[ElementInfo]:
        """Resolve via class_name + INSTANCE (ordem depth-first nos descendentes)."""
        try:
            class_name = self._safe_class(element)
            if not class_name:
                return None

            matches = self._enumerate_by_class(window, class_name)
            target_handle = None
            try:
                target_handle = element.handle
            except Exception:
                return None

            instance = None
            for i, ctrl in enumerate(matches, start=1):
                try:
                    if ctrl.handle == target_handle:
                        instance = i
                        break
                except Exception:
                    continue

            if instance is None:
                return None

            process_name, window_title, window_class = self._get_context(window)
            return ElementInfo(
                class_name=class_name,
                found_index=instance - 1,
                instance=instance,
                title=self._safe_title(element),
                control_type=self._safe_control_type(element),
                window_class=window_class,
                process_name=process_name,
                window_title=window_title,
                strategy_used="class_instance",
            )
        except Exception:
            return None

    def find_by_class_and_title(self, window, element) -> Optional[ElementInfo]:
        try:
            class_name = self._safe_class(element)
            title = self._safe_title(element)

            if not class_name:
                return None
            if class_name in self._CLASSES_SEM_TITULO or not title:
                return None

            process_name, window_title, window_class = self._get_context(window)
            return ElementInfo(
                class_name=class_name,
                title=title,
                control_type=self._safe_control_type(element),
                window_class=window_class,
                process_name=process_name,
                window_title=window_title,
                strategy_used="class_title",
            )
        except Exception:
            return None

    def find_by_automation_id(self, window, element) -> Optional[ElementInfo]:
        try:
            auto_id = element.automation_id()
            if not auto_id or not str(auto_id).strip():
                return None

            class_name = self._safe_class(element)
            info = self.find_by_class_instance(window, element)
            if info:
                info.automation_id = str(auto_id).strip()
                return info

            process_name, window_title, window_class = self._get_context(window)
            return ElementInfo(
                automation_id=str(auto_id).strip(),
                class_name=class_name,
                title=self._safe_title(element),
                control_type=self._safe_control_type(element),
                window_class=window_class,
                process_name=process_name,
                window_title=window_title,
                strategy_used="automation_id",
            )
        except Exception:
            return None

    def find_by_class_index(self, window, element) -> Optional[ElementInfo]:
        try:
            class_name = self._safe_class(element)
            if not class_name:
                return None

            siblings = window.children(class_name=class_name)
            index = None
            for i, sibling in enumerate(siblings):
                try:
                    if sibling.handle == element.handle:
                        index = i
                        break
                except Exception:
                    continue

            if index is None:
                return None

            process_name, window_title, window_class = self._get_context(window)
            return ElementInfo(
                class_name=class_name,
                found_index=index,
                instance=index + 1,
                control_type=self._safe_control_type(element),
                window_class=window_class,
                process_name=process_name,
                window_title=window_title,
                strategy_used="class_index",
            )
        except Exception:
            return None

    def resolve(self, window, element) -> ElementInfo:
        """Tenta estratégias em ordem. Sempre retorna ElementInfo.

        1º tenta capturar o `automation_id` — é o que casa com o alias-map já
        curado (mappings/<Módulo>/*.json) e evita inventar nomes pelo rótulo errado.
        """
        info = self.find_by_automation_id(window, element)
        if info:
            return info

        class_name = self._safe_class(element)
        if class_name in self._CLASSES_SEM_TITULO or class_name:
            info = self.find_by_class_instance(window, element)
            if info:
                return info

        info = (
            self.find_by_class_and_title(window, element)
            or self.find_by_class_index(window, element)
        )
        if info:
            return info

        process_name, window_title, window_class = self._get_context(window)
        return ElementInfo(
            class_name=class_name,
            process_name=process_name,
            window_title=window_title,
            window_class=window_class,
            strategy_used="failed",
        )

    def resolve_focused(self, window) -> ElementInfo:
        """Resolve o controle com foco na janela em foreground."""
        try:
            focused = window.get_focus()
            if focused:
                return self.resolve(window, focused)
        except Exception:
            pass
        process_name, window_title, window_class = self._get_context(window)
        return ElementInfo(
            process_name=process_name,
            window_title=window_title,
            window_class=window_class,
            strategy_used="failed",
        )

    @staticmethod
    def _enumerate_by_class(window, class_name: str) -> list:
        """Lista controles da classe em ordem depth-first (como AutoIt INSTANCE)."""
        result = []
        try:
            for desc in window.descendants():
                try:
                    if desc.class_name() == class_name:
                        result.append(desc)
                except Exception:
                    continue
        except Exception:
            pass
        if not result:
            try:
                result = list(window.children(class_name=class_name))
            except Exception:
                pass
        return result

    @staticmethod
    def _safe_class(element) -> Optional[str]:
        try:
            v = element.class_name()
            return v.strip() if v else None
        except Exception:
            return None

    @staticmethod
    def _safe_title(element) -> Optional[str]:
        try:
            v = element.window_text()
            return v.strip() if v else None
        except Exception:
            return None

    @staticmethod
    def _safe_control_type(element) -> Optional[str]:
        try:
            return str(element.element_info.control_type)
        except Exception:
            return None

    @staticmethod
    def _get_context(window) -> tuple[Optional[str], Optional[str], Optional[str]]:
        process_name = None
        window_title = None
        window_class = None
        try:
            pid = window.process_id()
            proc = psutil.Process(pid)
            process_name = proc.name()
        except Exception:
            pass
        try:
            top = window.top_level_parent()
            window_title = top.window_text().strip() or None
            window_class = top.class_name()
        except Exception:
            try:
                window_title = window.window_text().strip() or None
                window_class = window.class_name()
            except Exception:
                pass
        return process_name, window_title, window_class
