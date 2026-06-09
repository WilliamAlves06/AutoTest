"""
pages/mapear_ui.py
Aba para mapear controles de uma janela Delphi e exibir o caminho do JSON gerado.
"""

from __future__ import annotations

import json
import os
import queue
import re
import sys
import threading
import tkinter as tk
import unicodedata
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, simpledialog

import pythoncom
from loguru import logger

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.mapear_janela import mapear_janela, resolver_entrada_mapeamento
from fc.mapping_store import salvar_mapa, caminho_mapa

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
        self._last_processo: str | None = None
        self._last_titulo: str | None = None
        self._last_exe: str | None = None

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

        row_acoes = tk.Frame(card, bg=C_WHITE)
        row_acoes.pack(anchor="w", fill="x", padx=16, pady=(8, 8))

        self.btn_mapear = tk.Button(
            row_acoes,
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
        self.btn_mapear.pack(side="left")

        self.btn_editar_salvo = tk.Button(
            row_acoes,
            text="📂 Editar alias-map salvo",
            bg=C_BLUE,
            fg=C_WHITE,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=16,
            pady=8,
            cursor="hand2",
            command=self._abrir_map_existente,
        )
        self.btn_editar_salvo.pack(side="left", padx=(8, 0))

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
        self.btn_copiar.pack(side="left", padx=(0, 8))

        self.btn_aliases = tk.Button(
            row_btns,
            text="Editar aliases →",
            bg=C_GREEN,
            fg=C_WHITE,
            relief="flat",
            padx=12,
            pady=5,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
            state="disabled",
            command=self._abrir_editor_aliases,
        )
        self.btn_aliases.pack(side="left")

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

        # guarda os parâmetros exatos do mapeamento p/ o editor reler posições ao vivo
        self._last_processo = processo
        self._last_titulo = titulo
        self._last_exe = exe_path

        self._rodando = True
        self.btn_mapear.config(state="disabled", text="Mapeando...")
        proc_log = processo or "(fcerta.exe)"
        tit_log = titulo or "(janela principal / top_window)"
        self._append_log(f"\n--- Mapeando ---\n")
        self._append_log(f"Processo: {proc_log}\n")
        self._append_log(f"Titulo: {tit_log}\n")

        def worker():
            # pywinauto/comtypes so inicializam o COM na thread que faz o import
            # (a thread principal). Sem isso aqui, chamadas profundas de travessia
            # da arvore UIA (descendants/children em paineis aninhados) falham com
            # erros COM silenciosamente engolidos, truncando o mapeamento.
            pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
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
                mensagem = str(exc)
                self.after(0, lambda: self._on_erro(mensagem))
            finally:
                pythoncom.CoUninitialize()

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
        for btn in (self.btn_abrir_pasta, self.btn_abrir_arquivo, self.btn_copiar, self.btn_aliases):
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

    def _abrir_editor_aliases(self) -> None:
        if not self._ultimo_json or not self._ultimo_json.exists():
            messagebox.showwarning("Aviso", "Mapeie uma janela primeiro.")
            return
        try:
            elementos = json.loads(self._ultimo_json.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro", f"Falha ao ler o JSON: {exc}")
            return

        # Sugestões de módulo/janela a partir do que foi mapeado.
        proc = (self._last_processo or self.entry_processo.get().strip() or "")
        modulo_sug = proc[:-4] if proc.lower().endswith(".exe") else proc
        janela_sug = (self._last_titulo or self.entry_titulo.get().strip() or "")
        if janela_sug.lower().startswith("regex:"):
            janela_sug = janela_sug[6:].strip(". *")
        AliasEditorWindow(
            self, elementos, modulo_sug, janela_sug,
            processo=self._last_processo,
            titulo_busca=self._last_titulo,
            exe_path=self._last_exe,
        )

    def _abrir_map_existente(self) -> None:
        """Abre um alias-map já salvo (mappings/<Módulo>/<Janela>.json) para editar."""
        from fc import mapping_store

        mapping_store.MAPPINGS_DIR.mkdir(parents=True, exist_ok=True)
        caminho = filedialog.askopenfilename(
            title="Abrir alias-map salvo",
            initialdir=str(mapping_store.MAPPINGS_DIR),
            filetypes=[("Alias-map JSON", "*.json"), ("Todos", "*.*")],
        )
        if not caminho:
            return

        try:
            dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro", f"Falha ao ler o alias-map: {exc}")
            return

        if not isinstance(dados, dict) or "elements" not in dados:
            messagebox.showerror(
                "Formato inválido",
                "Este arquivo não parece um alias-map (esperado {module, window, elements}).",
            )
            return

        modulo = dados.get("module", "")
        janela = dados.get("window", "")
        elementos = dados.get("elements", [])
        # processo/exe para reconectar e habilitar realce + captura ao vivo
        processo = (modulo + ".exe") if modulo and not modulo.lower().endswith(".exe") else modulo

        AliasEditorWindow(
            self, elementos, modulo, janela,
            processo=processo or None,
            titulo_busca=None,        # usa top_window do processo
            exe_path=self._last_exe,
            dedup=False,              # mapa já curado — não deduplicar
        )


def _slug_alias(titulo: str) -> str:
    """'Próxima Requisição' -> 'proxima_requisicao' (sugestão de alias)."""
    if not titulo:
        return ""
    txt = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode()
    txt = re.sub(r"[^a-zA-Z0-9]+", "_", txt).strip("_").lower()
    return txt[:30]


def _dedup_elementos(elementos: list[dict]) -> list[dict]:
    """Remove duplicatas da varredura em duas fases.

    Chave: automation_id quando presente; senão assinatura visual
    (control_type + title + class_name + rectangle). Mantém a 1ª ocorrência.
    """
    vistos: set = set()
    saida: list[dict] = []
    for el in elementos:
        auto_id = (el.get("automation_id") or "").strip()
        if auto_id:
            chave = ("aid", auto_id)
        else:
            chave = (
                "vis",
                el.get("control_type"),
                el.get("title"),
                el.get("class_name"),
                tuple(el.get("rectangle") or ()),
            )
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append(el)
    return saida


_HL_STOP = object()  # sentinela para encerrar a thread de realce


class _OverlayRealce(tk.Toplevel):
    """Moldura piscante, topmost e sem bordas, posicionada sobre o campo real.

    Usa -transparentcolor (Windows) para que apenas a moldura colorida apareça,
    deixando o campo visível por baixo. Não rouba foco (overrideredirect).
    """

    _TRANSP = "#00fe01"  # cor "mágica" tornada transparente

    def __init__(self, parent, rect, cor="#ff2d2d", piscadas=3, dur=130):
        super().__init__(parent)
        left, top, right, bottom = rect
        w, h = max(2, right - left), max(2, bottom - top)

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-transparentcolor", self._TRANSP)
        except tk.TclError:
            pass  # ambiente sem suporte — moldura aparece sólida, mas funciona

        self.configure(bg=cor)
        inner = tk.Frame(self, bg=self._TRANSP)
        inner.pack(fill="both", expand=True, padx=3, pady=3)
        # folga de 3px p/ a moldura ladear o campo sem cobri-lo
        self.geometry(f"{w + 6}x{h + 6}+{left - 3}+{top - 3}")

        self._restantes = piscadas * 2
        self._dur = dur
        self._piscar()

    def _piscar(self):
        if not self.winfo_exists():
            return
        if self._restantes <= 0:
            self.destroy()
            return
        if self.state() == "withdrawn":
            self.deiconify()
        else:
            self.withdraw()
        self._restantes -= 1
        self.after(self._dur, self._piscar)


class AliasEditorWindow(tk.Toplevel):
    """Autoria assistida de aliases (FASE 2): QA nomeia cada elemento e salva o alias-map."""

    def __init__(self, parent, elementos: list[dict], modulo_sug: str, janela_sug: str,
                 *, processo: str | None = None, titulo_busca: str | None = None,
                 exe_path: str | None = None, dedup: bool = True):
        super().__init__(parent)
        self.title("Editar aliases — gerar alias-map")
        self.geometry("900x620")
        self.configure(bg=C_BG)
        self.transient(parent)

        self._elementos = _dedup_elementos(elementos) if dedup else list(elementos)
        self._linhas: list[tuple[dict, tk.Entry]] = []
        self._realce: tk.Toplevel | None = None
        # parâmetros para reconectar à janela e reler a posição REAL dos campos
        self._processo = processo
        self._titulo_busca = titulo_busca
        self._exe_path = exe_path

        # thread de realce: conexão + wrappers ficam em cache nela (clique = ~0ms)
        self._hl_queue: queue.Queue = queue.Queue()
        self._hl_thread: threading.Thread | None = None

        # captura manual (modo "spy": clica no campo da tela -> captura)
        self._captura_on = False
        self._captura_ocupada = False
        self._captura_listener = None
        self._grid_inner: tk.Frame | None = None
        self._remap_em_andamento = False

        self._build_header(modulo_sug, janela_sug)
        self._build_grid()
        self._build_footer()

        # pré-aquece a conexão enquanto o QA lê a grade (esconde a latência inicial)
        self._ensure_worker()

    def _build_header(self, modulo_sug: str, janela_sug: str):
        card = tk.Frame(self, bg=C_WHITE, bd=1, relief="solid")
        card.pack(fill="x", padx=12, pady=10)

        row = tk.Frame(card, bg=C_WHITE)
        row.pack(fill="x", padx=12, pady=10)

        tk.Label(row, text="Módulo:", bg=C_WHITE, font=("Segoe UI", 9, "bold")).pack(side="left")
        self.entry_modulo = tk.Entry(row, font=C_FONT, width=16, relief="solid", bd=1)
        self.entry_modulo.insert(0, modulo_sug or "FCReceitas")
        self.entry_modulo.pack(side="left", padx=(4, 16))

        tk.Label(row, text="Janela:", bg=C_WHITE, font=("Segoe UI", 9, "bold")).pack(side="left")
        self.entry_janela = tk.Entry(row, font=C_FONT, width=18, relief="solid", bd=1)
        self.entry_janela.insert(0, janela_sug or "Principal")
        self.entry_janela.pack(side="left", padx=(4, 16))

        tk.Label(
            row,
            text="Salva em mappings/<Módulo>/<Janela>.json — só linhas com alias preenchido.",
            bg=C_WHITE, font=("Segoe UI", 8), fg="#666",
        ).pack(side="left")

        tk.Label(
            card,
            text="💡 Clique no botão 👁 (ou na linha) e o campo PISCA na janela do Formula Certa. "
                 "A posição é relida AO VIVO a cada clique — pode mover a janela à vontade.",
            bg=C_WHITE, font=("Segoe UI", 8), fg="#1565C0", justify="left",
        ).pack(anchor="w", padx=12, pady=(0, 8))

    def _build_grid(self):
        wrap = tk.Frame(self, bg=C_BG)
        wrap.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        canvas = tk.Canvas(wrap, bg=C_BG, highlightthickness=0)
        scroll = tk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=C_BG)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

        # cabeçalho
        hdr = tk.Frame(inner, bg="#e8eef7")
        hdr.pack(fill="x")
        for txt, w in (("ver", 4), ("alias", 22), ("class_name", 22), ("title", 20),
                       ("type", 10), ("auto_id", 12), ("idx", 5), ("del", 4)):
            tk.Label(hdr, text=txt, bg="#e8eef7", font=("Segoe UI", 8, "bold"),
                     width=w, anchor="w").pack(side="left", padx=2)

        self._grid_inner = inner
        for el in self._elementos:
            self._add_row(inner, el)

    def _add_row(self, parent, el: dict, alias_inicial: str | None = None):
        row = tk.Frame(parent, bg=C_WHITE, bd=1, relief="flat")
        row.pack(fill="x", pady=1)

        btn_ver = tk.Button(
            row, text="👁", width=3, relief="flat", bg="#e8f0fe", fg=C_BLUE,
            cursor="hand2", command=lambda e=el: self._realcar_live(e),
        )
        btn_ver.pack(side="left", padx=2)

        entry = tk.Entry(row, font=C_MONO, width=22, relief="solid", bd=1)
        # prioridade do alias inicial: argumento > alias salvo no mapa > slug do título
        if alias_inicial is not None:
            sugestao = alias_inicial
        else:
            sugestao = el.get("alias") or _slug_alias(el.get("title") or "")
        if sugestao:
            entry.insert(0, sugestao)
        entry.pack(side="left", padx=2)

        def cell(valor, w):
            lbl = tk.Label(row, text=str(valor)[:w], bg=C_WHITE, font=C_MONO,
                           width=w, anchor="w")
            lbl.pack(side="left", padx=2)
            # clicar na linha também realça (relendo a posição atual)
            lbl.bind("<Button-1>", lambda e, x=el: self._realcar_live(x))

        cell(el.get("class_name") or "—", 22)
        cell(el.get("title") or "", 20)
        cell((el.get("control_type") or "")[:10], 10)
        cell(el.get("automation_id") or "", 12)
        cell(el.get("found_index"), 5)

        btn_del = tk.Button(
            row, text="🗑", width=3, relief="flat", bg="#fde8e8", fg=C_RED,
            cursor="hand2", command=lambda: self._remover_linha(row, entry),
        )
        btn_del.pack(side="left", padx=2)

        self._linhas.append((el, entry))

    def _remover_linha(self, row, entry) -> None:
        self._linhas = [(e, en) for (e, en) in self._linhas if en is not entry]
        try:
            row.destroy()
        except Exception:
            pass

    # ── realce ao vivo (thread persistente com conexão + wrappers em cache) ──
    def _ensure_worker(self) -> None:
        if self._hl_thread is not None:
            return
        self._hl_thread = threading.Thread(target=self._hl_worker_loop, daemon=True)
        self._hl_thread.start()

    def _realcar_live(self, el: dict) -> None:
        """Pede o realce do campo; a thread relê a posição ATUAL (1º clique paga,
        próximos no mesmo campo são instantâneos via wrapper em cache)."""
        self._ensure_worker()
        self._set_status("Localizando campo na tela...")
        self._hl_queue.put(el)

    def _hl_worker_loop(self) -> None:
        """Roda numa thread única com COM inicializado; mantém app/janela e
        wrappers de elementos em cache para que `.rectangle()` saia em ~0ms."""
        pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
        ctx: dict = {"app": None, "win": None}
        cache: dict = {}
        try:
            self._hl_connect(ctx)  # pré-aquece a conexão
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Pré-conexão de realce falhou: {exc}")
        try:
            while True:
                item = self._hl_queue.get()
                if item is _HL_STOP:
                    break

                # pedido de CAPTURA manual (modo spy): ("__cap__", x, y)
                if isinstance(item, tuple) and item and item[0] == "__cap__":
                    self._hl_capturar(item[1], item[2], ctx, cache)
                    continue

                # senão é REALCE (dict): se houver cliques acumulados, salta p/ o último
                el = item
                while True:
                    try:
                        nxt = self._hl_queue.get_nowait()
                    except queue.Empty:
                        break
                    if nxt is _HL_STOP:
                        el = _HL_STOP
                        break
                    if isinstance(nxt, tuple) and nxt and nxt[0] == "__cap__":
                        self._hl_queue.put(nxt)  # devolve a captura p/ a próxima volta
                        break
                    el = nxt
                if el is _HL_STOP:
                    break

                rect = self._hl_rect(el, ctx, cache)
                try:
                    self.after(0, lambda e=el, r=rect: self._aplicar_realce(e, r))
                except Exception:
                    break  # janela do editor foi fechada
        finally:
            pythoncom.CoUninitialize()

    def _hl_connect(self, ctx: dict) -> None:
        from tools.mapear_janela import _conectar_app, _obter_janela
        ctx["app"] = _conectar_app(
            processo=self._processo, exe_path=self._exe_path or "", timeout_janela=8
        )
        ctx["win"] = _obter_janela(ctx["app"], self._titulo_busca, 8, self._processo)

    def _hl_rect(self, el: dict, ctx: dict, cache: dict) -> list[int] | None:
        key = self._hl_key(el)
        # 1) wrapper já resolvido -> rectangle() ao vivo é ~0ms
        w = cache.get(key)
        if w is not None:
            try:
                r = w.rectangle()
                return [r.left, r.top, r.right, r.bottom]
            except Exception:
                cache.pop(key, None)  # ficou obsoleto; re-resolve abaixo
        # 2) (re)resolve, reconectando se a janela caiu
        for _ in (1, 2):
            try:
                if ctx["win"] is None:
                    self._hl_connect(ctx)
                w = self._hl_fast_resolve(ctx["win"], el)
                cache[key] = w
                r = w.rectangle()
                return [r.left, r.top, r.right, r.bottom]
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"Resolve ao vivo falhou: {exc}")
                ctx["app"] = None
                ctx["win"] = None
        return None

    @staticmethod
    def _hl_key(el: dict):
        aid = el.get("automation_id")
        if aid:
            return ("aid", str(aid))
        return ("ci", el.get("class_name"), el.get("found_index"),
                el.get("instance"), el.get("title"))

    @staticmethod
    def _hl_fast_resolve(win, el: dict):
        """Resolve o elemento SEM o wait('visible enabled') — só localizar e pegar
        o wrapper. Mesma prioridade do locator_engine."""
        auto_id = el.get("automation_id")
        ctype = el.get("control_type") or None
        cls = el.get("class_name")
        title = el.get("title")
        fi = el.get("found_index")

        specs: list[dict] = []
        if auto_id:
            kw = {"auto_id": str(auto_id)}
            if ctype:
                kw["control_type"] = ctype
            specs.append(kw)
        if cls and title:
            specs.append({"class_name": cls, "title": title})
        if title and ctype and not cls:
            specs.append({"control_type": ctype, "title": title})
        if cls and fi is not None:
            specs.append({"class_name": cls, "found_index": fi})

        ultimo = None
        for kw in specs:
            try:
                return win.child_window(**kw).wrapper_object()
            except Exception as exc:  # noqa: BLE001
                ultimo = exc
        raise ultimo or RuntimeError("nenhuma estratégia de localização")

    def _aplicar_realce(self, el: dict, rect: list[int] | None) -> None:
        """Cria a moldura na thread principal; fallback p/ posição do mapeamento."""
        if not self.winfo_exists():
            return
        if rect is None:
            rect = el.get("rectangle")
            self._set_status("⚠ não consegui reler ao vivo — usando posição do mapeamento", erro=True)
        else:
            self._set_status("")
        self._realcar(rect)

    def _realcar(self, rect) -> None:
        """Pisca uma moldura sobre o campo (rect em coordenadas de tela)."""
        if not rect or len(rect) != 4:
            return
        left, top, right, bottom = (int(v) for v in rect)
        if right - left <= 0 or bottom - top <= 0:
            return
        try:
            if self._realce is not None and self._realce.winfo_exists():
                self._realce.destroy()
        except Exception:
            pass
        self._realce = _OverlayRealce(self, (left, top, right, bottom))

    def _set_status(self, texto: str, erro: bool = False) -> None:
        if hasattr(self, "lbl_status") and self.lbl_status.winfo_exists():
            self.lbl_status.config(text=texto, fg=(C_RED if erro else "#444"))

    def destroy(self):
        # encerra a thread de realce e o listener de captura ao fechar o editor
        self._captura_on = False
        self._parar_listener()
        try:
            if self._hl_thread is not None:
                self._hl_queue.put(_HL_STOP)
        except Exception:
            pass
        super().destroy()

    def _build_footer(self):
        foot = tk.Frame(self, bg=C_BG)
        foot.pack(fill="x", padx=12, pady=(0, 12))

        self.btn_remap = tk.Button(
            foot, text="🔄 Re-mapear (mesclar)", bg="#7c3aed", fg=C_WHITE,
            font=("Segoe UI", 9, "bold"), relief="flat", padx=14, pady=8,
            cursor="hand2", command=self._remapear_mesclar,
        )
        self.btn_remap.pack(side="left")

        self.btn_captura = tk.Button(
            foot, text="🎯 Capturar manual", bg=C_BLUE, fg=C_WHITE,
            font=("Segoe UI", 9, "bold"), relief="flat", padx=14, pady=8,
            cursor="hand2", command=self._toggle_captura,
        )
        self.btn_captura.pack(side="left", padx=(8, 0))

        self.lbl_status = tk.Label(foot, text="", bg=C_BG, font=("Segoe UI", 9), fg="#444")
        self.lbl_status.pack(side="left", padx=(12, 0))

        tk.Button(
            foot, text="Salvar alias-map", bg=C_GREEN, fg=C_WHITE,
            font=("Segoe UI", 10, "bold"), relief="flat", padx=20, pady=8,
            cursor="hand2", command=self._salvar,
        ).pack(side="right")

    # ── captura manual (modo spy) ────────────────────────────────
    def _toggle_captura(self):
        if not self._captura_on:
            self._ensure_worker()
            if not self._iniciar_listener():
                return
            self._captura_on = True
            self._captura_ocupada = False
            self.btn_captura.config(text="■ Parar captura", bg=C_RED)
            self._set_status("Captura LIGADA — clique num campo do Formula Certa.")
        else:
            self._captura_on = False
            self._captura_ocupada = False
            self._parar_listener()
            self.btn_captura.config(text="🎯 Capturar manual", bg=C_BLUE)
            self._set_status("Captura desligada.")

    # ── re-mapeamento geral + mesclagem (inclusão em massa) ──────
    def _remapear_mesclar(self) -> None:
        """Re-mapeia a janela ao vivo e MESCLA os elementos novos, preservando
        os aliases já existentes. Casa por automation_id (estável no Delphi)."""
        if self._remap_em_andamento:
            return
        if not self._processo and not self._titulo_busca:
            messagebox.showwarning(
                "Re-mapear",
                "Sem processo/janela para re-mapear. Abra este editor a partir de "
                "um mapeamento ou de um alias-map com módulo válido.",
                parent=self,
            )
            return

        self._remap_em_andamento = True
        self.btn_remap.config(state="disabled", text="Re-mapeando...")
        self._set_status("Re-mapeando a janela (pode levar 1–3 min)...")

        def _prog(msg: str):
            try:
                self.after(0, lambda m=msg: self._set_status(str(m)[:90]))
            except Exception:
                pass

        def worker():
            pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
            try:
                from tools.mapear_janela import mapear_janela
                out = mapear_janela(
                    self._titulo_busca,
                    processo=self._processo,
                    exe_path=self._exe_path or None,
                    timeout_janela=30,
                    incluir_ocultos=True,
                    on_progress=_prog,
                )
                mapped = json.loads(Path(out).read_text(encoding="utf-8"))
                self.after(0, lambda: self._aplicar_merge(mapped))
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                self.after(0, lambda: self._fim_remap(f"⚠ falha ao re-mapear: {msg}", erro=True))
            finally:
                pythoncom.CoUninitialize()

        threading.Thread(target=worker, daemon=True).start()

    def _aplicar_merge(self, mapped: list[dict]) -> None:
        if not self.winfo_exists():
            return
        novos = _dedup_elementos(mapped)
        chaves = {self._merge_key(el) for el, _ in self._linhas}
        adicionados = 0
        for el in novos:
            k = self._merge_key(el)
            if k in chaves:
                continue           # já existe (mesmo automation_id / botão) — preserva
            chaves.add(k)
            self._add_row(self._grid_inner, el)
            adicionados += 1
        self._fim_remap(
            f"✓ Re-mapeado: {adicionados} novo(s) elemento(s) adicionado(s) "
            f"— total {len(self._linhas)}. Preencha os aliases e salve."
        )

    @staticmethod
    def _merge_key(el: dict):
        """Identidade estável p/ mesclagem: automation_id; senão control_type+title+class."""
        aid = (el.get("automation_id") or "").strip()
        if aid:
            return ("aid", aid)
        return ("ct", el.get("control_type") or "", el.get("title") or "", el.get("class_name") or "")

    def _fim_remap(self, msg: str, erro: bool = False) -> None:
        self._remap_em_andamento = False
        if self.winfo_exists():
            self.btn_remap.config(state="normal", text="🔄 Re-mapear (mesclar)")
            self._set_status(msg, erro=erro)

    def _iniciar_listener(self) -> bool:
        try:
            from pynput import mouse
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Captura manual", f"pynput indisponível: {exc}", parent=self)
            return False
        self._captura_listener = mouse.Listener(on_click=self._on_click_global)
        self._captura_listener.start()
        return True

    def _parar_listener(self):
        try:
            if self._captura_listener is not None:
                self._captura_listener.stop()
                self._captura_listener = None
        except Exception:
            pass

    def _on_click_global(self, x, y, button, pressed):
        # roda na thread do pynput; só dispara em clique esquerdo, fora da nossa UI
        if not pressed:
            return
        try:
            from pynput.mouse import Button
            if button != Button.left:
                return
        except Exception:
            pass
        if not self._captura_on or self._captura_ocupada:
            return
        if self._ponto_e_nosso(x, y):
            return  # clicou na própria janela do editor/diálogo — ignora
        self._captura_ocupada = True
        try:
            self.after(0, lambda: self._set_status("Lendo campo clicado..."))
            self._hl_queue.put(("__cap__", int(x), int(y)))
        except Exception:
            self._captura_ocupada = False

    @staticmethod
    def _ponto_e_nosso(x, y) -> bool:
        try:
            import os
            import win32gui
            import win32process
            hwnd = win32gui.WindowFromPoint((int(x), int(y)))
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return pid == os.getpid()
        except Exception:
            return False

    def _hl_capturar(self, x, y, ctx, cache) -> None:
        """(thread COM) lê o elemento sob o cursor e abre o diálogo de captura."""
        try:
            from pywinauto import Desktop
            from core.recorder.locator import ElementLocator

            elem = Desktop(backend="uia").from_point(int(x), int(y))
            top = elem.top_level_parent()
            loc = ElementLocator().resolve(top, elem)
            r = elem.rectangle()

            def _s(fn):
                try:
                    v = fn()
                    return (v or "").strip() if isinstance(v, str) else v
                except Exception:
                    return None

            info = {
                "alias": "",
                "automation_id": loc.automation_id or _s(elem.automation_id) or "",
                "class_name": loc.class_name or _s(elem.class_name) or "",
                "title": loc.title or _s(elem.window_text) or "",
                "control_type": loc.control_type or str(elem.element_info.control_type),
                "found_index": loc.found_index,
                "instance": loc.instance,
                "rectangle": [r.left, r.top, r.right, r.bottom],
            }
            self.after(0, lambda i=info: self._mostrar_captura(i))
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Captura falhou: {exc}")
            self.after(0, lambda: self._fim_captura("⚠ não consegui ler o campo clicado — tente de novo.", erro=True))

    def _mostrar_captura(self, info: dict) -> None:
        if not self.winfo_exists():
            return
        self._realcar(info.get("rectangle"))  # pisca o que foi capturado
        resumo = (
            f"class_name:     {info['class_name'] or '—'}\n"
            f"control_type:   {info['control_type'] or '—'}\n"
            f"automation_id:  {info['automation_id'] or '—'}\n"
            f"title:          {info['title'] or '—'}\n"
            f"found_index:    {info['found_index']}     instance: {info['instance']}"
        )
        if not messagebox.askyesno("Campo capturado", resumo + "\n\nSalvar este campo?", parent=self):
            self._fim_captura("Campo descartado — clique no próximo.")
            return

        dup = self._achar_duplicado(info)
        if dup is not None:
            if not messagebox.askyesno(
                "Já existe",
                f"Este campo já está na lista (alias '{dup}').\nAdicionar mesmo assim?",
                parent=self,
            ):
                self._fim_captura("Já existia — clique no próximo.")
                return

        while True:
            alias = simpledialog.askstring("Alias", "Nome do alias para este campo:", parent=self)
            if alias is None:
                self._fim_captura("Cancelado — clique no próximo.")
                return
            alias = alias.strip()
            if not alias:
                continue
            if alias in self._aliases_atuais():
                messagebox.showwarning("Alias repetido", f"O alias '{alias}' já existe.", parent=self)
                continue
            break

        self._add_row(self._grid_inner, info, alias_inicial=alias)
        self._fim_captura(f"✓ '{alias}' adicionado. Clique no próximo campo.")

    def _achar_duplicado(self, info: dict) -> str | None:
        aid = (info.get("automation_id") or "").strip()
        cls = info.get("class_name")
        fi = info.get("found_index")
        for el, entry in self._linhas:
            if aid and (el.get("automation_id") or "").strip() == aid:
                return entry.get().strip() or "(sem alias)"
            if not aid and fi is not None and el.get("class_name") == cls and el.get("found_index") == fi:
                return entry.get().strip() or "(sem alias)"
        return None

    def _aliases_atuais(self) -> set[str]:
        return {entry.get().strip() for _el, entry in self._linhas if entry.get().strip()}

    def _fim_captura(self, msg: str, erro: bool = False) -> None:
        self._captura_ocupada = False
        if self._captura_on:
            self._set_status(msg, erro=erro)

    def _salvar(self):
        modulo = self.entry_modulo.get().strip()
        janela = self.entry_janela.get().strip()
        if not modulo or not janela:
            messagebox.showwarning("Aviso", "Informe módulo e janela.")
            return

        aliases: dict[str, dict] = {}
        elementos: list[dict] = []
        for el, entry in self._linhas:
            alias = entry.get().strip()
            if not alias:
                continue
            if alias in aliases:
                messagebox.showwarning("Alias duplicado", f"O alias '{alias}' está repetido.")
                return
            aliases[alias] = el
            elementos.append({**el, "alias": alias})

        if not elementos:
            messagebox.showwarning("Aviso", "Preencha ao menos um alias.")
            return

        try:
            caminho = salvar_mapa(modulo, janela, elementos)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro", f"Falha ao salvar: {exc}")
            return

        messagebox.showinfo(
            "Alias-map salvo",
            f"{len(elementos)} aliases salvos em:\n{caminho}",
        )
        self.destroy()
