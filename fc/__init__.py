"""
fc/  — DSL estilo Cypress para o Formula Certa.

Uso:
    from fc import fc

    fc.login()
    fc.open_module("FCReceitas")
    fc.button("incluir").click()
    fc.field("produto").type("51639")
    fc.button("salvar").click()
    fc.db.assert_saved(
        query="receita_salva",
        params={"produto": "51639"},
        expected={"CDCLI": "1", "CDPRO": "51639", "QTD": "200"},
    )

Ação na tela (foco direto, sem TAB/coordenadas) + validação obrigatória no banco.
"""

from __future__ import annotations

from .context import FCContext
from .db_facade import DBFacade
from .elements import Button, Field, Window


class FC:
    """Fachada única da DSL. Importe a instância `fc`, não a classe."""

    def __init__(self):
        self._ctx = FCContext()
        self.db = DBFacade()

    # ── navegação ────────────────────────────────────────────────
    def login(self):
        self._ctx.login()
        return self

    def open_module(self, nome: str, **kwargs):
        self._ctx.open_module(nome, **kwargs)
        return self

    # ── elementos ────────────────────────────────────────────────
    def field(self, alias: str) -> Field:
        return Field(self._ctx, self._ctx.info_de(alias))

    def button(self, alias: str) -> Button:
        return Button(self._ctx, self._ctx.info_de(alias))

    def window(self, titulo: str, timeout: float = 10.0) -> Window:
        return Window(self._ctx, titulo, timeout=timeout)

    def tab(self, *titulos: str):
        """Seleciona uma aba do módulo ativo pelo título (ciclando Ctrl+Tab —
        essas abas não expõem header clicável). Ex.: fc.tab("Estoques") ·
        aninhado: fc.tab("Livros/Mapas", "Anvisa")."""
        self._ctx.selecionar_aba(*titulos)
        return self

    def print(self, label: str):
        """Tira um print de evidência com esse nome exato.
        Ex.: fc.print("1- inclusão do login")."""
        from core.evidence import iniciar_sessao, sessao_ativa

        sessao = sessao_ativa() or iniciar_sessao("sessao_avulsa")
        sessao.capturar(label)
        return self

    # ── acesso ao contexto (avançado) ────────────────────────────
    @property
    def context(self) -> FCContext:
        return self._ctx

    @property
    def main(self):
        return self._ctx.main

    def reset(self):
        self._ctx.reset()
        self.db.close()
        return self


# Singleton compartilhado pelos testes.
fc = FC()

__all__ = ["fc", "FC", "Field", "Button", "Window"]
