"""
ui/dashboard_testes.py — tela "Execução de Testes" (CustomTkinter).

Reproduz o mockup do QA Studio: cabeçalho + busca, 4 cards de métrica, painel de
suítes (esquerda) e painel de resultados com abas (direita) + barra de ações.
A lógica de descoberta/execução reaproveita o padrão do pages/testes.py (subprocess).
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import customtkinter as ctk

from ui import theme as T
from ui.widgets import StatCard, SuiteItem, pill

_ROOT = Path(__file__).resolve().parent.parent
# Cores rotativas para os badges das suítes.
_CORES_SUITE = ["#3b82f6", "#a855f7", "#f59e0b", "#10b981", "#ef4444", "#06b6d4"]


class DashboardTestes(ctk.CTkFrame):
    def __init__(self, master, config: dict):
        super().__init__(master, fg_color=T.BG_APP)
        self.config_data = config or {}
        self._suites: dict[str, list[str]] = {}
        self._itens: dict[str, SuiteItem] = {}
        self._suite_sel: str | None = None
        self._resultados: list[dict] = []
        self._executando = False
        self._tab = "resumo"

        self._build_header()
        self._build_stats()
        self._build_body()
        self._build_actionbar()
        self.carregar_suites()

    # ── HEADER ───────────────────────────────────────────────────
    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(20, 8))

        esq = ctk.CTkFrame(hdr, fg_color="transparent")
        esq.pack(side="left")
        ctk.CTkLabel(esq, text="Execução de Testes", text_color=T.TXT,
                     font=T.font(22, "bold")).pack(anchor="w")
        ctk.CTkLabel(esq, text="Selecione suítes e rode seus fluxos automatizados",
                     text_color=T.TXT_DIM, font=T.font(12)).pack(anchor="w")

        # Avatar
        inicial = (self.config_data.get("login") or "W")[:1].upper()
        ctk.CTkLabel(hdr, text=inicial, text_color="white", fg_color=T.PURPLE,
                     corner_radius=T.RADIUS_PILL, width=40, height=40,
                     font=T.font(14, "bold")).pack(side="right", padx=(12, 0))

        ctk.CTkButton(hdr, text="↻  Recarregar", command=self.carregar_suites,
                      corner_radius=T.RADIUS_SM, height=40, width=120,
                      fg_color=T.BLUE_TINT, hover_color=T.BG_SEL, text_color=T.BLUE,
                      font=T.font(12, "bold")).pack(side="right", padx=8)

        self._busca = ctk.CTkEntry(hdr, placeholder_text="🔍  Buscar teste...",
                                   width=230, height=40, corner_radius=T.RADIUS_SM,
                                   fg_color=T.BG_PANEL, border_color=T.BORDER,
                                   text_color=T.TXT)
        self._busca.pack(side="right")
        self._busca.bind("<KeyRelease>", lambda _e: self._render_suites())

    # ── STAT CARDS ───────────────────────────────────────────────
    def _build_stats(self):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=8)
        for i in range(4):
            row.grid_columnconfigure(i, weight=1, uniform="stat")

        self.card_total = StatCard(row, "Total", T.TXT, "#cbd5e1")
        self.card_passou = StatCard(row, "Passou", T.GREEN, T.GREEN)
        self.card_falhou = StatCard(row, "Falhou", T.RED, T.RED)
        self.card_taxa = StatCard(row, "Taxa de sucesso", T.BLUE, T.BLUE)
        for i, c in enumerate((self.card_total, self.card_passou, self.card_falhou, self.card_taxa)):
            c.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 12, 0))

        self.card_total.set(0, "fluxos na suíte")
        self.card_passou.set(0, "")
        self.card_falhou.set(0, "")
        self.card_taxa.set("0%", "aguardando execução")

    # ── BODY (suítes + resultados) ───────────────────────────────
    def _build_body(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=8)
        body.grid_columnconfigure(0, weight=2, uniform="b")
        body.grid_columnconfigure(1, weight=3, uniform="b")
        body.grid_rowconfigure(0, weight=1)

        # ----- Painel de suítes -----
        painel_s = ctk.CTkFrame(body, corner_radius=T.RADIUS, fg_color=T.BG_PANEL,
                                border_width=1, border_color=T.BORDER)
        painel_s.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        cab = ctk.CTkFrame(painel_s, fg_color="transparent")
        cab.pack(fill="x", padx=16, pady=(14, 6))
        ctk.CTkLabel(cab, text="Suítes de Teste", text_color=T.TXT,
                     font=T.font(14, "bold")).pack(side="left")
        self._lbl_qtd_suites = ctk.CTkLabel(cab, text="0 suítes", text_color=T.TXT_DIM,
                                            fg_color=T.BG_PANEL_2, corner_radius=T.RADIUS_PILL,
                                            font=T.font(11), padx=10, pady=2)
        self._lbl_qtd_suites.pack(side="right")

        self._lista_suites = ctk.CTkScrollableFrame(painel_s, fg_color="transparent")
        self._lista_suites.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        # ----- Painel de resultados -----
        painel_r = ctk.CTkFrame(body, corner_radius=T.RADIUS, fg_color=T.BG_PANEL,
                                border_width=1, border_color=T.BORDER)
        painel_r.grid(row=0, column=1, sticky="nsew")

        abas = ctk.CTkFrame(painel_r, fg_color="transparent")
        abas.pack(fill="x", padx=16, pady=(12, 4))
        self._botoes_aba: dict[str, ctk.CTkButton] = {}
        for chave, rotulo in (("resumo", "Resumo"), ("falhas", "Falhas"), ("log", "Log completo")):
            b = ctk.CTkButton(abas, text=rotulo, width=10, height=28,
                              corner_radius=T.RADIUS_SM, fg_color="transparent",
                              hover_color=T.BG_HOVER, text_color=T.TXT_DIM,
                              font=T.font(12, "bold"), command=lambda c=chave: self._set_tab(c))
            b.pack(side="left", padx=(0, 4))
            self._botoes_aba[chave] = b

        # Tabela (resumo/falhas)
        self._tabela = ctk.CTkScrollableFrame(painel_r, fg_color="transparent")
        self._tabela.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        # Log (oculto até a aba Log)
        self._log = ctk.CTkTextbox(painel_r, fg_color=T.BG_APP, text_color="#9be7c4",
                                   font=("Consolas", 11), border_width=0)

        self._set_tab("resumo")

    # ── BARRA DE AÇÕES ───────────────────────────────────────────
    def _build_actionbar(self):
        bar = ctk.CTkFrame(self, corner_radius=T.RADIUS, fg_color=T.BG_PANEL,
                           border_width=1, border_color=T.BORDER)
        bar.pack(fill="x", padx=24, pady=(4, 18))

        self.btn_sel = ctk.CTkButton(bar, text="▶  Executar selecionados",
                                     command=self._executar_selecionados,
                                     corner_radius=T.RADIUS_SM, height=42, width=210,
                                     fg_color=T.BLUE, hover_color=T.BLUE_DK,
                                     font=T.font(13, "bold"))
        self.btn_sel.pack(side="left", padx=(14, 8), pady=12)

        self.btn_todos = ctk.CTkButton(bar, text="Executar todos",
                                       command=self._executar_todos,
                                       corner_radius=T.RADIUS_SM, height=42, width=140,
                                       fg_color=T.BG_PANEL_2, hover_color=T.BG_HOVER,
                                       text_color=T.TXT, font=T.font(13))
        self.btn_todos.pack(side="left")

        self._lbl_info = ctk.CTkLabel(bar, text="nenhuma suíte selecionada",
                                      text_color=T.TXT_MUTED, font=T.font(12))
        self._lbl_info.pack(side="left", padx=16)

        ctk.CTkButton(bar, text="Limpar", command=self._limpar,
                      corner_radius=T.RADIUS_SM, height=42, width=90,
                      fg_color=T.BG_PANEL_2, hover_color=T.BG_HOVER,
                      text_color=T.TXT_DIM, font=T.font(13)).pack(side="right", padx=14)

    # ── SUÍTES ───────────────────────────────────────────────────
    def carregar_suites(self):
        self._suites.clear()
        base = self.config_data.get("base", "")
        if base and os.path.isdir(base):
            for pasta in sorted(os.listdir(base)):
                caminho = os.path.join(base, pasta)
                if not os.path.isdir(caminho):
                    continue
                scripts = [os.path.join(caminho, f) for f in sorted(os.listdir(caminho))
                           if f.endswith(".py") and not f.startswith("__")]
                if scripts:
                    self._suites[pasta] = scripts
        self._render_suites()
        total = sum(len(v) for v in self._suites.values())
        self.card_total.set(total, "fluxos na suíte")

    def _render_suites(self):
        for w in self._lista_suites.winfo_children():
            w.destroy()
        self._itens.clear()

        termo = (self._busca.get() or "").strip().lower() if hasattr(self, "_busca") else ""
        nomes = [n for n in self._suites if termo in n.lower()]

        self._lbl_qtd_suites.configure(text=f"{len(nomes)} suíte{'s' if len(nomes) != 1 else ''}")
        for i, nome in enumerate(nomes):
            item = SuiteItem(self._lista_suites, nome, len(self._suites[nome]),
                             _CORES_SUITE[i % len(_CORES_SUITE)], self._select_suite)
            item.pack(fill="x", pady=3, padx=4)
            self._itens[nome] = item
            if nome == self._suite_sel:
                item.set_selected(True)

    def _select_suite(self, nome: str):
        self._suite_sel = nome
        for n, item in self._itens.items():
            item.set_selected(n == nome)
        n = len(self._suites.get(nome, []))
        self._lbl_info.configure(text=f"1 suíte selecionada · {n} teste{'s' if n != 1 else ''}")

    # ── EXECUÇÃO ─────────────────────────────────────────────────
    def _executar_selecionados(self):
        if self._executando:
            return
        if not self._suite_sel:
            self._lbl_info.configure(text="selecione uma suíte primeiro", text_color=T.RED)
            return
        self._rodar(self._suites.get(self._suite_sel, []), self._suite_sel)

    def _executar_todos(self):
        if self._executando:
            return
        alvos = [(c, s) for s, scripts in self._suites.items() for c in scripts]
        self._rodar([c for c, _ in alvos], None, pares=alvos)

    def _rodar(self, scripts: list[str], modulo: str | None, pares=None):
        if not scripts:
            return
        self._executando = True
        self.btn_sel.configure(state="disabled")
        self.btn_todos.configure(state="disabled")
        alvos = pares if pares is not None else [(c, modulo or self._suite_sel) for c in scripts]

        def worker():
            for caminho, mod in alvos:
                self._exec_one(caminho, mod)
            self.after(0, self._ao_finalizar)

        threading.Thread(target=worker, daemon=True).start()

    def _exec_one(self, caminho: str, modulo: str | None):
        nome = os.path.splitext(os.path.basename(caminho))[0]
        inicio = time.time()
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        try:
            proc = subprocess.run(
                [sys.executable, "-u", caminho],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="replace", cwd=str(_ROOT), env=env, timeout=600,
            )
            saida, rc = proc.stdout, proc.returncode
        except Exception as exc:  # noqa: BLE001
            saida, rc = f"{type(exc).__name__}: {exc}", 1
        dur = time.time() - inicio
        status = "PASS" if rc == 0 else "FAIL"
        self.after(0, lambda: self._registrar(nome, modulo or "—", status, dur, saida or ""))

    def _registrar(self, nome, modulo, status, dur, log):
        self._resultados.append({"nome": nome, "modulo": modulo, "status": status,
                                 "dur": dur, "log": log})
        self._render_tabela()
        self._append_log(f"\n>> {modulo}/{nome}  [{status}]  {dur:.1f}s\n{log}\n")
        self._atualizar_stats()

    def _ao_finalizar(self):
        self._executando = False
        self.btn_sel.configure(state="normal")
        self.btn_todos.configure(state="normal")

    def _limpar(self):
        self._resultados.clear()
        self._render_tabela()
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")
        self._atualizar_stats()

    # ── MÉTRICAS / TABELA ────────────────────────────────────────
    def _atualizar_stats(self):
        total = len(self._resultados)
        passou = sum(1 for r in self._resultados if r["status"] == "PASS")
        falhou = total - passou
        taxa = f"{round(passou / total * 100)}%" if total else "0%"
        falhas_mods = ", ".join(sorted({r["modulo"] for r in self._resultados if r["status"] == "FAIL"}))
        self.card_passou.set(passou, "")
        self.card_falhou.set(falhou, falhas_mods)
        self.card_taxa.set(taxa, "última execução" if total else "aguardando execução")
        self._botoes_aba["falhas"].configure(text=f"Falhas  {falhou}" if falhou else "Falhas")

    def _set_tab(self, chave: str):
        self._tab = chave
        for k, b in self._botoes_aba.items():
            ativo = k == chave
            b.configure(fg_color=T.BG_PANEL_2 if ativo else "transparent",
                        text_color=T.TXT if ativo else T.TXT_DIM)
        if chave == "log":
            self._tabela.pack_forget()
            self._log.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        else:
            self._log.pack_forget()
            self._tabela.pack(fill="both", expand=True, padx=12, pady=(4, 12))
            self._render_tabela()

    def _render_tabela(self):
        for w in self._tabela.winfo_children():
            w.destroy()

        # cabeçalho
        head = ctk.CTkFrame(self._tabela, fg_color="transparent")
        head.pack(fill="x", pady=(0, 6))
        for txt, w in (("STATUS", 90), ("TESTE", 240), ("MÓDULO", 130), ("DURAÇÃO", 90)):
            ctk.CTkLabel(head, text=txt, text_color=T.TXT_MUTED, font=T.font(10, "bold"),
                         width=w, anchor="w").pack(side="left")

        linhas = self._resultados
        if self._tab == "falhas":
            linhas = [r for r in linhas if r["status"] == "FAIL"]

        if not linhas:
            ctk.CTkLabel(self._tabela, text="Nenhum resultado ainda — rode uma suíte.",
                         text_color=T.TXT_MUTED, font=T.font(12)).pack(anchor="w", pady=16)
            return

        for r in linhas:
            row = ctk.CTkFrame(self._tabela, fg_color="transparent")
            row.pack(fill="x", pady=2)
            cel = ctk.CTkFrame(row, fg_color="transparent", width=90)
            cel.pack(side="left")
            cel.pack_propagate(False)
            pill(cel, r["status"], r["status"]).pack(side="left")
            ctk.CTkLabel(row, text=r["nome"], text_color=T.TXT, font=T.font(12),
                         width=240, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=r["modulo"], text_color=T.TXT_DIM, font=T.font(12),
                         width=130, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=f"{r['dur']:.1f}s", text_color=T.TXT_DIM, font=T.font(12),
                         width=90, anchor="w").pack(side="left")

    def _append_log(self, texto: str):
        self._log.configure(state="normal")
        self._log.insert("end", texto)
        self._log.see("end")
        self._log.configure(state="disabled")
