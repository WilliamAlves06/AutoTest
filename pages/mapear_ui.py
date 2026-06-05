"""
pages/mapear_ui.py
Aba para mapear controles de uma janela Delphi e exibir o caminho do JSON gerado.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.mapear_janela import mapear_janela, resolver_entrada_mapeamento

C_BG = "#f0f2f5"
C_WHITE = "white"
C_BLUE = "#2563eb"
C_GREEN = "#4CAF50"
C_RED = "#f44336"
C_PANEL_BG = "#1e1e1e"
C_PANEL_FG = "#00ff90"
C_FONT = ("Segoe UI", 10)
C_MONO = ("Courier", 9)

_MODULOS_RAPIDOS = (
    ("FCFiliais", "FCFiliais.exe", "regex:.*Filiais.*"),
    ("FCReceitas", "FCReceitas.exe", "regex:.*Receitas.*"),
    ("FCProdutos", "FCProdutos.exe", ""),
    ("Login", "", "FórmulaCerta Autenticação de Usuário"),
)


class MapearTab(tk.Frame):
    """Interface para executar mapear_janela() e mostrar onde o JSON foi salvo."""

    def __init__(self, parent, config: dict):
        super().__init__(parent, bg=C_BG)
        self.config_data = config
        self._rodando = False
        self._ultimo_json: Path | None = None

        self._build_form()
        self._build_resultado()
        self._build_log()

    def _build_form(self):
        hdr = tk.Frame(self, bg=C_WHITE, pady=10)
        hdr.pack(fill="x")
        tk.Label(
            hdr,
            text="Mapear janela",
            bg=C_WHITE,
            font=("Segoe UI", 13, "bold"),
            fg="#1e293b",
        ).pack(side="left", padx=16)

        card = tk.Frame(self, bg=C_WHITE, bd=1, relief="solid")
        card.pack(fill="x", padx=16, pady=(0, 8))

        tk.Label(
            card,
            text="Processo do modulo (opcional) — nome no Gerenciador de Tarefas",
            bg=C_WHITE,
            font=("Segoe UI", 9, "bold"),
            fg="#1565C0",
        ).pack(anchor="w", padx=16, pady=(12, 4))

        row_proc = tk.Frame(card, bg=C_WHITE)
        row_proc.pack(fill="x", padx=16, pady=(0, 8))
        self.entry_processo = tk.Entry(
            row_proc, font=C_FONT, bg="#f8f9fb", relief="solid", bd=1
        )
        self.entry_processo.pack(side="left", fill="x", expand=True, ipady=6)
        self.entry_processo.insert(0, "")

        tk.Label(
            card,
            text="Titulo da janela (opcional) — barra de titulo; regex:... para padrao",
            bg=C_WHITE,
            font=("Segoe UI", 9, "bold"),
            fg="#1565C0",
        ).pack(anchor="w", padx=16, pady=(4, 4))

        row_titulo = tk.Frame(card, bg=C_WHITE)
        row_titulo.pack(fill="x", padx=16, pady=(0, 8))
        self.entry_titulo = tk.Entry(
            row_titulo, font=C_FONT, bg="#f8f9fb", relief="solid", bd=1
        )
        self.entry_titulo.pack(side="left", fill="x", expand=True, ipady=6)

        tk.Label(
            card,
            text="Atalhos de modulos:",
            bg=C_WHITE,
            font=("Segoe UI", 8),
            fg="#666",
        ).pack(anchor="w", padx=16)
        row_atalhos = tk.Frame(card, bg=C_WHITE)
        row_atalhos.pack(fill="x", padx=16, pady=(4, 8))
        for label, processo, titulo in _MODULOS_RAPIDOS:
            tk.Button(
                row_atalhos,
                text=label,
                bg="#e8f0fe",
                fg=C_BLUE,
                relief="flat",
                font=("Segoe UI", 8),
                cursor="hand2",
                command=lambda p=processo, t=titulo: self._definir_atalho(p, t),
            ).pack(side="left", padx=(0, 4), pady=2)

        row_opts = tk.Frame(card, bg=C_WHITE)
        row_opts.pack(fill="x", padx=16, pady=(0, 8))

        self.var_ocultos = tk.BooleanVar(value=True)
        tk.Checkbutton(
            row_opts,
            text="Incluir abas ocultas",
            variable=self.var_ocultos,
            bg=C_WHITE,
            font=C_FONT,
            activebackground=C_WHITE,
        ).pack(side="left")

        tk.Label(row_opts, text="Timeout conexao (s):", bg=C_WHITE, font=C_FONT).pack(
            side="left", padx=(16, 6)
        )
        self.spin_timeout = tk.Spinbox(
            row_opts,
            from_=5,
            to=300,
            width=6,
            font=C_FONT,
            relief="solid",
            bd=1,
        )
        self.spin_timeout.delete(0, tk.END)
        self.spin_timeout.insert(0, "30")
        self.spin_timeout.pack(side="left")

        self.btn_mapear = tk.Button(
            card,
            text="Mapear agora",
            bg=C_GREEN,
            fg=C_WHITE,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
            command=self._iniciar_mapeamento,
        )
        self.btn_mapear.pack(anchor="w", padx=16, pady=(8, 8))

        tk.Label(
            card,
            text=(
                "FCFiliais.exe = processo no Gerenciador de Tarefas; "
                "titulo = barra da janela (ex.: FórmulaCerta - Filiais).\n"
                "Telas grandes podem levar 1-3 minutos — acompanhe o log abaixo."
            ),
            bg=C_WHITE,
            font=("Segoe UI", 8),
            fg="#666",
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 12))

    def _build_resultado(self):
        res = tk.Frame(self, bg=C_WHITE, bd=1, relief="solid")
        res.pack(fill="x", padx=16, pady=8)

        tk.Label(
            res,
            text="Arquivo JSON gerado",
            bg=C_WHITE,
            font=("Segoe UI", 10, "bold"),
            fg="#1565C0",
        ).pack(anchor="w", padx=16, pady=(12, 4))

        row_path = tk.Frame(res, bg=C_WHITE)
        row_path.pack(fill="x", padx=16, pady=(0, 8))

        self.entry_path = tk.Entry(
            row_path,
            font=C_MONO,
            bg="#f8f9fb",
            relief="solid",
            bd=1,
            state="readonly",
            readonlybackground="#f8f9fb",
        )
        self.entry_path.pack(side="left", fill="x", expand=True, ipady=6)

        self.lbl_resumo = tk.Label(
            res,
            text="Nenhum mapeamento executado ainda.",
            bg=C_WHITE,
            font=C_FONT,
            fg="#444",
        )
        self.lbl_resumo.pack(anchor="w", padx=16, pady=(0, 8))

        row_btns = tk.Frame(res, bg=C_WHITE)
        row_btns.pack(anchor="w", padx=16, pady=(0, 16))

        self.btn_abrir_pasta = tk.Button(
            row_btns,
            text="Abrir pasta output",
            bg="#e8f0fe",
            fg=C_BLUE,
            relief="flat",
            padx=12,
            pady=5,
            cursor="hand2",
            state="disabled",
            command=self._abrir_pasta,
        )
        self.btn_abrir_pasta.pack(side="left", padx=(0, 8))

        self.btn_abrir_arquivo = tk.Button(
            row_btns,
            text="Abrir JSON",
            bg="#e8f0fe",
            fg=C_BLUE,
            relief="flat",
            padx=12,
            pady=5,
            cursor="hand2",
            state="disabled",
            command=self._abrir_arquivo,
        )
        self.btn_abrir_arquivo.pack(side="left", padx=(0, 8))

        self.btn_copiar = tk.Button(
            row_btns,
            text="Copiar caminho",
            bg="#e8f0fe",
            fg=C_BLUE,
            relief="flat",
            padx=12,
            pady=5,
            cursor="hand2",
            state="disabled",
            command=self._copiar_caminho,
        )
        self.btn_copiar.pack(side="left")

    def _build_log(self):
        tk.Label(
            self,
            text="Log",
            bg=C_BG,
            font=("Segoe UI", 9, "bold"),
            fg="#444",
        ).pack(anchor="w", padx=16, pady=(4, 2))

        self.log = scrolledtext.ScrolledText(
            self,
            height=10,
            state="disabled",
            bg=C_PANEL_BG,
            fg=C_PANEL_FG,
            font=C_MONO,
        )
        self.log.pack(fill="both", expand=True, padx=16, pady=(0, 12))

    def _definir_atalho(self, processo: str, titulo: str) -> None:
        self.entry_processo.delete(0, tk.END)
        self.entry_processo.insert(0, processo)
        self.entry_titulo.delete(0, tk.END)
        self.entry_titulo.insert(0, titulo)

    def _append_log(self, texto: str) -> None:
        self.log.config(state="normal")
        self.log.insert(tk.END, texto)
        self.log.see(tk.END)
        self.log.config(state="disabled")

    def _on_progress(self, msg: str) -> None:
        self.after(0, lambda m=msg: self._append_log(f"{m}\n"))

    def _set_path_readonly(self, caminho: str) -> None:
        self.entry_path.config(state="normal")
        self.entry_path.delete(0, tk.END)
        self.entry_path.insert(0, caminho)
        self.entry_path.config(state="readonly")

    def _iniciar_mapeamento(self) -> None:
        if self._rodando:
            messagebox.showwarning("Aviso", "Mapeamento em andamento.")
            return

        processo = self.entry_processo.get().strip() or None
        titulo = self.entry_titulo.get().strip() or None

        if not processo and not titulo:
            messagebox.showwarning(
                "Aviso",
                "Informe o processo do modulo (ex.: FCFiliais.exe) "
                "ou o titulo da janela.",
            )
            return

        try:
            timeout = float(self.spin_timeout.get())
        except ValueError:
            messagebox.showwarning("Aviso", "Timeout invalido.")
            return

        exe_path = self.config_data.get("exe_path", "").strip() or None
        incluir_ocultos = self.var_ocultos.get()

        try:
            titulo, processo = resolver_entrada_mapeamento(titulo, processo)
        except ValueError as exc:
            messagebox.showwarning("Entrada invalida", str(exc))
            return

        self._rodando = True
        self.btn_mapear.config(state="disabled", text="Mapeando...")
        proc_log = processo or "(fcerta.exe)"
        tit_log = titulo or "(janela principal / top_window)"
        self._append_log(f"\n--- Mapeando ---\n")
        self._append_log(f"Processo: {proc_log}\n")
        self._append_log(f"Titulo: {tit_log}\n")

        def worker():
            try:
                out_path = mapear_janela(
                    titulo,
                    processo=processo,
                    exe_path=exe_path,
                    timeout_janela=timeout,
                    incluir_ocultos=incluir_ocultos,
                    on_progress=self._on_progress,
                )
                abs_path = out_path.resolve()
                with open(abs_path, encoding="utf-8") as f:
                    total = len(json.load(f))
                self.after(0, lambda: self._on_sucesso(abs_path, total))
            except Exception as exc:
                self.after(0, lambda: self._on_erro(str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_sucesso(self, path: Path, total: int) -> None:
        self._rodando = False
        self.btn_mapear.config(state="normal", text="Mapear agora")
        self._ultimo_json = path

        caminho_str = str(path)
        self._set_path_readonly(caminho_str)
        self.lbl_resumo.config(
            text=f"{total} elementos exportados.",
            fg=C_GREEN,
        )
        for btn in (self.btn_abrir_pasta, self.btn_abrir_arquivo, self.btn_copiar):
            btn.config(state="normal")

        self._append_log(f"OK — {total} elementos\n")
        self._append_log(f"JSON: {caminho_str}\n")

        messagebox.showinfo(
            "Mapeamento concluido",
            f"{total} elementos mapeados.\n\nArquivo salvo em:\n{caminho_str}",
        )

    def _on_erro(self, mensagem: str) -> None:
        self._rodando = False
        self.btn_mapear.config(state="normal", text="Mapear agora")
        self.lbl_resumo.config(text="Falha no mapeamento.", fg=C_RED)
        self._append_log(f"ERRO: {mensagem}\n")
        messagebox.showerror("Erro no mapeamento", mensagem)

    def _abrir_pasta(self) -> None:
        pasta = self._ultimo_json.parent if self._ultimo_json else ROOT / "output"
        pasta.mkdir(parents=True, exist_ok=True)
        os.startfile(str(pasta))

    def _abrir_arquivo(self) -> None:
        if self._ultimo_json and self._ultimo_json.exists():
            os.startfile(str(self._ultimo_json))

    def _copiar_caminho(self) -> None:
        if not self._ultimo_json:
            return
        self.clipboard_clear()
        self.clipboard_append(str(self._ultimo_json.resolve()))
        messagebox.showinfo("Copiado", "Caminho copiado para a area de transferencia.")
