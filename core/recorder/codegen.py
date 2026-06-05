"""
core/recorder/codegen.py
Gera scripts Python no padrao CT-168635 + etapas gravadas (estilo produtos_flow).
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.recorder.action_detector import DetectedAction


_HEADER_TEMPLATE = '''\
# {filename}
# Gerado automaticamente pelo Recorder em {date}
import sys
import time
from pathlib import Path
from pywinauto import Application
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.config import LOGIN, SENHA, EXE_PATH
from core.logging_setup import setup_logging
from core.login_flow import login_ou_obter_principal
from core.actions import (
    wait_element,
    wait_window,
    wait_app_by_exe,
    safe_click,
    safe_type,
    screenshot_on_failure,
)

'''

_BOILERPLATE_FUNCS = '''\

def etapa_conectar_ou_iniciar() -> Application:
    """Conecta ao processo em execucao ou inicia pelo caminho do exe."""
    try:
        app = Application(backend="uia").connect(path=EXE_PATH, timeout=3)
        logger.info("Conectado ao sistema ja aberto.")
        return app
    except Exception:
        logger.info("Sistema nao estava aberto — iniciando...")
        return Application(backend="uia").start(EXE_PATH)

'''


class CodeGenerator:
    """Gera script completo com boilerplate CT-168635 e etapas gravadas."""

    def generate(
        self,
        actions: list[DetectedAction],
        test_name: str,
        config: Optional[dict] = None,
    ) -> str:
        config = config or {}
        filename = f"{self._slugify(test_name)}.py"
        log_name = self._slugify(test_name)

        recorded = [a for a in actions if a.action_type != "process_changed"]
        etapas = self._agrupar_em_etapas(actions)

        code = _HEADER_TEMPLATE.format(
            filename=filename,
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        code += _BOILERPLATE_FUNCS

        etapa_funcs: list[tuple[str, str]] = []
        for i, (proc, etapa_actions) in enumerate(etapas, start=1):
            func_name, desc = self._nome_etapa(proc, etapa_actions, i)
            etapa_funcs.append((func_name, desc))
            code += self._render_etapa_gravada(func_name, proc, etapa_actions, i, desc)

        code += self._render_run(log_name, test_name, etapa_funcs, bool(recorded))
        return code

    def save(
        self,
        actions: list[DetectedAction],
        test_name: str,
        output_dir: str | Path,
        config: Optional[dict] = None,
    ) -> Path:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{self._slugify(test_name)}.py"
        path.write_text(self.generate(actions, test_name, config), encoding="utf-8")
        return path

    def _render_run(
        self,
        log_name: str,
        test_name: str,
        etapa_funcs: list[tuple[str, str]],
        has_recorded: bool,
    ) -> str:
        lines = [
            "",
            "def run():",
            f'    setup_logging(log_name="{log_name}", json_output=True)',
            '    logger.info("=" * 65)',
            f'    logger.info("INICIO DO FLUXO — {test_name}")',
            '    logger.info("=" * 65)',
            "",
            "    try:",
            '        logger.info("Etapa 1: Conectando ao sistema...")',
            "        app = etapa_conectar_ou_iniciar()",
            "",
            '        logger.info("Etapa 2: Autenticando...")',
            "        main = login_ou_obter_principal(app, LOGIN, SENHA)",
            "        main.set_focus()",
            "",
        ]

        step_num = 3
        for func_name, desc in etapa_funcs:
            lines.append(f'        logger.info("Etapa {step_num}: {desc}")')
            lines.append(f"        {func_name}(main)")
            step_num += 1

        if not has_recorded:
            lines.append('        logger.info("Nenhuma acao gravada apos login.")')

        lines.extend([
            "",
            '        logger.success("FLUXO FINALIZADO COM SUCESSO.")',
            "        return 0",
            "",
            "    except Exception as e:",
            "        import traceback",
            '        logger.error(f"FALHA NO FLUXO: {type(e).__name__}: {e}")',
            "        logger.error(traceback.format_exc())",
            f'        screenshot_on_failure("falha_{log_name}")',
            "        return 1",
            "",
            "",
            'if __name__ == "__main__":',
            "    sys.exit(run())",
            "",
        ])
        return "\n".join(lines)

    def _agrupar_em_etapas(
        self, actions: list[DetectedAction]
    ) -> list[tuple[Optional[str], list[DetectedAction]]]:
        if not actions:
            return []

        etapas: list[tuple[Optional[str], list[DetectedAction]]] = []
        processo_atual: Optional[str] = None
        grupo: list[DetectedAction] = []

        for action in actions:
            if action.action_type == "process_changed":
                if grupo:
                    etapas.append((processo_atual, grupo))
                    grupo = []
                processo_atual = action.process_name
            else:
                if processo_atual is None and action.process_name:
                    processo_atual = action.process_name
                grupo.append(action)

        if grupo:
            etapas.append((processo_atual, grupo))

        return self._fundir_etapas_vazias(etapas)

    @staticmethod
    def _fundir_etapas_vazias(
        etapas: list[tuple[Optional[str], list[DetectedAction]]],
    ) -> list[tuple[Optional[str], list[DetectedAction]]]:
        if not etapas:
            return []
        merged: list[tuple[Optional[str], list[DetectedAction]]] = []
        proc_pendente: Optional[str] = None

        for proc, grupo in etapas:
            if not grupo:
                proc_pendente = proc or proc_pendente
                continue
            proc_efetivo = proc or proc_pendente
            proc_pendente = None
            merged.append((proc_efetivo, grupo))

        return merged

    def _nome_etapa(
        self,
        process_name: Optional[str],
        actions: list[DetectedAction],
        index: int,
    ) -> tuple[str, str]:
        keys = [a.key for a in actions if a.action_type == "special_key" and a.key]
        if keys and keys[0].startswith("%"):
            return f"etapa_abrir_menu_gravado_{index}", "Abrir menu por teclado"

        proc = process_name or "janela principal"
        if any(a.action_type == "type" for a in actions):
            if process_name and not process_name.lower().startswith("fcerta"):
                return f"etapa_preencher_gravado_{index}", f"Preencher campos ({proc})"
            return f"etapa_preencher_gravado_{index}", f"Preencher campos ({proc})"
        if any(a.action_type == "click" for a in actions):
            return f"etapa_interagir_gravado_{index}", f"Interagir com controles ({proc})"
        return f"etapa_gravada_{index}", f"Acoes gravadas ({proc})"

    def _render_etapa_gravada(
        self,
        name: str,
        process_name: Optional[str],
        actions: list[DetectedAction],
        index: int,
        desc: str,
    ) -> str:
        lines = [
            f"def {name}(main):",
            f'    """{desc}"""',
        ]

        is_sub = process_name and not process_name.lower().startswith("fcerta")
        if is_sub:
            exe = process_name
            lines.append(f'    logger.info("Aguardando processo {exe}...")')
            lines.append(f'    app_sub = wait_app_by_exe("{exe}", timeout=20)')
            lines.append("    time.sleep(0.3)")
            lines.append("    win = app_sub.top_window()")
            lines.append(f'    logger.info(f"Janela capturada: \'{{win.window_text()}}\'")')
        else:
            lines.append("    win = main")

        lines.append("    win.set_focus()")
        lines.append("    time.sleep(0.2)")
        lines.append("")

        lines.extend(self._render_actions_block(actions))
        lines.append("")
        return "\n".join(lines) + "\n"

    def _render_actions_block(self, actions: list[DetectedAction]) -> list[str]:
        lines: list[str] = []
        i = 0
        while i < len(actions):
            action = actions[i]

            if action.action_type == "special_key":
                keys: list[str] = []
                while i < len(actions) and actions[i].action_type == "special_key":
                    if actions[i].key:
                        keys.append(actions[i].key)
                    i += 1
                lines.extend(self._render_menu_keys(keys))
                continue

            if action.action_type == "type":
                next_enter = (
                    i + 1 < len(actions)
                    and actions[i + 1].action_type == "special_key"
                    and actions[i + 1].key == "{ENTER}"
                )
                lines.extend(self._render_type_action(action, with_enter=next_enter))
                i += 2 if next_enter else 1
                continue

            if action.action_type == "click":
                rendered = self._render_click_action(action)
                if rendered:
                    lines.extend(rendered)
                i += 1
                continue

            i += 1

        return lines

    def _render_menu_keys(self, keys: list[str]) -> list[str]:
        if not keys:
            return []

        if keys[0].startswith("%"):
            rest = "".join(keys[1:])
            letter = keys[0][1:].upper() if len(keys[0]) > 1 else "?"
            lines = [
                f'    logger.info("Abrindo menu Arquivo (ALT+{letter})...")',
                "    win = main",
                "    win.set_focus()",
                "    time.sleep(0.3)",
                f'    win.type_keys("{self._quote_py_string(keys[0])}")',
                "    time.sleep(0.4)",
            ]
            if rest:
                lines.append(f'    win.type_keys("{self._quote_py_string(rest)}")')
            return lines

        combined = "".join(keys)
        return [f'    win.type_keys("{self._quote_py_string(combined)}")']

    def _render_type_action(
        self, action: DetectedAction, with_enter: bool = False
    ) -> list[str]:
        text = self._escape_string(action.text or "")
        if action.element and action.element.is_resolved():
            label = self._label(action.element)
            var = self._var_name_for_element(action.element)
            elem_call = action.element.to_wait_element_call("win")
            lines = [
                f'    logger.info("Preenchendo campo {label}...")',
                f"    {var} = {elem_call}",
                f'    safe_type({var}, "{text}", label={label})',
            ]
            if with_enter:
                lines.append(f"    {var}.type_keys(\"{{ENTER}}\")")
            return lines

        escaped = self._quote_py_string(action.text or "")
        return [f'    win.type_keys("{escaped}")']

    def _render_click_action(self, action: DetectedAction) -> list[str]:
        if not action.resolved or not action.element or not action.element.is_resolved():
            return []
        elem_call = action.element.to_wait_element_call("win")
        label = self._label(action.element)
        return [
            f"    _el = {elem_call}",
            f"    safe_click(_el, label={label})",
        ]

    @staticmethod
    def _var_name_for_element(info) -> str:
        if info.class_name:
            base = re.sub(r"[^a-zA-Z0-9]", "_", info.class_name).lower()
            if info.found_index is not None:
                return f"campo_{base}_{info.found_index}"
            return f"campo_{base}"
        return "campo"

    @staticmethod
    def _label(info) -> str:
        if info.title:
            return f'"{info.title}"'
        if info.class_name and info.instance:
            return f'"{info.class_name}_{info.instance}"'
        if info.class_name:
            return f'"{info.class_name}"'
        return '"campo"'

    @staticmethod
    def _quote_py_string(text: str) -> str:
        """Escapa texto para literal Python em aspas duplas (preserva {DOWN}, %a, etc.)."""
        return text.replace("\\", "\\\\").replace('"', '\\"')

    @staticmethod
    def _escape_string(text: str) -> str:
        return (
            text.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "")
            .replace("\r", "")
        )

    @staticmethod
    def _slugify(name: str) -> str:
        name = name.strip().lower()
        name = re.sub(r"[^\w\s-]", "", name)
        name = re.sub(r"[\s-]+", "_", name)
        return name or "teste_gravado"
