"""
ui/app_shell.py — janela principal do AutoTest QA Studio (CustomTkinter).

Menu lateral + área de conteúdo que troca de tela. A tela de Testes e a de
Configurações são nativas do novo tema; Recorder/Mapear/Módulos são as telas
existentes (tk) hospedadas aqui — funcionam normalmente e serão re-estilizadas
de forma incremental.
"""

from __future__ import annotations

import customtkinter as ctk

from core.config import carregar_config
from ui import theme as T
from ui.config_page import ConfigPage
from ui.dashboard_testes import DashboardTestes
from ui.widgets import SidebarButton

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

_NAV = [
    ("testes", "🧪", "Testes"),
    ("recorder", "⏺", "Recorder"),
    ("mapear", "🎯", "Mapear"),
    ("modulos", "▦", "Módulos"),
    ("config", "⚙", "Configurações"),
]


class StudioApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AutoTest — QA Studio")
        self.geometry("1280x820")
        self.minsize(1100, 720)
        self.configure(fg_color=T.BG_APP)

        self._cfg = carregar_config()
        self._recorder_tab = None
        self._botoes: dict[str, SidebarButton] = {}

        self._build_sidebar()
        self._content = ctk.CTkFrame(self, fg_color=T.BG_APP)
        self._content.pack(side="left", fill="both", expand=True)

        self.mostrar("testes")

    # ── SIDEBAR ──────────────────────────────────────────────────
    def _build_sidebar(self):
        bar = ctk.CTkFrame(self, width=210, corner_radius=0, fg_color=T.BG_SIDEBAR)
        bar.pack(side="left", fill="y")
        bar.pack_propagate(False)

        # Logo
        logo = ctk.CTkFrame(bar, fg_color="transparent")
        logo.pack(fill="x", padx=16, pady=(18, 14))
        ctk.CTkLabel(logo, text="A", text_color="white", fg_color=T.BLUE,
                     corner_radius=T.RADIUS_SM, width=38, height=38,
                     font=T.font(18, "bold")).pack(side="left")
        txt = ctk.CTkFrame(logo, fg_color="transparent")
        txt.pack(side="left", padx=10)
        ctk.CTkLabel(txt, text="AutoTest", text_color=T.TXT,
                     font=T.font(15, "bold")).pack(anchor="w")
        ctk.CTkLabel(txt, text="QA Studio", text_color=T.TXT_MUTED,
                     font=T.font(11)).pack(anchor="w")

        ctk.CTkLabel(bar, text="MENU", text_color=T.TXT_MUTED,
                     font=T.font(10, "bold")).pack(anchor="w", padx=22, pady=(6, 4))

        for chave, icone, rotulo in _NAV:
            b = SidebarButton(bar, icone, rotulo, lambda c=chave: self.mostrar(c))
            b.pack(fill="x", padx=12, pady=2)
            self._botoes[chave] = b

        # Rodapé: status do sistema + versão
        rod = ctk.CTkFrame(bar, fg_color="transparent")
        rod.pack(side="bottom", fill="x", padx=14, pady=14)
        status = ctk.CTkFrame(rod, fg_color=T.BG_PANEL, corner_radius=T.RADIUS_SM,
                              border_width=1, border_color=T.BORDER)
        status.pack(fill="x")
        ctk.CTkLabel(status, text="●  FórmulaCerta 6.0", text_color=T.GREEN,
                     font=T.font(11, "bold")).pack(side="left", padx=10, pady=8)
        ctk.CTkLabel(rod, text="v2.0", text_color=T.TXT_MUTED,
                     font=T.font(10)).pack(anchor="w", pady=(6, 0))

    # ── NAVEGAÇÃO ────────────────────────────────────────────────
    def mostrar(self, chave: str):
        self._parar_recorder_se_ativo()
        for k, b in self._botoes.items():
            b.set_active(k == chave)
        for w in self._content.winfo_children():
            w.destroy()
        self._recorder_tab = None

        self._cfg = carregar_config()
        try:
            construtor = getattr(self, f"_tela_{chave}")
            construtor()
        except Exception as exc:  # noqa: BLE001
            self._erro_tela(chave, exc)

    def _tela_testes(self):
        DashboardTestes(self._content, self._cfg).pack(fill="both", expand=True)

    def _tela_config(self):
        ConfigPage(self._content).pack(fill="both", expand=True)

    def _tela_recorder(self):
        from pages.recorder_ui import RecorderTab
        self._recorder_tab = RecorderTab(self._content, self._cfg)
        self._recorder_tab.pack(fill="both", expand=True)

    def _tela_mapear(self):
        from pages.mapear_ui import MapearTab
        MapearTab(self._content, self._cfg).pack(fill="both", expand=True)

    def _tela_modulos(self):
        from pages.modulos_ui import ModulosTab
        ModulosTab(self._content, self._cfg).pack(fill="both", expand=True)

    def _erro_tela(self, chave: str, exc: Exception):
        ctk.CTkLabel(
            self._content,
            text=f"Não foi possível abrir '{chave}':\n{type(exc).__name__}: {exc}",
            text_color=T.RED, font=T.font(13), justify="left",
        ).pack(padx=30, pady=30, anchor="w")

    def _parar_recorder_se_ativo(self):
        tab = self._recorder_tab
        if tab is not None and hasattr(tab, "_detector"):
            try:
                if tab._detector.is_running():
                    tab._parar()
            except Exception:
                pass


def main():
    StudioApp().mainloop()


if __name__ == "__main__":
    main()
