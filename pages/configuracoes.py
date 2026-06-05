import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from core.config import salvar_config

class PaginaConfiguracoes(tk.Frame):
    def __init__(self, parent, config: dict, on_salvar):
        super().__init__(parent, bg="#f0f2f5")
        self.config   = config
        self.on_salvar = on_salvar  # callback para avisar o app.py
        self._construir()

    def _construir(self):
        # Header
        hdr = tk.Frame(self, bg="white", pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Configuracoes", bg="white",
                 font=("Segoe UI", 13, "bold"), fg="#1e293b").pack(side="left", padx=16)

        # Card
        card = tk.Frame(self, bg="white", bd=1, relief="solid")
        card.pack(fill="both", expand=True, padx=16, pady=12)

        # ── Diretório Base ──
        tk.Label(card, text="Diretorio Base", bg="white",
                 font=("Segoe UI", 10, "bold"), fg="#1565C0").pack(anchor="w", padx=16, pady=(16, 4))
        ttk.Separator(card, orient="horizontal").pack(fill="x", padx=16)

        tk.Label(card, text="Caminho da pasta raiz dos testes",
                 bg="white", font=("Segoe UI", 9), fg="#666").pack(anchor="w", padx=16, pady=(8, 2))

        frame_base = tk.Frame(card, bg="white")
        frame_base.pack(fill="x", padx=16, pady=(0, 12))

        self.entry_base = tk.Entry(frame_base, font=("Segoe UI", 10),
                                    bg="#f8f9fb", relief="solid", bd=1)
        self.entry_base.pack(side="left", fill="x", expand=True, ipady=5)
        self.entry_base.insert(0, self.config.get("base", ""))

        tk.Button(frame_base, text="Procurar", bg="#e8f0fe", fg="#2563eb",
                  relief="flat", padx=10, cursor="hand2",
                  command=self._procurar_pasta).pack(side="left", padx=(6, 0), ipady=5)

        # ── Credenciais ──
        tk.Label(card, text="Credenciais", bg="white",
                 font=("Segoe UI", 10, "bold"), fg="#1565C0").pack(anchor="w", padx=16, pady=(8, 4))
        ttk.Separator(card, orient="horizontal").pack(fill="x", padx=16)

        frame_cred = tk.Frame(card, bg="white")
        frame_cred.pack(fill="x", padx=16, pady=(12, 0))

        # Login
        fl = tk.Frame(frame_cred, bg="white")
        fl.pack(side="left", fill="x", expand=True, padx=(0, 12))
        tk.Label(fl, text="Login", bg="white", font=("Segoe UI", 9), fg="#444").pack(anchor="w", pady=(0, 4))
        self.entry_login = tk.Entry(fl, font=("Segoe UI", 10), bg="#f8f9fb", relief="solid", bd=1)
        self.entry_login.pack(fill="x", ipady=5)
        self.entry_login.insert(0, self.config.get("login", ""))

        # Senha
        fs = tk.Frame(frame_cred, bg="white")
        fs.pack(side="left", fill="x", expand=True)
        tk.Label(fs, text="Senha", bg="white", font=("Segoe UI", 9), fg="#444").pack(anchor="w", pady=(0, 4))
        self.entry_senha = tk.Entry(fs, font=("Segoe UI", 10), bg="#f8f9fb",
                                     relief="solid", bd=1, show="*")
        self.entry_senha.pack(fill="x", ipady=5)
        self.entry_senha.insert(0, self.config.get("senha", ""))

        # Botões
        frame_btns = tk.Frame(card, bg="white")
        frame_btns.pack(anchor="w", padx=16, pady=20)

        tk.Button(frame_btns, text="Salvar", bg="#2563eb", fg="white",
                  font=("Segoe UI", 10, "bold"), relief="flat", padx=16, pady=6,
                  cursor="hand2", command=self._salvar).pack(side="left", padx=(0, 8))

        tk.Button(frame_btns, text="Cancelar", bg="white", fg="#555",
                  font=("Segoe UI", 10), relief="solid", bd=1, padx=16, pady=6,
                  cursor="hand2", command=lambda: self.on_salvar(salvo=False)).pack(side="left")

    def _procurar_pasta(self):
        pasta = filedialog.askdirectory()
        if pasta:
            self.entry_base.delete(0, tk.END)
            self.entry_base.insert(0, pasta)

    def _salvar(self):
        self.config["base"]  = self.entry_base.get().strip()
        self.config["login"] = self.entry_login.get().strip()
        self.config["senha"] = self.entry_senha.get()
        salvar_config(self.config)
        messagebox.showinfo("Sucesso", "Configuracoes salvas!")
        self.on_salvar(salvo=True)