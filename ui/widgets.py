"""
ui/widgets.py — componentes reutilizáveis do design system (CustomTkinter).

Cards, pills, badges, item de suíte e botão de menu — todos lendo cores de ui.theme.
"""

from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from ui import theme as T


def pill(master, text: str, status: str = "") -> ctk.CTkLabel:
    """Chip arredondado de status (PASS verde / FAIL vermelho)."""
    cor, fundo = T.cor_status(status or text)
    return ctk.CTkLabel(
        master, text=f"● {text}", text_color=cor, fg_color=fundo,
        corner_radius=T.RADIUS_PILL, font=T.font(11, "bold"),
        padx=10, pady=2,
    )


def letter_badge(master, letra: str, cor: str = T.BLUE, size: int = 36) -> ctk.CTkLabel:
    """Quadrado arredondado com a inicial (ex.: 'R' de Receitas)."""
    return ctk.CTkLabel(
        master, text=letra.upper()[:1], text_color="white", fg_color=cor,
        corner_radius=T.RADIUS_SM, width=size, height=size, font=T.font(14, "bold"),
    )


def dot(master, cor: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(master, text="", fg_color=cor, corner_radius=6, width=9, height=9)


class StatCard(ctk.CTkFrame):
    """Card de métrica: rótulo + ponto colorido, número grande, legenda."""

    def __init__(self, master, titulo: str, cor_num: str, cor_dot: str):
        super().__init__(master, corner_radius=T.RADIUS, fg_color=T.BG_PANEL,
                         border_width=1, border_color=T.BORDER)
        self._cor_num = cor_num

        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=18, pady=(16, 4))
        ctk.CTkLabel(topo, text=titulo, text_color=T.TXT_DIM,
                     font=T.font(12)).pack(side="left")
        dot(topo, cor_dot).pack(side="right", pady=4)

        self._num = ctk.CTkLabel(self, text="0", text_color=cor_num,
                                 font=T.font(30, "bold"))
        self._num.pack(anchor="w", padx=18)

        self._sub = ctk.CTkLabel(self, text="", text_color=T.TXT_MUTED, font=T.font(11))
        self._sub.pack(anchor="w", padx=18, pady=(0, 14))

    def set(self, valor, sub: Optional[str] = None):
        self._num.configure(text=str(valor))
        if sub is not None:
            self._sub.configure(text=sub)


class SidebarButton(ctk.CTkButton):
    """Item do menu lateral com estado ativo/inativo e caixinha de ícone."""

    def __init__(self, master, icone: str, texto: str, comando: Callable):
        super().__init__(
            master, text=f"   {texto}", command=comando, anchor="w",
            corner_radius=T.RADIUS_SM, height=42, font=T.font(13),
            fg_color="transparent", hover_color=T.BG_HOVER,
            text_color=T.TXT_DIM, image=None,
        )
        self._icone = icone
        self._texto = texto
        self.set_active(False)

    def set_active(self, ativo: bool):
        if ativo:
            self.configure(fg_color=T.BLUE, hover_color=T.BLUE_DK, text_color="white")
        else:
            self.configure(fg_color="transparent", hover_color=T.BG_HOVER,
                           text_color=T.TXT_DIM)


class SuiteItem(ctk.CTkFrame):
    """Linha de suíte: badge + nome + contagem + chevron, selecionável."""

    def __init__(self, master, nome: str, n_testes: int, cor: str, on_click: Callable):
        super().__init__(master, corner_radius=T.RADIUS_SM, fg_color="transparent",
                         border_width=1, border_color=T.BG_PANEL)
        self.nome = nome
        self._on_click = on_click

        self._badge = letter_badge(self, nome, cor, size=34)
        self._badge.pack(side="left", padx=(10, 12), pady=10)

        meio = ctk.CTkFrame(self, fg_color="transparent")
        meio.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(meio, text=nome, text_color=T.TXT,
                     font=T.font(13, "bold"), anchor="w").pack(anchor="w")
        ctk.CTkLabel(meio, text=f"{n_testes} teste{'s' if n_testes != 1 else ''}",
                     text_color=T.TXT_MUTED, font=T.font(11), anchor="w").pack(anchor="w")

        self._chevron = ctk.CTkLabel(self, text="›", text_color=T.TXT_MUTED,
                                     font=T.font(18))
        self._chevron.pack(side="right", padx=14)

        for w in (self, meio, self._chevron) + tuple(meio.winfo_children()):
            w.bind("<Button-1>", lambda _e: self._on_click(self.nome))
        self._badge.bind("<Button-1>", lambda _e: self._on_click(self.nome))

    def set_selected(self, sel: bool):
        if sel:
            self.configure(fg_color=T.BG_SEL, border_color=T.BLUE)
            self._chevron.configure(text_color=T.BLUE)
        else:
            self.configure(fg_color="transparent", border_color=T.BG_PANEL)
            self._chevron.configure(text_color=T.TXT_MUTED)
