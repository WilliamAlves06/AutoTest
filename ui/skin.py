"""
ui/skin.py — aplica o tema escuro nas telas tk legadas (Recorder/Mapear/Módulos)
SEM reescrevê-las: percorre a árvore de widgets e remapeia as cores claras para as
do design system (ui.theme). Mantém os acentos (verde/azul/vermelho dos botões).

Uso:
    from ui import skin
    skin.estilo_ttk(root)        # uma vez, na criação da janela
    skin.aplicar(page)           # após construir cada página tk hospedada
"""

from __future__ import annotations

from ui import theme as T

# Superfícies claras -> escuras (fundo). Inclui defaults do Windows (System*).
_BG = {
    "#f0f2f5": T.BG_APP, "systembuttonface": T.BG_PANEL,
    "white": T.BG_PANEL, "#ffffff": T.BG_PANEL, "#fafafa": T.BG_PANEL,
    "systemwindow": T.BG_PANEL_2, "systemfield": T.BG_PANEL_2,
    "#f8f9fb": T.BG_PANEL_2, "#dce8f7": T.BG_PANEL_2, "#e8eef7": T.BG_PANEL_2,
    "#e8f0fe": T.BLUE_TINT, "#eef2ff": T.BLUE_TINT,
    "#fde8e8": T.RED_TINT, "#cccccc": T.BG_PANEL_2,
    "#1e1e1e": T.BG_APP, "#2a2a2a": T.BG_PANEL, "#1a2235": T.BG_SIDEBAR,
}

# Textos escuros -> claros (mantém azul como acento). Inclui defaults do Windows.
_FG = {
    "black": T.TXT, "#000000": T.TXT, "#1e293b": T.TXT, "#222": T.TXT,
    "systemwindowtext": T.TXT, "systembuttontext": T.TXT,
    "#333": T.TXT, "#444": T.TXT, "#555": T.TXT,
    "#666": T.TXT_DIM, "#666666": T.TXT_DIM, "#777": T.TXT_DIM,
    "#888": T.TXT_DIM, "#888888": T.TXT_DIM, "#999": T.TXT_DIM, "#999999": T.TXT_DIM,
    "#7a8fa6": T.TXT_DIM, "#3a4a5a": T.TXT_MUTED,
    "#1565c0": T.BLUE, "#2563eb": T.BLUE,
}


def _map(valor, tabela):
    return tabela.get((valor or "").strip().lower())


def aplicar(widget) -> None:
    """Remapeia recursivamente as cores de `widget` e descendentes para o tema escuro."""
    for w in _percorrer(widget):
        _recolor(w)


def _percorrer(w):
    yield w
    try:
        filhos = w.winfo_children()
    except Exception:
        filhos = []
    for c in filhos:
        yield from _percorrer(c)


def _recolor(w) -> None:
    try:
        opcoes = set(w.keys())
    except Exception:
        return

    def setopt(**kw):
        for k, v in kw.items():
            if k in opcoes and v is not None:
                try:
                    w.configure(**{k: v})
                except Exception:
                    pass

    # fundo
    for chave in ("background", "bg"):
        if chave in opcoes:
            novo = _map(w.cget(chave), _BG)
            if novo:
                setopt(**{chave: novo})
            break
    # texto
    for chave in ("foreground", "fg"):
        if chave in opcoes:
            novo = _map(w.cget(chave), _FG)
            if novo:
                setopt(**{chave: novo})
            break

    # campos readonly/disabled (ex.: caminho do JSON gerado) — bg próprio
    for chave in ("readonlybackground", "disabledbackground"):
        if chave in opcoes:
            novo = _map(w.cget(chave), _BG) or T.BG_PANEL_2
            setopt(**{chave: novo})

    # bordas de foco brancas -> borda escura
    setopt(highlightbackground=T.BORDER, highlightcolor=T.BLUE)

    try:
        cls = w.winfo_class()
    except Exception:
        cls = ""
    if cls in ("Entry", "Text", "Listbox", "Spinbox", "Canvas"):
        setopt(insertbackground=T.TXT)
    if cls in ("Entry", "Text", "Listbox", "Spinbox"):
        setopt(selectbackground=T.BLUE, selectforeground="white")


def estilo_ttk(root) -> None:
    """Aplica um tema escuro aos widgets ttk (Notebook/Treeview/Separator/etc.)."""
    try:
        from tkinter import ttk
        st = ttk.Style(root)
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure(".", background=T.BG_PANEL, foreground=T.TXT,
                     fieldbackground=T.BG_PANEL_2, bordercolor=T.BORDER, lightcolor=T.BG_PANEL,
                     darkcolor=T.BG_PANEL, troughcolor=T.BG_APP, arrowcolor=T.TXT)
        st.configure("TNotebook", background=T.BG_APP, borderwidth=0)
        st.configure("TNotebook.Tab", background=T.BG_PANEL_2, foreground=T.TXT_DIM,
                     padding=(14, 6), borderwidth=0)
        st.map("TNotebook.Tab", background=[("selected", T.BG_PANEL)],
               foreground=[("selected", T.TXT)])
        st.configure("Treeview", background=T.BG_PANEL, fieldbackground=T.BG_PANEL,
                     foreground=T.TXT, rowheight=24, borderwidth=0)
        st.configure("Treeview.Heading", background=T.BG_PANEL_2, foreground=T.TXT_DIM,
                     borderwidth=0)
        st.map("Treeview", background=[("selected", T.BLUE_TINT)])
        st.configure("TSeparator", background=T.BORDER)
        st.configure("TScrollbar", background=T.BG_PANEL_2, troughcolor=T.BG_APP,
                     arrowcolor=T.TXT_DIM, bordercolor=T.BG_APP)
        st.configure("TCombobox", fieldbackground=T.BG_PANEL_2, background=T.BG_PANEL_2,
                     foreground=T.TXT, arrowcolor=T.TXT)
        st.configure("TSpinbox", fieldbackground=T.BG_PANEL_2, foreground=T.TXT, arrowcolor=T.TXT)
        st.configure("TCheckbutton", background=T.BG_PANEL, foreground=T.TXT_DIM)
        st.configure("TButton", background=T.BG_PANEL_2, foreground=T.TXT, borderwidth=0)
    except Exception:
        pass
