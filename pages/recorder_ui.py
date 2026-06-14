"""
pages/recorder_ui.py
Aba "Recorder" para o app.py — painel estilo Cypress com lista de comandos em tempo real.

Layout:
  ┌─ HEADER ──────────────────────────────────────────┐
  │  [● Iniciar]  [■ Parar]  [🗑 Limpar]  Nome: [___] │
  │  Status: ● PARADO  /  ● GRAVANDO — FCProdutos.exe │
  └───────────────────────────────────────────────────┘
  ┌─ PAINEL DE COMANDOS (tempo real) ─────────────────┐
  │  bg #1e1e1e  fg #00ff90  font Courier 9           │
  │  1  safe_click(wait_element(win, ...))             │
  │  2  safe_type(..., "texto digitado")               │
  │  3  ⚠ clique não mapeado (x=412, y=308)           │
  └───────────────────────────────────────────────────┘
  ┌─ RODAPÉ ──────────────────────────────────────────┐
  │  [💾 Exportar .py]    3 ações gravadas            │
  └───────────────────────────────────────────────────┘
"""

from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Optional

from core.config import carregar as carregar_config
from core.recorder.action_detector import ActionDetector, DetectedAction
from core.recorder.codegen import CodeGenerator
from core.recorder.fc_codegen import FCCodeGenerator

# ── Cores (mesmas do app.py) ──────────────────────────────────
C_NAV       = "#1a2235"
C_BG        = "#f0f2f5"
C_BLUE      = "#2563eb"
C_GREEN     = "#4CAF50"
C_RED       = "#f44336"
C_YELLOW    = "#f5a623"
C_WHITE     = "white"
C_PANEL_BG  = "#1e1e1e"
C_PANEL_FG  = "#00ff90"   # verde terminal
C_WARN_FG   = "#f5a623"   # amarelo para não resolvidos
C_INFO_FG   = "#5bc8f5"   # azul claro para eventos de processo
C_FONT      = ("Segoe UI", 10)
C_MONO      = ("Courier", 9)


class RecorderTab(tk.Frame):
    """
    Frame que encapsula toda a UI do Recorder.
    Encaixado como nova aba no app.py via mostrar_recorder().
    """

    def __init__(self, parent, config: dict):
        super().__init__(parent, bg=C_BG)
        self.config_data = config
        self._detector = ActionDetector()
        self._codegen  = CodeGenerator()
        self._fc_codegen = FCCodeGenerator()
        self._usar_fc = tk.BooleanVar(master=self, value=True)  # gerar na DSL fc por padrão
        self._actions: list[DetectedAction] = []
        self._action_count = 0
        self._blink_state  = False
        self._blink_job    = None
        self._drain_job    = None

        self._build_header()
        self._build_assert_bar()
        self._build_panel()
        self._build_footer()

    # ──────────────────────────────────────────────────────────
    # Construção do layout
    # ──────────────────────────────────────────────────────────

    def _build_header(self):
        hdr = tk.Frame(self, bg=C_WHITE, pady=8)
        hdr.pack(fill="x")

        # Botões de controle
        btn_frame = tk.Frame(hdr, bg=C_WHITE)
        btn_frame.pack(side="left", padx=12)

        self.btn_start = tk.Button(
            btn_frame, text="● Iniciar", bg=C_GREEN, fg=C_WHITE,
            font=("Segoe UI", 9, "bold"), relief="flat",
            padx=12, pady=5, cursor="hand2",
            command=self._iniciar,
        )
        self.btn_start.pack(side="left", padx=(0, 6))

        self.btn_stop = tk.Button(
            btn_frame, text="■ Parar", bg="#cccccc", fg="#888888",
            font=("Segoe UI", 9, "bold"), relief="flat",
            padx=12, pady=5, cursor="hand2",
            state="disabled", command=self._parar,
        )
        self.btn_stop.pack(side="left", padx=(0, 6))

        self.btn_clear = tk.Button(
            btn_frame, text="🗑 Limpar", bg="#e8f0fe", fg=C_BLUE,
            font=("Segoe UI", 9), relief="flat",
            padx=10, pady=5, cursor="hand2",
            command=self._limpar,
        )
        self.btn_clear.pack(side="left")

        # Nome do teste
        name_frame = tk.Frame(hdr, bg=C_WHITE)
        name_frame.pack(side="left", padx=20)
        tk.Label(name_frame, text="Nome:", bg=C_WHITE,
                 font=C_FONT, fg="#444").pack(side="left", padx=(0, 6))
        self.entry_name = tk.Entry(
            name_frame, font=C_FONT, bg="#f8f9fb",
            relief="solid", bd=1, width=28
        )
        self.entry_name.insert(0, "Teste_Gravado")
        self.entry_name.pack(side="left", ipady=4)

        # Estilo de saída: DSL fc (recomendado) x legado wait_element
        tk.Checkbutton(
            hdr, text="DSL fc (aliases)", variable=self._usar_fc,
            bg=C_WHITE, fg="#444", font=C_FONT, activebackground=C_WHITE,
            selectcolor=C_BLUE, cursor="hand2", command=self._on_toggle_fc,
        ).pack(side="left", padx=8)

        # Status
        self.lbl_status = tk.Label(
            hdr, text="● PARADO", bg=C_WHITE,
            font=("Segoe UI", 10, "bold"), fg="#999999"
        )
        self.lbl_status.pack(side="right", padx=16)

    def _build_assert_bar(self):
        """Toolbar de verificações (estilo Playwright: tipo + clique no elemento)."""
        bar = tk.Frame(self, bg=C_WHITE)
        bar.pack(fill="x")
        tk.Label(bar, text="Verificações:", bg=C_WHITE, fg="#444",
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(12, 6), pady=6)
        for kind, rotulo in (("visible", "✓ visível"), ("text", "✓ texto"), ("value", "✓ valor")):
            tk.Button(bar, text=rotulo, bg="#eef2ff", fg=C_BLUE, relief="flat",
                      font=("Segoe UI", 9), padx=8, pady=3, cursor="hand2",
                      command=lambda k=kind: self._armar_assert(k)).pack(side="left", padx=3)
        self._assert_hint = tk.Label(
            bar, text="clique num tipo e depois no elemento na tela",
            bg=C_WHITE, fg="#999", font=("Segoe UI", 9))
        self._assert_hint.pack(side="left", padx=10)

    def _armar_assert(self, kind: str):
        if not self._detector.is_running():
            self._assert_hint.config(text="Inicie a gravação antes de adicionar verificação.", fg=C_RED)
            return
        if not self._usar_fc.get():
            self._usar_fc.set(True)   # verificações só geram código no modo DSL fc
        self._detector.arm_assertion(kind)
        rot = {"visible": "visível", "text": "texto", "value": "valor"}[kind]
        self._assert_hint.config(text=f"🎯 agora CLIQUE no elemento para verificar ({rot})...", fg=C_GREEN)

    def _on_toggle_fc(self):
        """Re-renderiza o painel ao alternar entre DSL fc e legado."""
        self.panel.config(state="normal")
        self.panel.delete("1.0", tk.END)
        self.panel.config(state="disabled")
        if self._usar_fc.get():
            self._render_codigo_live()
        else:
            self._action_count = 0
            for a in self._actions:
                self._render_action(a)

    def _render_codigo_live(self):
        """Mostra o teste fc gerado AO VIVO (regenera a cada ação, estilo codegen)."""
        nome = self.entry_name.get().strip() or "Teste_Gravado"
        try:
            codigo = self._fc_codegen.generate(self._actions, nome)
        except Exception as e:  # noqa: BLE001
            codigo = f"# erro ao gerar codigo: {e}"
        self.panel.config(state="normal")
        self.panel.delete("1.0", tk.END)
        self.panel.insert(tk.END, codigo, "normal")
        self.panel.see(tk.END)
        self.panel.config(state="disabled")

    def _build_panel(self):
        """Painel central estilo Cypress — lista de comandos em tempo real."""
        panel_wrapper = tk.Frame(self, bg=C_BG, padx=12, pady=6)
        panel_wrapper.pack(fill="both", expand=True)

        # Label do painel
        tk.Label(
            panel_wrapper, text="Comandos gravados",
            bg=C_BG, font=("Segoe UI", 9, "bold"), fg="#444"
        ).pack(anchor="w", pady=(0, 4))

        # Frame do terminal
        terminal_frame = tk.Frame(panel_wrapper, bg=C_PANEL_BG)
        terminal_frame.pack(fill="both", expand=True)

        # Scrollbar
        scrollbar = tk.Scrollbar(terminal_frame, bg=C_PANEL_BG)
        scrollbar.pack(side="right", fill="y")

        self.panel = tk.Text(
            terminal_frame,
            bg=C_PANEL_BG, fg=C_PANEL_FG,
            font=C_MONO,
            state="disabled",
            relief="flat",
            bd=0,
            padx=12, pady=8,
            cursor="arrow",
            yscrollcommand=scrollbar.set,
            selectbackground="#2563eb",
        )
        self.panel.pack(fill="both", expand=True)
        scrollbar.config(command=self.panel.yview)

        # Tags de cor para diferentes tipos de linha
        self.panel.tag_config("normal",   foreground=C_PANEL_FG)
        self.panel.tag_config("warning",  foreground=C_WARN_FG)
        self.panel.tag_config("info",     foreground=C_INFO_FG)
        self.panel.tag_config("comment",  foreground="#666666")

        # Mensagem inicial
        self._write_panel(
            "  Clique em Iniciar para gravar.\n"
            "  Clique na janela do Fcerta ANTES de Alt+A, setas e Enter.\n"
            "  Com 'DSL fc' ligado: a exportação gera fc.field/fc.button por alias\n"
            "  e registra campos novos nos mappings automaticamente.\n",
            tag="comment"
        )

    def _build_footer(self):
        footer = tk.Frame(self, bg=C_WHITE, pady=8)
        footer.pack(fill="x", side="bottom")

        self.btn_export = tk.Button(
            footer, text="💾 Exportar .py",
            bg=C_BLUE, fg=C_WHITE,
            font=("Segoe UI", 9, "bold"), relief="flat",
            padx=14, pady=5, cursor="hand2",
            command=self._exportar,
        )
        self.btn_export.pack(side="left", padx=12)

        self.lbl_count = tk.Label(
            footer, text="0 ações gravadas",
            bg=C_WHITE, font=C_FONT, fg="#666"
        )
        self.lbl_count.pack(side="left", padx=8)

    # ──────────────────────────────────────────────────────────
    # Controles
    # ──────────────────────────────────────────────────────────

    def _iniciar(self):
        if self._detector.is_running():
            return
        try:
            self._detector.start()
        except RuntimeError as e:
            messagebox.showerror("Erro", str(e))
            return

        self.btn_start.config(state="disabled", bg="#cccccc", fg="#888888")
        self.btn_stop.config(state="normal", bg=C_RED, fg=C_WHITE)
        self._set_status_gravando()
        self._write_panel("\n", tag="comment")
        self._write_panel("  --- gravacao iniciada ---\n", tag="comment")
        self._schedule_drain()

    def _parar(self):
        if not self._detector.is_running():
            return
        self._detector.stop()

        self.btn_start.config(state="normal", bg=C_GREEN, fg=C_WHITE)
        self.btn_stop.config(state="disabled", bg="#cccccc", fg="#888888")
        self._set_status_parado()

        if self._blink_job:
            self.after_cancel(self._blink_job)
            self._blink_job = None
        if self._drain_job:
            self.after_cancel(self._drain_job)
            self._drain_job = None
        for action in self._detector.drain_queue():
            self._handle_action(action)

        # Cliques em campo levam ~0,18 s para resolver (espera do foco) e podem
        # terminar logo após o Parar — captura essas ações em atraso.
        self.after(350, self._drain_final)

        self._write_panel("  --- gravacao encerrada ---\n", tag="comment")

    def _drain_final(self):
        """Drena ações que ainda estavam resolvendo quando a gravação parou."""
        for action in self._detector.drain_queue():
            self._handle_action(action)

    def _limpar(self):
        self._actions.clear()
        self._action_count = 0
        self.panel.config(state="normal")
        self.panel.delete("1.0", tk.END)
        self.panel.config(state="disabled")
        self._write_panel(
            "  Clique em Iniciar para gravar.\n"
            "  Preferir Tab, Enter e Espaco.\n",
            tag="comment"
        )
        self.lbl_count.config(text="0 ações gravadas")

    def _exportar(self):
        test_name = self.entry_name.get().strip() or "Teste_Gravado"
        cfg = carregar_config()
        cfg.update(self.config_data)
        output_dir = Path(
            cfg.get("recorder", {}).get(
                "output_dir",
                os.path.join(
                    os.path.dirname(cfg.get("base", "flows")),
                    "flows", "Gravados"
                )
            )
        )

        try:
            if self._usar_fc.get():
                path = self._fc_codegen.save(
                    actions=self._actions,
                    test_name=test_name,
                    output_dir=output_dir,
                    persistir_aliases=True,
                )
                novos = self._fc_codegen.novos_aliases
                resumo = ""
                if novos:
                    linhas = [
                        f"  • {mod}: {', '.join(e['alias'] for e in els)}"
                        for mod, els in novos.items()
                    ]
                    resumo = "\n\nAliases novos registrados nos mappings:\n" + "\n".join(linhas)
                messagebox.showinfo(
                    "Exportado (DSL fc)",
                    f"Teste salvo em:\n{path}{resumo}",
                )
            else:
                path = self._codegen.save(
                    actions=self._actions,
                    test_name=test_name,
                    output_dir=output_dir,
                    config=cfg,
                )
                messagebox.showinfo("Exportado com sucesso", f"Script salvo em:\n{path}")
        except Exception as e:
            messagebox.showerror("Erro ao exportar", str(e))

    def _schedule_drain(self):
        if not self._detector.is_running():
            return
        for action in self._detector.drain_queue():
            self._handle_action(action)
        self._drain_job = self.after(50, self._schedule_drain)

    def _handle_action(self, action: DetectedAction):
        self._actions.append(action)
        if action.action_type == "assert":
            self._assert_hint.config(text="✓ verificação adicionada", fg=C_BLUE)
        if self._usar_fc.get():
            self._render_codigo_live()
        else:
            self._render_action(action)
        self._atualizar_contador()

    def _atualizar_contador(self):
        n = len([a for a in self._actions if a.action_type != "process_changed"])
        self.lbl_count.config(text=f"{n} ação{'ões' if n != 1 else ''} gravada{'s' if n != 1 else ''}")

    def _render_action(self, action: DetectedAction):
        """Atualiza o painel na thread principal do Tkinter."""
        self._action_count += 1

        line = action.to_display_line(self._action_count)

        # Escolher cor da linha
        if action.action_type == "process_changed":
            tag = "info"
        elif not action.resolved and action.action_type == "click":
            tag = "warning"
        elif action.action_type == "special_key":
            tag = "normal"
        elif action.action_type == "type" and action.element and action.element.is_resolved():
            tag = "normal"
        else:
            tag = "normal"

        self._write_panel(f"{line}\n", tag=tag)

        # Atualizar contador no rodapé
        n = len([a for a in self._actions if a.action_type != "process_changed"])
        self.lbl_count.config(text=f"{n} ação{'ões' if n != 1 else ''} gravada{'s' if n != 1 else ''}")

    # ──────────────────────────────────────────────────────────
    # Helpers de UI
    # ──────────────────────────────────────────────────────────

    def _write_panel(self, text: str, tag: str = "normal"):
        self.panel.config(state="normal")
        self.panel.insert(tk.END, text, tag)
        self.panel.see(tk.END)
        self.panel.config(state="disabled")

    def _set_status_gravando(self):
        processo = self._detector._current_process or "..."
        self.lbl_status.config(
            text=f"● GRAVANDO — {processo}",
            fg=C_GREEN,
        )
        self._blink()

    def _set_status_parado(self):
        self.lbl_status.config(text="● PARADO", fg="#999999")

    def _blink(self):
        """Faz o status piscar enquanto está gravando."""
        if not self._detector.is_running():
            return
        self._blink_state = not self._blink_state
        cor = C_GREEN if self._blink_state else "#1a6630"
        processo = self._detector._current_process or "..."
        self.lbl_status.config(
            text=f"● GRAVANDO — {processo}",
            fg=cor,
        )
        self._blink_job = self.after(600, self._blink)