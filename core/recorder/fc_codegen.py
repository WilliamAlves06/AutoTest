"""
core/recorder/fc_codegen.py
Gera um teste já na DSL `fc` (estilo Cypress/Playwright) a partir das ações gravadas.

Diferente do `codegen.py` legado (que emite wait_element/safe_type cru), este:
  - usa `from fc.kit import *` e a API fluente (`fc.field/fc.button/fc.open_module`);
  - resolve cada elemento para um ALIAS (reaproveita o alias-map do módulo ou cria
    aliases novos via AliasResolver, persistidos no mapping);
  - representa a abertura de módulo por `fc.open_module(...)` (sem teclas de menu);
  - deixa um TODO de validação obrigatória no banco (`fc.db.assert_saved`).
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.recorder.action_detector import DetectedAction
from core.recorder.alias_resolver import AliasResolver

# Classes/tipos que tratamos como botão (clique = fc.button).
_BOTOES = ("button", "bitbtn", "fagronbutton", "speedbutton")

_HEADER = '''\
# {filename}
# Gerado pelo Recorder (DSL fc) em {date}
"""Teste gerado automaticamente — revise os aliases e preencha a validação no banco."""

import sys
from pathlib import Path

try:
    import pytest
except ImportError:
    pytest = None

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Um único import traz fc, logger, setup_logging, imprimir_*, screenshot_on_failure.
from fc.kit import *  # noqa: F401,F403

'''


class FCCodeGenerator:
    """Converte uma lista de DetectedAction em um teste na DSL `fc`."""

    def __init__(self):
        # módulo -> AliasResolver (preenchido a cada generate()).
        self._resolvers: dict[str, AliasResolver] = {}
        # módulo -> título de janela representativo (para nomear o arquivo do mapping).
        self._janela_por_modulo: dict[str, str] = {}

    # ── API pública ──────────────────────────────────────────────
    def generate(
        self,
        actions: list[DetectedAction],
        test_name: str,
        aliases_por_modulo: Optional[dict] = None,
    ) -> str:
        """Retorna o código-fonte do teste. `aliases_por_modulo` injeta mapas existentes (testes)."""
        self._resolvers = {}
        self._janela_por_modulo = {}
        self._aliases_injetados = aliases_por_modulo or {}

        slug = self._slug(test_name)
        passos = self._gerar_passos(actions)

        code = _HEADER.format(
            filename=f"{slug}.py",
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        code += self._render_corpo(slug, test_name, passos)
        return code

    def save(
        self,
        actions: list[DetectedAction],
        test_name: str,
        output_dir: str | Path,
        persistir_aliases: bool = True,
    ) -> Path:
        code = self.generate(actions, test_name)

        if persistir_aliases:
            for modulo, resolver in self._resolvers.items():
                janela = self._janela_por_modulo.get(modulo) or modulo
                try:
                    resolver.persistir(window=self._slug_janela(janela))
                except Exception:
                    pass

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{self._slug(test_name)}.py"
        path.write_text(code, encoding="utf-8")
        return path

    @property
    def novos_aliases(self) -> dict[str, list[dict]]:
        """{modulo: [elementos novos]} descobertos no último generate()."""
        return {m: list(r.novos.values()) for m, r in self._resolvers.items() if r.novos}

    # ── geração dos passos ───────────────────────────────────────
    def _gerar_passos(self, actions: list[DetectedAction]) -> list[str]:
        linhas: list[str] = ["fc.login()"]
        modulo_atual: Optional[str] = None
        resolver: Optional[AliasResolver] = None
        pular_proximo_enter = False
        campo_pendente: Optional[str] = None   # alias do campo clicado, p/ mesclar com o type

        for i, action in enumerate(actions):
            modulo = self._modulo_de(action.process_name)
            if modulo and modulo != modulo_atual:
                modulo_atual = modulo
                resolver = self._resolver_de(modulo)
                linhas.append(f'fc.open_module("{modulo}")')
            if modulo and action.element is not None:
                titulo = getattr(action.element, "window_title", None)
                if titulo:
                    self._janela_por_modulo.setdefault(modulo, titulo)

            tipo = action.action_type

            if tipo == "type":
                if modulo_atual is None:
                    campo_pendente = None
                    continue  # campo de login — coberto por fc.login()
                seguido_de_enter = (
                    i + 1 < len(actions)
                    and actions[i + 1].action_type == "special_key"
                    and actions[i + 1].key == "{ENTER}"
                )
                linhas.append(self._linha_type(resolver, action, seguido_de_enter,
                                               alias_override=campo_pendente))
                campo_pendente = None
                pular_proximo_enter = seguido_de_enter
                continue

            if tipo == "click":
                if modulo_atual is None:
                    continue
                if self._parece_campo(action.element):
                    alias = self._alias(resolver, action)
                    prox = actions[i + 1] if i + 1 < len(actions) else None
                    if prox is not None and prox.action_type == "type":
                        campo_pendente = alias   # o type a seguir vira fc.field(alias).type(...)
                        continue
                    linhas.append(f'fc.field("{alias}").click()' if alias
                                  else "# clique em campo não identificado — mapear manualmente")
                else:
                    linhas.append(self._linha_click(resolver, action))
                continue

            if tipo == "assert":
                if modulo_atual is None:
                    continue
                linhas.append(self._linha_assert(resolver, action))
                continue

            if tipo == "special_key":
                if pular_proximo_enter and action.key == "{ENTER}":
                    pular_proximo_enter = False
                    continue
                key = action.key or ""
                if key.startswith("%") or modulo_atual is None:
                    continue  # menu/alt e navegação pré-módulo → fc.open_module cobre
                linhas.append(f'fc.context.janela_ativa().type_keys("{self._q(key)}")')
                continue

        linhas.append("")
        linhas.append("# TODO: validação OBRIGATÓRIA no banco (a tela não basta):")
        linhas.append("# fc.db.assert_saved(query=\"<sql>\", params={...}, expected={...})")
        return linhas

    def _linha_type(self, resolver, action: DetectedAction, com_enter: bool,
                    alias_override: Optional[str] = None) -> str:
        texto = self._q(action.text or "")
        # Prefere o campo clicado logo antes (mais confiável que o foco no momento do flush).
        alias = alias_override if alias_override else self._alias(resolver, action)
        if alias is None:
            return f'# digitou "{texto}" (campo não identificado — mapear manualmente)'
        chamada = f'fc.field("{alias}").type("{texto}")'
        if com_enter:
            chamada += '.press("{ENTER}")'
        return chamada

    def _linha_click(self, resolver, action: DetectedAction) -> str:
        if not action.resolved or action.element is None:
            return "# clique não mapeado (prefira teclado / mapeie o elemento)"
        alias = self._alias(resolver, action)
        if alias is None:
            return "# clique em elemento não identificado — mapear manualmente"
        if self._parece_botao(action.element):
            return f'fc.button("{alias}").click()'
        return f'fc.button("{alias}").click()  # confirme: clique em campo, não botão'

    def _linha_assert(self, resolver, action: DetectedAction) -> str:
        alias = self._alias(resolver, action)
        if alias is None:
            return "# verificação em elemento não identificado — mapear manualmente"
        if action.assert_kind == "visible":
            return f'fc.field("{alias}").should_be_visible()'
        if action.assert_kind == "text":
            return f'fc.field("{alias}").should_have_text("{self._q(action.text or "")}")'
        return f'fc.field("{alias}").should_have_value("{self._q(action.text or "")}")'

    def _alias(self, resolver: Optional[AliasResolver], action: DetectedAction) -> Optional[str]:
        if resolver is None or action.element is None or not action.element.is_resolved():
            return None
        return resolver.alias_para(action.element)

    # ── render do arquivo ────────────────────────────────────────
    def _render_corpo(self, slug: str, test_name: str, passos: list[str]) -> str:
        ind = "    "
        corpo = "\n".join(ind + p if p else "" for p in passos)

        return f'''\
def executar() -> None:
    """Fluxo gravado. Foco direto por alias — sem TAB/coordenadas."""
{corpo}


if pytest is not None:

    @pytest.fixture(scope="module", autouse=True)
    def _fluxo():
        setup_logging(log_name="{slug}_test", json_output=True)
        executar()
        yield
        fc.reset()

    @pytest.mark.e2e
    def test_{slug}():
        # TODO: asserts de validação no banco aqui (fc.db.assert_saved / comparar).
        pass


def run() -> int:
    setup_logging(log_name="{slug}", json_output=True)
    imprimir_inicio("{test_name}", "Teste gerado pelo Recorder (DSL fc)")
    try:
        executar()
        logger.success("FLUXO FINALIZADO (revise a validação no banco).")
        return 0
    except Exception as e:
        import traceback
        logger.error(f"FALHA NO FLUXO: {{type(e).__name__}}: {{e}}")
        logger.error(traceback.format_exc())
        screenshot_on_failure("{slug}_falha")
        return 1
    finally:
        fc.reset()


if __name__ == "__main__":
    sys.exit(run())
'''

    # ── helpers ──────────────────────────────────────────────────
    def _resolver_de(self, modulo: str) -> AliasResolver:
        if modulo not in self._resolvers:
            existentes = self._aliases_injetados.get(modulo)
            self._resolvers[modulo] = AliasResolver(modulo, existentes=existentes)
        return self._resolvers[modulo]

    @staticmethod
    def _modulo_de(process_name: Optional[str]) -> Optional[str]:
        if not process_name:
            return None
        base = process_name[:-4] if process_name.lower().endswith(".exe") else process_name
        low = base.lower()
        if low == "fcerta":
            return None
        if not low.startswith("fc"):
            return None   # ignora processos que não são módulos do Fcerta (python, code, ...)
        return base

    @staticmethod
    def _parece_botao(info) -> bool:
        alvo = f"{getattr(info, 'class_name', '') or ''} {getattr(info, 'control_type', '') or ''}".lower()
        return any(b in alvo for b in _BOTOES)

    @staticmethod
    def _parece_campo(info) -> bool:
        """True se o elemento é um campo de entrada (Edit/Combo/Memo/etc.)."""
        if info is None:
            return False
        alvo = f"{getattr(info, 'class_name', '') or ''} {getattr(info, 'control_type', '') or ''}".lower()
        return any(k in alvo for k in ("edit", "combo", "memo", "spin", "date"))

    @staticmethod
    def _q(text: str) -> str:
        """Escapa para literal Python em aspas duplas (preserva {ENTER}, %a, etc.)."""
        return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "").replace("\r", "")

    @staticmethod
    def _slug(name: str) -> str:
        name = re.sub(r"[^\w\s-]", "", name.strip().lower())
        name = re.sub(r"[\s-]+", "_", name)
        return name or "teste_gravado"

    @staticmethod
    def _slug_janela(name: str) -> str:
        return re.sub(r"[^\w]+", "_", str(name).strip()).strip("_") or "Gravado"
