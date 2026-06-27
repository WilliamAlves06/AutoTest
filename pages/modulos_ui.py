"""
pages/modulos_ui.py
Aba "Módulos": cadastra a inicialização de cada módulo do Formula Certa
(exe + sequência de teclas p/ abrir pelo menu) — grava em modulos.json.

Inclui um GRAVADOR DE TECLAS: você aperta as teclas que abre o módulo
(ALT+A, setas, Enter) e o app converte para a sintaxe type_keys automaticamente,
sem precisar conhecer os códigos.
"""

from __future__ import annotations

import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import pythoncom

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fc.modules import info_modulo, listar_modulos, salvar_modulo, remover_modulo

C_BG = "#f0f2f5"
C_WHITE = "white"
C_BLUE = "#2563eb"
C_GREEN = "#4CAF50"
C_RED = "#f44336"
C_PURPLE = "#7c3aed"
C_FONT = ("Segoe UI", 10)
C_MONO = ("Consolas", 10)


class ModulosTab(tk.Frame):
    def __init__(self, parent, config: dict):
        super().__init__(parent, bg=C_BG)
        self.config_data = config
        self._gravando = False
        self._kb_listener = None
        self._mouse_listener = None
        self._mods_pressionados: set = set()

        self._build()
        self._recarregar_lista()

    # ── layout ───────────────────────────────────────────────────
    def _build(self):
        hdr = tk.Frame(self, bg=C_WHITE, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Módulos — inicialização", bg=C_WHITE,
                 font=("Segoe UI", 13, "bold"), fg="#1e293b").pack(side="left", padx=16)
        tk.Label(hdr, text="Cadastre como cada módulo é aberto a partir da tela principal.",
                 bg=C_WHITE, font=("Segoe UI", 9), fg="#666").pack(side="left", padx=4)

        corpo = tk.Frame(self, bg=C_BG)
        corpo.pack(fill="both", expand=True, padx=12, pady=10)

        # ── esquerda: lista de módulos ──
        esq = tk.Frame(corpo, bg=C_WHITE, bd=1, relief="solid")
        esq.pack(side="left", fill="y", padx=(0, 10))
        tk.Label(esq, text="Módulos cadastrados", bg="#dce8f7",
                 font=("Segoe UI", 9, "bold"), anchor="w", padx=8, pady=4).pack(fill="x")
        self.lista = tk.Listbox(esq, width=22, font=C_FONT, activestyle="none",
                                selectbackground=C_BLUE, selectforeground="white",
                                exportselection=False, bd=0)
        self.lista.pack(fill="both", expand=True)
        self.lista.bind("<<ListboxSelect>>", self._ao_selecionar)
        tk.Button(esq, text="+ Novo", bg="#e8f0fe", fg=C_BLUE, relief="flat",
                  cursor="hand2", command=self._novo).pack(fill="x", padx=6, pady=6)

        # ── direita: formulário ──
        dir_ = tk.Frame(corpo, bg=C_WHITE, bd=1, relief="solid")
        dir_.pack(side="left", fill="both", expand=True)

        def campo(label, helper=""):
            tk.Label(dir_, text=label, bg=C_WHITE, font=("Segoe UI", 9, "bold"),
                     fg="#1565C0").pack(anchor="w", padx=16, pady=(12, 2))
            if helper:
                tk.Label(dir_, text=helper, bg=C_WHITE, font=("Segoe UI", 8),
                         fg="#666", justify="left").pack(anchor="w", padx=16)

        campo("Nome do módulo", "Ex.: FCFiliais (sem .exe)")
        self.entry_nome = tk.Entry(dir_, font=C_FONT, relief="solid", bd=1)
        self.entry_nome.pack(fill="x", padx=16, ipady=4)

        campo("Executável (processo)", "Ex.: FCFiliais.exe")
        self.entry_exe = tk.Entry(dir_, font=C_FONT, relief="solid", bd=1)
        self.entry_exe.pack(fill="x", padx=16, ipady=4)

        campo("Passos para abrir (um por linha)",
              "Vazio = só anexa ao processo já aberto. Item de menu por índice (livre de resolução): "
              "@menuitem:i,j. Clique por coordenada (fallback): @click:X,Y. Teclas avulsas (quando o "
              "menu exigir): %a=ALT+A · {DOWN} {RIGHT} · {ENTER} · {DOWN 3}=3x.")
        self.txt_teclas = tk.Text(dir_, font=C_MONO, height=6, relief="solid", bd=1)
        self.txt_teclas.pack(fill="x", padx=16, pady=(0, 4))

        # gravador: clique no item do menu grava @menuitem automaticamente; teclas também são capturadas
        atalhos = tk.Frame(dir_, bg=C_WHITE)
        atalhos.pack(fill="x", padx=16, pady=(0, 6))
        tk.Label(atalhos, text="Mapeamento automático: clique no item do menu durante a gravação.",
                 bg=C_WHITE, font=("Segoe UI", 8), fg="#666").pack(side="left")

        self.btn_gravar = tk.Button(
            atalhos, text="🎬 Gravar teclas/cliques", bg=C_PURPLE, fg=C_WHITE, relief="flat",
            font=("Segoe UI", 8, "bold"), cursor="hand2", command=self._toggle_gravar,
        )
        self.btn_gravar.pack(side="right")

        # ações
        acoes = tk.Frame(dir_, bg=C_WHITE)
        acoes.pack(fill="x", padx=16, pady=12)
        tk.Button(acoes, text="💾 Salvar", bg=C_GREEN, fg=C_WHITE,
                  font=("Segoe UI", 10, "bold"), relief="flat", padx=18, pady=6,
                  cursor="hand2", command=self._salvar).pack(side="left")
        tk.Button(acoes, text="▶ Testar abertura", bg=C_BLUE, fg=C_WHITE,
                  font=("Segoe UI", 9, "bold"), relief="flat", padx=14, pady=6,
                  cursor="hand2", command=self._testar).pack(side="left", padx=8)
        tk.Button(acoes, text="🗑 Remover", bg="#fde8e8", fg=C_RED,
                  font=("Segoe UI", 9, "bold"), relief="flat", padx=14, pady=6,
                  cursor="hand2", command=self._remover).pack(side="left")

        self.lbl_status = tk.Label(dir_, text="", bg=C_WHITE, font=("Segoe UI", 9), fg="#444")
        self.lbl_status.pack(anchor="w", padx=16, pady=(0, 10))

    # ── lista / seleção ──────────────────────────────────────────
    def _recarregar_lista(self):
        self.lista.delete(0, tk.END)
        for nome in listar_modulos():
            self.lista.insert(tk.END, f"  {nome}")

    def _ao_selecionar(self, _evt=None):
        sel = self.lista.curselection()
        if not sel:
            return
        nome = self.lista.get(sel[0]).strip()
        info = info_modulo(nome) or {}
        self._preencher(nome, info.get("exe", ""), info.get("menu", []))

    def _preencher(self, nome, exe, menu):
        self.entry_nome.delete(0, tk.END); self.entry_nome.insert(0, nome)
        self.entry_exe.delete(0, tk.END); self.entry_exe.insert(0, exe)
        self.txt_teclas.delete("1.0", tk.END)
        self.txt_teclas.insert("1.0", "\n".join(menu or []))

    def _novo(self):
        self.lista.selection_clear(0, tk.END)
        self._preencher("", "", [])
        self.entry_nome.focus_set()
        self._status("Novo módulo — preencha e salve.")

    # ── edição de teclas ─────────────────────────────────────────
    def _inserir_token(self, token: str):
        # acrescenta numa nova linha
        atual = self.txt_teclas.get("1.0", tk.END).strip()
        novo = (atual + "\n" + token) if atual else token
        self.txt_teclas.delete("1.0", tk.END)
        self.txt_teclas.insert("1.0", novo)

    def _ler_menu(self) -> list[str]:
        linhas = self.txt_teclas.get("1.0", tk.END).splitlines()
        return [ln.strip() for ln in linhas if ln.strip()]

    # ── salvar / remover / testar ────────────────────────────────
    def _salvar(self):
        nome = self.entry_nome.get().strip()
        exe = self.entry_exe.get().strip()
        if not nome or not exe:
            messagebox.showwarning("Aviso", "Informe o nome do módulo e o executável.", parent=self)
            return
        salvar_modulo(nome, exe, self._ler_menu())
        self._recarregar_lista()
        self._status(f"✓ '{nome}' salvo em modulos.json", ok=True)

    def _remover(self):
        nome = self.entry_nome.get().strip()
        if not nome:
            return
        if not messagebox.askyesno("Remover", f"Remover o módulo '{nome}'?", parent=self):
            return
        remover_modulo(nome)
        self._recarregar_lista()
        self._novo()
        self._status(f"Módulo '{nome}' removido.")

    def _testar(self):
        nome = self.entry_nome.get().strip()
        if not nome:
            messagebox.showwarning("Aviso", "Selecione/preencha um módulo.", parent=self)
            return
        # salva antes para testar exatamente o que está na tela
        self._salvar()
        self._status("Abrindo módulo (login + navegação)...")

        def worker():
            pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
            try:
                from fc import fc
                fc.reset()
                fc.open_module(nome)
                self.after(0, lambda: self._status(f"✓ Módulo '{nome}' abriu com sucesso.", ok=True))
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                self.after(0, lambda: self._status(f"⚠ falhou: {msg[:90]}", erro=True))
            finally:
                pythoncom.CoUninitialize()

        threading.Thread(target=worker, daemon=True).start()

    # ── gravador de teclas + cliques ─────────────────────────────
    def _toggle_gravar(self):
        if not self._gravando:
            try:
                from pynput import keyboard, mouse
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Gravar teclas", f"pynput indisponível: {exc}", parent=self)
                return
            self._mods_pressionados.clear()
            self._kb_listener = keyboard.Listener(
                on_press=self._on_key_press, on_release=self._on_key_release
            )
            self._kb_listener.start()
            self._mouse_listener = mouse.Listener(on_click=self._on_click_rec)
            self._mouse_listener.start()
            self._gravando = True
            self.btn_gravar.config(text="■ Parar gravação", bg=C_RED)
            self._status("Gravando — foque a tela principal; aperte as teclas E/OU CLIQUE no item do menu.")
        else:
            self._parar_gravacao()
            self._status("Gravação encerrada. Revise os passos e salve.")

    def _parar_gravacao(self):
        self._gravando = False
        for attr in ("_kb_listener", "_mouse_listener"):
            try:
                lst = getattr(self, attr)
                if lst is not None:
                    lst.stop()
                    setattr(self, attr, None)
            except Exception:
                pass
        if self.btn_gravar.winfo_exists():
            self.btn_gravar.config(text="🎬 Gravar teclas", bg=C_PURPLE)

    def _on_click_rec(self, x, y, button, pressed):
        """Grava um clique no menu como @menuitem:i,j (índice, livre de resolução).
        Se o clique não cair sobre um item de menu, grava @click:x,y como fallback."""
        if not pressed:
            return
        try:
            from pynput.mouse import Button
            if button != Button.left:
                return
        except Exception:
            pass
        if not self._gravando or self._ponto_e_nosso(x, y):
            return
        passo = self._clique_para_menuitem(int(x), int(y)) or f"@click:{int(x)},{int(y)}"
        self.after(0, lambda t=passo: self._inserir_token(t))

    @staticmethod
    def _clique_para_menuitem(x, y) -> str | None:
        """Descobre o índice do item de menu sob o clique (Win32). API de menu não é
        COM, então funciona direto da thread do pynput."""
        try:
            import ctypes
            from ctypes import wintypes
            import win32gui

            from fc.context import _achar_main_hwnd
            hwnd = _achar_main_hwnd()
            if not hwnd:
                return None
            hmenu = win32gui.GetMenu(hwnd)
            if not hmenu:
                return None

            user32 = ctypes.windll.user32

            def _rect(hm, idx):
                rc = wintypes.RECT()
                if user32.GetMenuItemRect(hwnd, hm, idx, ctypes.byref(rc)):
                    return (rc.left, rc.top, rc.right, rc.bottom)
                return None

            def _dentro(r):
                return r and r[0] <= x <= r[2] and r[1] <= y <= r[3]

            n_top = win32gui.GetMenuItemCount(hmenu)
            for i in range(n_top):
                hsub = win32gui.GetSubMenu(hmenu, i)
                if hsub:
                    for j in range(win32gui.GetMenuItemCount(hsub)):
                        if _dentro(_rect(hsub, j)):
                            return f"@menuitem:{i},{j}"
                if _dentro(_rect(hmenu, i)):
                    return f"@menuitem:{i}"
            return None
        except Exception:
            return None

    @staticmethod
    def _ponto_e_nosso(x, y) -> bool:
        """True se o ponto está sobre a própria janela do app (p/ ignorar na gravação)."""
        try:
            import os
            import win32gui
            import win32process
            hwnd = win32gui.WindowFromPoint((int(x), int(y)))
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return pid == os.getpid()
        except Exception:
            return False

    def _on_key_release(self, key):
        nome = self._nome_modificador(key)
        if nome:
            self._mods_pressionados.discard(nome)

    def _on_key_press(self, key):
        from pynput import keyboard

        modnome = self._nome_modificador(key)
        if modnome:
            self._mods_pressionados.add(modnome)
            return  # modificador sozinho não gera token

        token = self._tecla_para_token(key)
        if token:
            self.after(0, lambda t=token: self._inserir_token(t))

    @staticmethod
    def _nome_modificador(key) -> str | None:
        from pynput import keyboard
        k = key
        if k in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
            return "alt"
        if k in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            return "ctrl"
        if k in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
            return "shift"
        return None

    def _tecla_para_token(self, key) -> str | None:
        from pynput import keyboard

        especiais = {
            keyboard.Key.down: "{DOWN}", keyboard.Key.up: "{UP}",
            keyboard.Key.left: "{LEFT}", keyboard.Key.right: "{RIGHT}",
            keyboard.Key.enter: "{ENTER}", keyboard.Key.tab: "{TAB}",
            keyboard.Key.esc: "{ESC}", keyboard.Key.space: "{SPACE}",
            keyboard.Key.home: "{HOME}", keyboard.Key.end: "{END}",
            keyboard.Key.backspace: "{BACKSPACE}", keyboard.Key.delete: "{DELETE}",
        }
        for i in range(1, 13):
            f = getattr(keyboard.Key, f"f{i}", None)
            if f is not None:
                especiais[f] = "{F%d}" % i

        base = especiais.get(key)
        if base is None:
            # tecla de caractere (inclui Alt+letra, onde key.char pode vir vazio)
            ch = None
            chattr = getattr(key, "char", None)
            if chattr and chattr.isprintable():
                ch = chattr
            else:
                vk = getattr(key, "vk", None)
                if vk is not None:
                    if 65 <= vk <= 90:
                        ch = chr(vk).lower()
                    elif 48 <= vk <= 57:
                        ch = chr(vk)
                    elif 96 <= vk <= 105:  # numpad 0-9
                        ch = chr(vk - 48)
            if not ch:
                return None
            base = ch

        prefixo = ""
        if "alt" in self._mods_pressionados:
            prefixo += "%"
        if "ctrl" in self._mods_pressionados:
            prefixo += "^"
        if "shift" in self._mods_pressionados and len(base) == 1 and base.isalpha():
            prefixo += "+"
        return prefixo + base

    # ── util ─────────────────────────────────────────────────────
    def _status(self, texto, ok=False, erro=False):
        cor = C_GREEN if ok else (C_RED if erro else "#444")
        if self.lbl_status.winfo_exists():
            self.lbl_status.config(text=texto, fg=cor)

    def destroy(self):
        self._parar_gravacao()
        super().destroy()
