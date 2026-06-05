# pages/testes.py
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, scrolledtext, messagebox

class PaginaTestes(tk.Frame):
    def __init__(self, parent, config: dict):
        super().__init__(parent, bg="#f0f2f5")
        self.config      = config
        self.mapa_suites = {}
        self.suite_ativa = None
        self.resultados  = []
        self._executando = False
        self._construir()
        self.carregar_suites()

    # ─────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────
    def _construir(self):
        # Header
        hdr = tk.Frame(self, bg="white", pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Executar Scripts", bg="white",
                 font=("Segoe UI", 13, "bold"), fg="#1e293b").pack(side="left", padx=16)
        tk.Button(hdr, text="Recarregar", command=self.carregar_suites,
                  bg="#e8f0fe", fg="#2563eb", relief="flat", padx=10).pack(side="right", padx=12)

        tk.Label(self, text="Suites de Teste:", bg="#f0f2f5",
                 font=("Segoe UI", 9, "bold"), fg="#444").pack(anchor="w", padx=12, pady=(8, 2))

        # Painéis lado a lado
        frame_central = tk.Frame(self, bg="#f0f2f5")
        frame_central.pack(fill="both", expand=True, padx=12)

        frame_esq = tk.Frame(frame_central, bd=1, relief="sunken", bg="white")
        frame_esq.pack(side="left", fill="both", expand=True)
        tk.Label(frame_esq, text="Suite / Teste", font=("Segoe UI", 9, "bold"),
                 bg="#dce8f7", anchor="w", padx=8, pady=4).pack(fill="x")
        self.lista_suites = tk.Listbox(
            frame_esq, selectmode="single", font=("Segoe UI", 10),
            activestyle="none", selectbackground="#1565C0",
            selectforeground="white", cursor="hand2",
            exportselection=False, bd=0)
        self.lista_suites.pack(fill="both", expand=True)
        self.lista_suites.bind("<<ListboxSelect>>", self._ao_selecionar_suite)

        frame_dir = tk.Frame(frame_central, bd=1, relief="sunken", bg="white")
        frame_dir.pack(side="right", fill="both", expand=True, padx=(6, 0))
        tk.Label(frame_dir, text="Testes", font=("Segoe UI", 9, "bold"),
                 bg="#dce8f7", anchor="w", padx=8, pady=4).pack(fill="x")
        self.lista_testes = tk.Listbox(
            frame_dir, selectmode="extended", font=("Segoe UI", 10),
            activestyle="none", selectbackground="#1565C0",
            selectforeground="white", exportselection=False, bd=0)
        self.lista_testes.pack(fill="both", expand=True)

        # Botões — referência salva para poder desabilitar
        frame_botoes = tk.Frame(self, bg="#f0f2f5", pady=6)
        frame_botoes.pack(fill="x", padx=12)

        self.btn_executar_sel = tk.Button(
            frame_botoes, text="Executar Selecionado",
            command=self._executar_selecionado,
            bg="#4CAF50", fg="white", font=("Segoe UI", 9, "bold"),
            relief="flat", padx=10, pady=4)
        self.btn_executar_sel.pack(side="left", padx=(0, 4))

        self.btn_executar_todos = tk.Button(
            frame_botoes, text="Executar Todos",
            command=self._executar_todos,
            bg="#2196F3", fg="white", font=("Segoe UI", 9, "bold"),
            relief="flat", padx=10, pady=4)
        self.btn_executar_todos.pack(side="left")

        tk.Button(frame_botoes, text="Limpar", command=self._limpar_tudo,
                  bg="#f44336", fg="white", relief="flat",
                  padx=10, pady=4).pack(side="right")

        # Notebook de logs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        # Aba Resumo
        frame_resumo = tk.Frame(self.notebook, bg="#1e1e1e")
        self.notebook.add(frame_resumo, text="  Resumo  ")

        frame_cards = tk.Frame(frame_resumo, bg="#1e1e1e", pady=8)
        frame_cards.pack(fill="x", padx=12)
        self.card_total  = self._criar_card(frame_cards, "Total",  "0", "#aaaaaa")
        self.card_passou = self._criar_card(frame_cards, "Passou", "0", "#4CAF50")
        self.card_falhou = self._criar_card(frame_cards, "Falhou", "0", "#f44336")

        frame_tree = tk.Frame(frame_resumo, bg="#1e1e1e")
        frame_tree.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.tree_resumo = ttk.Treeview(frame_tree, columns=("status", "teste"),
                                         show="headings", height=6)
        self.tree_resumo.heading("status", text="Status")
        self.tree_resumo.heading("teste",  text="Teste")
        self.tree_resumo.column("status", width=80,  anchor="center")
        self.tree_resumo.column("teste",  width=400, anchor="w")
        style = ttk.Style()
        style.configure("Treeview", font=("Segoe UI", 9), rowheight=24)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        self.tree_resumo.tag_configure("passou", foreground="#4CAF50", background="#1a2e1a")
        self.tree_resumo.tag_configure("falhou", foreground="#ff5555", background="#2e1a1a")
        scroll_tree = ttk.Scrollbar(frame_tree, orient="vertical", command=self.tree_resumo.yview)
        self.tree_resumo.configure(yscrollcommand=scroll_tree.set)
        self.tree_resumo.pack(side="left", fill="both", expand=True)
        scroll_tree.pack(side="right", fill="y")

        # Aba Falhas
        frame_erros = tk.Frame(self.notebook)
        self.notebook.add(frame_erros, text="  Falhas  ")
        self.log_erros = scrolledtext.ScrolledText(frame_erros, state="disabled",
                                                    bg="#1e1e1e", fg="#ff5555", font=("Courier", 9))
        self.log_erros.pack(fill="both", expand=True)

        # Aba Log Completo
        frame_log = tk.Frame(self.notebook)
        self.notebook.add(frame_log, text="  Log Completo  ")
        self.log_completo = scrolledtext.ScrolledText(frame_log, state="disabled",
                                                       bg="#1e1e1e", fg="#00ff90", font=("Courier", 9))
        self.log_completo.pack(fill="both", expand=True)

    def _criar_card(self, parent, label, valor, cor):
        f = tk.Frame(parent, bg="#2a2a2a", padx=20, pady=8)
        f.pack(side="left", padx=6)
        tk.Label(f, text=label, font=("Segoe UI", 8), bg="#2a2a2a", fg="#aaa").pack()
        lbl = tk.Label(f, text=valor, font=("Segoe UI", 20, "bold"), bg="#2a2a2a", fg=cor)
        lbl.pack()
        return lbl

    # ─────────────────────────────────────────
    # SUITES
    # ─────────────────────────────────────────
    def carregar_suites(self):
        self.lista_suites.delete(0, tk.END)
        self.lista_testes.delete(0, tk.END)
        self.mapa_suites.clear()
        self.suite_ativa = None
        base = self.config.get("base", "")
        if not base or not os.path.isdir(base):
            messagebox.showwarning("Aviso", "Configure o diretorio base em Configuracoes.")
            return
        for pasta in sorted(os.listdir(base)):
            caminho_pasta = os.path.join(base, pasta)
            if not os.path.isdir(caminho_pasta):
                continue
            scripts = [os.path.join(caminho_pasta, f)
                       for f in sorted(os.listdir(caminho_pasta)) if f.endswith(".py")]
            if scripts:
                self.mapa_suites[pasta] = scripts
                self.lista_suites.insert(tk.END, f"  {pasta}")

    def _ao_selecionar_suite(self, event):
        sel = self.lista_suites.curselection()
        if not sel:
            return
        nome = self.lista_suites.get(sel[0]).strip()
        if nome == self.suite_ativa:
            return
        self.suite_ativa = nome
        self.lista_testes.delete(0, tk.END)
        for caminho in self.mapa_suites.get(nome, []):
            self.lista_testes.insert(tk.END, f"  {os.path.basename(caminho)}")

    # ─────────────────────────────────────────
    # EXECUÇÃO
    # ─────────────────────────────────────────
    def _executar_selecionado(self):
        if self._executando:
            messagebox.showwarning("Aviso", "Ja existe um teste em execucao.")
            return
        if not self.suite_ativa:
            messagebox.showwarning("Aviso", "Selecione uma suite primeiro.")
            return
        scripts = self.mapa_suites.get(self.suite_ativa, [])
        indices = self.lista_testes.curselection()
        alvos = [scripts[i] for i in indices] if indices else scripts
        self._rodar_em_thread(alvos)

    def _executar_todos(self):
        if self._executando:
            messagebox.showwarning("Aviso", "Ja existe um teste em execucao.")
            return
        todos = [c for scripts in self.mapa_suites.values() for c in scripts]
        if not todos:
            messagebox.showwarning("Aviso", "Nenhum script encontrado.")
            return
        self._rodar_em_thread(todos)

    def _rodar_em_thread(self, alvos: list):
        self._executando = True
        self._set_botoes_estado("disabled")

        def worker():
            for caminho in alvos:
                self._executar(caminho)
            self.after(0, self._ao_finalizar)

        threading.Thread(target=worker, daemon=True).start()

    def _ao_finalizar(self):
        self._executando = False
        self._set_botoes_estado("normal")
        self._atualizar_cards()

    def _set_botoes_estado(self, estado: str):
        self.btn_executar_sel.config(state=estado)
        self.btn_executar_todos.config(state=estado)

    def _executar(self, caminho):
        nome = os.path.basename(caminho)
        self.after(0, lambda t=f"\n>> Executando: {nome}\n": self._log_completo(t))

        root_dir = Path(__file__).resolve().parent.parent
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        proc = subprocess.Popen(
            [sys.executable, "-u", caminho],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(root_dir),
            env=env,
        )

        buffer: list[str] = []
        if proc.stdout:
            for line in proc.stdout:
                buffer.append(line)
                if len(buffer) >= 15:
                    chunk = "".join(buffer)
                    buffer.clear()
                    self.after(0, lambda c=chunk: self._log_completo(c))
        if buffer:
            self.after(0, lambda c="".join(buffer): self._log_completo(c))

        returncode = proc.wait()
        if returncode == 0:
            self.after(0, lambda t="OK - Concluido\n": self._log_completo(t))
            self.after(0, lambda n=nome: self._registrar_resultado(n, "PASSOU", ""))
        else:
            msg = f"Processo encerrou com codigo {returncode}\n"
            self.after(0, lambda t=f"ERRO:\n{msg}": self._log_completo(t))
            self.after(0, lambda n=nome, e=msg: self._registrar_resultado(n, "FALHOU", e))

    def _registrar_resultado(self, nome: str, status: str, erro: str):
        self.resultados.append({"nome": nome, "status": status})
        tag = "passou" if status == "PASSOU" else "falhou"
        self.tree_resumo.insert("", "end", values=(status, nome), tags=(tag,))
        if status == "FALHOU":
            self._log_erros(nome, erro)
            n = sum(1 for r in self.resultados if r["status"] == "FALHOU")
            self.notebook.tab(1, text=f"  Falhas ({n})  ")

    # ─────────────────────────────────────────
    # LOGS
    # ─────────────────────────────────────────
    def _atualizar_cards(self):
        total  = len(self.resultados)
        passou = sum(1 for r in self.resultados if r["status"] == "PASSOU")
        self.card_total.config(text=str(total))
        self.card_passou.config(text=str(passou))
        self.card_falhou.config(text=str(total - passou))

    def _log_completo(self, texto):
        self.log_completo.config(state="normal")
        self.log_completo.insert(tk.END, texto)
        self.log_completo.see(tk.END)
        self.log_completo.config(state="disabled")

    def _log_erros(self, nome, texto):
        self.log_erros.config(state="normal")
        self.log_erros.insert(tk.END, f"\n{'='*50}\nFALHOU: {nome}\n{'='*50}\n{texto}\n")
        self.log_erros.see(tk.END)
        self.log_erros.config(state="disabled")

    def _limpar_tudo(self):
        self.resultados.clear()
        self.tree_resumo.delete(*self.tree_resumo.get_children())
        self.card_total.config(text="0")
        self.card_passou.config(text="0")
        self.card_falhou.config(text="0")
        self.notebook.tab(1, text="  Falhas  ")
        for log in [self.log_completo, self.log_erros]:
            log.config(state="normal")
            log.delete("1.0", tk.END)
            log.config(state="disabled")