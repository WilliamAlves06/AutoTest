import os
import json
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog

CONFIG_FILE = "config.json"

def carregar_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"base": "", "login": "", "senha": ""}

def salvar_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Executar Scripts Python")
        self.root.geometry("960x650")
        self.root.configure(bg="#1a2235")
        self.config = carregar_config()
        self.mapa_suites = {}
        self.suite_ativa = None
        self.resultados = []
        self.tela_ativa = None
        self.construir_layout()
        self.mostrar_testes()

    # ─────────────────────────────────────────
    # LAYOUT BASE
    # ─────────────────────────────────────────
    def construir_layout(self):
        # Navbar lateral
        self.nav = tk.Frame(self.root, bg="#1a2235", width=150)
        self.nav.pack(side="left", fill="y")
        self.nav.pack_propagate(False)

        tk.Label(self.nav, text="MENU", bg="#1a2235", fg="#7a8fa6",
                 font=("Segoe UI", 9, "bold")).pack(pady=(16, 8))

        self.btn_testes = self._nav_btn("Testes", "ti-player-play", self.mostrar_testes)
        self.btn_config = self._nav_btn("Configuracoes", "ti-settings", self.mostrar_config)

        tk.Label(self.nav, text="v1.0", bg="#1a2235", fg="#3a4a5a",
                 font=("Segoe UI", 8)).pack(side="bottom", pady=10)

        # Área de conteúdo
        self.frame_conteudo = tk.Frame(self.root, bg="#f0f2f5")
        self.frame_conteudo.pack(side="left", fill="both", expand=True)

    def _nav_btn(self, texto, icone, comando):
        btn = tk.Button(
            self.nav, text=f"  {texto}",
            bg="#1a2235", fg="#7a8fa6", activebackground="#2563eb",
            activeforeground="white", relief="flat", anchor="w",
            font=("Segoe UI", 10), cursor="hand2",
            command=comando, padx=16, pady=10
        )
        btn.pack(fill="x", padx=8, pady=2)
        return btn

    def _nav_ativo(self, btn_ativo):
        for btn in [self.btn_testes, self.btn_config]:
            btn.config(bg="#1a2235", fg="#7a8fa6")
        btn_ativo.config(bg="#2563eb", fg="white")

    def _limpar_conteudo(self):
        for w in self.frame_conteudo.winfo_children():
            w.destroy()

    # ─────────────────────────────────────────
    # TELA: TESTES
    # ─────────────────────────────────────────
    def mostrar_testes(self):
        self._nav_ativo(self.btn_testes)
        self._limpar_conteudo()
        self.tela_ativa = "testes"

        # Header
        hdr = tk.Frame(self.frame_conteudo, bg="white", pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Executar Scripts", bg="white",
                 font=("Segoe UI", 13, "bold"), fg="#1e293b").pack(side="left", padx=16)
        tk.Button(hdr, text="Recarregar", command=self.carregar_suites,
                  bg="#e8f0fe", fg="#2563eb", relief="flat", padx=10).pack(side="right", padx=12)

        tk.Label(self.frame_conteudo, text="Suites de Teste:", bg="#f0f2f5",
                 font=("Segoe UI", 9, "bold"), fg="#444").pack(anchor="w", padx=12, pady=(8, 2))

        # Painéis
        frame_central = tk.Frame(self.frame_conteudo, bg="#f0f2f5")
        frame_central.pack(fill="both", expand=True, padx=12)

        frame_esq = tk.Frame(frame_central, bd=1, relief="sunken", bg="white")
        frame_esq.pack(side="left", fill="both", expand=True)
        tk.Label(frame_esq, text="Suite / Teste", font=("Segoe UI", 9, "bold"),
                 bg="#dce8f7", anchor="w", padx=8, pady=4).pack(fill="x")
        self.lista_suites = tk.Listbox(frame_esq, selectmode="single", font=("Segoe UI", 10),
                                        activestyle="none", selectbackground="#1565C0",
                                        selectforeground="white", cursor="hand2",
                                        exportselection=False, bd=0)
        self.lista_suites.pack(fill="both", expand=True)
        self.lista_suites.bind("<<ListboxSelect>>", self.ao_selecionar_suite)

        frame_dir = tk.Frame(frame_central, bd=1, relief="sunken", bg="white")
        frame_dir.pack(side="right", fill="both", expand=True, padx=(6, 0))
        tk.Label(frame_dir, text="Testes", font=("Segoe UI", 9, "bold"),
                 bg="#dce8f7", anchor="w", padx=8, pady=4).pack(fill="x")
        self.lista_testes = tk.Listbox(frame_dir, selectmode="extended", font=("Segoe UI", 10),
                                        activestyle="none", selectbackground="#1565C0",
                                        selectforeground="white", exportselection=False, bd=0)
        self.lista_testes.pack(fill="both", expand=True)

        # Botões
        frame_botoes = tk.Frame(self.frame_conteudo, bg="#f0f2f5", pady=6)
        frame_botoes.pack(fill="x", padx=12)
        tk.Button(frame_botoes, text="Executar Selecionado", command=self.executar_selecionado,
                  bg="#4CAF50", fg="white", font=("Segoe UI", 9, "bold"),
                  relief="flat", padx=10, pady=4).pack(side="left", padx=(0, 4))
        tk.Button(frame_botoes, text="Executar Todos", command=self.executar_todos,
                  bg="#2196F3", fg="white", font=("Segoe UI", 9, "bold"),
                  relief="flat", padx=10, pady=4).pack(side="left")
        tk.Button(frame_botoes, text="Limpar", command=self.limpar_tudo,
                  bg="#f44336", fg="white", relief="flat", padx=10, pady=4).pack(side="right")

        # Notebook de logs
        self.notebook = ttk.Notebook(self.frame_conteudo)
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
        self.tree_resumo.column("status", width=80, anchor="center")
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

        self.carregar_suites()

    def _criar_card(self, parent, label, valor, cor):
        f = tk.Frame(parent, bg="#2a2a2a", padx=20, pady=8)
        f.pack(side="left", padx=6)
        tk.Label(f, text=label, font=("Segoe UI", 8), bg="#2a2a2a", fg="#aaa").pack()
        lbl = tk.Label(f, text=valor, font=("Segoe UI", 20, "bold"), bg="#2a2a2a", fg=cor)
        lbl.pack()
        return lbl

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

    def ao_selecionar_suite(self, event):
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

    def executar_selecionado(self):
        if not self.suite_ativa:
            messagebox.showwarning("Aviso", "Selecione uma suite primeiro.")
            return
        scripts = self.mapa_suites.get(self.suite_ativa, [])
        indices = self.lista_testes.curselection()
        alvos = [scripts[i] for i in indices] if indices else scripts
        for c in alvos:
            self.executar(c)
        self.atualizar_cards()

    def executar_todos(self):
        todos = [c for scripts in self.mapa_suites.values() for c in scripts]
        if not todos:
            messagebox.showwarning("Aviso", "Nenhum script encontrado.")
            return
        for c in todos:
            self.executar(c)
        self.atualizar_cards()

    def executar(self, caminho):
        nome = os.path.basename(caminho)
        self.escrever_log_completo(f"\n>> Executando: {nome}\n")
        res = subprocess.run([sys.executable, caminho], capture_output=True,
                             text=True, encoding="utf-8", errors="replace")
        ok = res.returncode == 0
        if res.stdout:
            self.escrever_log_completo(res.stdout)
        if ok:
            self.escrever_log_completo("OK - Concluido\n")
            self.resultados.append({"nome": nome, "status": "PASSOU"})
            self.tree_resumo.insert("", "end", values=("PASSOU", nome), tags=("passou",))
        else:
            self.escrever_log_completo(f"ERRO:\n{res.stderr}\n")
            self.resultados.append({"nome": nome, "status": "FALHOU"})
            self.tree_resumo.insert("", "end", values=("FALHOU", nome), tags=("falhou",))
            self.escrever_log_erros(nome, res.stderr)
            self.notebook.tab(1, text=f"  Falhas ({sum(1 for r in self.resultados if r['status']=='FALHOU')})  ")

    def atualizar_cards(self):
        total  = len(self.resultados)
        passou = sum(1 for r in self.resultados if r["status"] == "PASSOU")
        self.card_total.config(text=str(total))
        self.card_passou.config(text=str(passou))
        self.card_falhou.config(text=str(total - passou))

    def escrever_log_completo(self, texto):
        self.log_completo.config(state="normal")
        self.log_completo.insert(tk.END, texto)
        self.log_completo.see(tk.END)
        self.log_completo.config(state="disabled")

    def escrever_log_erros(self, nome, texto):
        self.log_erros.config(state="normal")
        self.log_erros.insert(tk.END, f"\n{'='*50}\nFALHOU: {nome}\n{'='*50}\n{texto}\n")
        self.log_erros.see(tk.END)
        self.log_erros.config(state="disabled")

    def limpar_tudo(self):
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

    # ─────────────────────────────────────────
    # TELA: CONFIGURAÇÕES
    # ─────────────────────────────────────────
    def mostrar_config(self):
        self._nav_ativo(self.btn_config)
        self._limpar_conteudo()
        self.tela_ativa = "config"

        # Header
        hdr = tk.Frame(self.frame_conteudo, bg="white", pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Configuracoes", bg="white",
                 font=("Segoe UI", 13, "bold"), fg="#1e293b").pack(side="left", padx=16)

        # Card principal
        card = tk.Frame(self.frame_conteudo, bg="white", bd=1, relief="solid")
        card.pack(fill="both", expand=True, padx=16, pady=12)

        # ── Seção: Diretório Base ──
        tk.Label(card, text="Diretorio Base", bg="white",
                 font=("Segoe UI", 10, "bold"), fg="#1565C0").pack(anchor="w", padx=16, pady=(16, 4))
        ttk.Separator(card, orient="horizontal").pack(fill="x", padx=16)

        tk.Label(card, text="Caminho da pasta raiz dos testes",
                 bg="white", font=("Segoe UI", 9), fg="#666").pack(anchor="w", padx=16, pady=(8, 2))

        frame_base = tk.Frame(card, bg="white")
        frame_base.pack(fill="x", padx=16, pady=(0, 12))

        self.entry_base = tk.Entry(frame_base, font=("Segoe UI", 10), bg="#f8f9fb",
                                    relief="solid", bd=1)
        self.entry_base.pack(side="left", fill="x", expand=True, ipady=5)
        self.entry_base.insert(0, self.config.get("base", ""))

        tk.Button(frame_base, text="Procurar", bg="#e8f0fe", fg="#2563eb",
                  relief="flat", padx=10, cursor="hand2",
                  command=self.procurar_pasta).pack(side="left", padx=(6, 0), ipady=5)

        # ── Seção: Credenciais ──
        tk.Label(card, text="Credenciais", bg="white",
                 font=("Segoe UI", 10, "bold"), fg="#1565C0").pack(anchor="w", padx=16, pady=(8, 4))
        ttk.Separator(card, orient="horizontal").pack(fill="x", padx=16)

        frame_cred = tk.Frame(card, bg="white")
        frame_cred.pack(fill="x", padx=16, pady=(12, 0))

        # Login
        frame_login = tk.Frame(frame_cred, bg="white")
        frame_login.pack(side="left", fill="x", expand=True, padx=(0, 12))
        tk.Label(frame_login, text="Login", bg="white",
                 font=("Segoe UI", 9), fg="#444").pack(anchor="w", pady=(0, 4))
        self.entry_login = tk.Entry(frame_login, font=("Segoe UI", 10), bg="#f8f9fb",
                                     relief="solid", bd=1)
        self.entry_login.pack(fill="x", ipady=5)
        self.entry_login.insert(0, self.config.get("login", ""))

        # Senha
        frame_senha = tk.Frame(frame_cred, bg="white")
        frame_senha.pack(side="left", fill="x", expand=True)
        tk.Label(frame_senha, text="Senha", bg="white",
                 font=("Segoe UI", 9), fg="#444").pack(anchor="w", pady=(0, 4))
        self.entry_senha = tk.Entry(frame_senha, font=("Segoe UI", 10), bg="#f8f9fb",
                                     relief="solid", bd=1, show="*")
        self.entry_senha.pack(fill="x", ipady=5)
        self.entry_senha.insert(0, self.config.get("senha", ""))

        # Botões salvar/cancelar
        frame_btns = tk.Frame(card, bg="white")
        frame_btns.pack(anchor="w", padx=16, pady=20)

        tk.Button(frame_btns, text="Salvar", bg="#2563eb", fg="white",
                  font=("Segoe UI", 10, "bold"), relief="flat", padx=16, pady=6,
                  cursor="hand2", command=self.salvar_configuracao).pack(side="left", padx=(0, 8))

        tk.Button(frame_btns, text="Cancelar", bg="white", fg="#555",
                  font=("Segoe UI", 10), relief="solid", bd=1, padx=16, pady=6,
                  cursor="hand2", command=self.mostrar_testes).pack(side="left")

    def procurar_pasta(self):
        pasta = filedialog.askdirectory()
        if pasta:
            self.entry_base.delete(0, tk.END)
            self.entry_base.insert(0, pasta)

    def salvar_configuracao(self):
        self.config["base"]  = self.entry_base.get().strip()
        self.config["login"] = self.entry_login.get().strip()
        self.config["senha"] = self.entry_senha.get()
        salvar_config(self.config)
        messagebox.showinfo("Sucesso", "Configuracoes salvas!")
        self.mostrar_testes()


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()