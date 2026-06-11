"""
ui/config_page.py — tela de Configurações (CustomTkinter), tema escuro.

Edita caminhos (base, exe, recorder) e credenciais. Salva via core.config.salvar_config,
que grava os caminhos no config.json e roteia login/senha para o .env (sem versionar segredo).
"""

from __future__ import annotations

from tkinter import filedialog

import customtkinter as ctk

from core.config import carregar_config, salvar_config
from ui import theme as T


class ConfigPage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=T.BG_APP)
        self.cfg = carregar_config()
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Configurações", text_color=T.TXT,
                     font=T.font(22, "bold")).pack(anchor="w", padx=24, pady=(20, 2))
        ctk.CTkLabel(self, text="Caminhos do projeto e credenciais (segredos vão para o .env)",
                     text_color=T.TXT_DIM, font=T.font(12)).pack(anchor="w", padx=24, pady=(0, 12))

        card = ctk.CTkFrame(self, corner_radius=T.RADIUS, fg_color=T.BG_PANEL,
                            border_width=1, border_color=T.BORDER)
        card.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        self.e_base = self._campo(card, "Diretório base dos testes",
                                  self.cfg.get("base", ""), procurar="pasta")
        self.e_exe = self._campo(card, "Executável do sistema (fcerta.exe)",
                                 self.cfg.get("exe_path", r"C:\Fcerta\fcerta.exe"), procurar="arquivo")
        self.e_rec = self._campo(card, "Recorder — pasta de saída",
                                 self.cfg.get("recorder", {}).get("output_dir", "flows/Gravados"),
                                 procurar="pasta")

        cred = ctk.CTkFrame(card, fg_color="transparent")
        cred.pack(fill="x", padx=20, pady=(8, 4))
        self.e_login = self._campo(cred, "Login", self.cfg.get("login", ""), inline=True)
        self.e_senha = self._campo(cred, "Senha", self.cfg.get("senha", ""),
                                   inline=True, secret=True)

        rodape = ctk.CTkFrame(card, fg_color="transparent")
        rodape.pack(fill="x", padx=20, pady=18)
        ctk.CTkButton(rodape, text="Salvar", command=self._salvar, corner_radius=T.RADIUS_SM,
                      height=40, width=120, fg_color=T.BLUE, hover_color=T.BLUE_DK,
                      font=T.font(13, "bold")).pack(side="left")
        self._toast = ctk.CTkLabel(rodape, text="", text_color=T.GREEN, font=T.font(12))
        self._toast.pack(side="left", padx=14)

    def _campo(self, master, rotulo, valor, procurar=None, inline=False, secret=False):
        wrap = ctk.CTkFrame(master, fg_color="transparent")
        wrap.pack(side="left" if inline else "top", fill="x", expand=inline,
                  padx=(0 if inline else 20, 12 if inline else 20), pady=(10, 0))
        ctk.CTkLabel(wrap, text=rotulo, text_color=T.TXT_DIM,
                     font=T.font(11, "bold")).pack(anchor="w", pady=(0, 4))
        linha = ctk.CTkFrame(wrap, fg_color="transparent")
        linha.pack(fill="x")
        entry = ctk.CTkEntry(linha, height=38, corner_radius=T.RADIUS_SM, fg_color=T.BG_PANEL_2,
                             border_color=T.BORDER, text_color=T.TXT,
                             show="•" if secret else "")
        entry.pack(side="left", fill="x", expand=True)
        entry.insert(0, valor or "")
        if procurar:
            ctk.CTkButton(linha, text="Procurar", width=88, height=38, corner_radius=T.RADIUS_SM,
                          fg_color=T.BG_PANEL_2, hover_color=T.BG_HOVER, text_color=T.BLUE,
                          command=lambda: self._procurar(entry, procurar)).pack(side="left", padx=(8, 0))
        return entry

    def _procurar(self, entry, tipo):
        caminho = filedialog.askdirectory() if tipo == "pasta" else filedialog.askopenfilename()
        if caminho:
            entry.delete(0, "end")
            entry.insert(0, caminho)

    def _salvar(self):
        cfg = carregar_config()
        cfg["base"] = self.e_base.get().strip()
        cfg["exe_path"] = self.e_exe.get().strip()
        cfg.setdefault("recorder", {})["output_dir"] = self.e_rec.get().strip()
        cfg["login"] = self.e_login.get().strip()
        cfg["senha"] = self.e_senha.get()
        salvar_config(cfg)
        self._toast.configure(text="✓ Configurações salvas")
        self.after(2500, lambda: self._toast.configure(text=""))
