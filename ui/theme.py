"""
ui/theme.py — design tokens centrais do AutoTest QA Studio.

Extraídos do mockup (tema escuro). É a ÚNICA fonte de cores/fontes/raios da GUI;
qualquer tela importa daqui (nada de hex solto espalhado pelos widgets).
"""

from __future__ import annotations

# ── Superfícies ──────────────────────────────────────────────
BG_APP      = "#0a0e16"   # fundo da janela
BG_SIDEBAR  = "#0c1019"   # menu lateral
BG_PANEL    = "#111725"   # cards e painéis
BG_PANEL_2  = "#141b2b"   # linhas / inputs dentro dos painéis
BG_HOVER    = "#1a2335"   # hover de linhas/itens
BG_SEL      = "#16233f"   # item selecionado (tom azulado)

BORDER      = "#222b3d"   # bordas dos cards
BORDER_SOFT = "#1b2333"   # divisórias sutis

# ── Texto ────────────────────────────────────────────────────
TXT         = "#e7ebf3"   # principal (quase branco)
TXT_DIM     = "#8b95a7"   # secundário (cinza)
TXT_MUTED   = "#5a6577"   # terciário (rótulos/placeholder)

# ── Acentos ──────────────────────────────────────────────────
BLUE        = "#3b82f6"
BLUE_DK     = "#2563eb"   # hover do azul
BLUE_TINT   = "#16233f"   # fundo azulado (seleção/botão fantasma)
GREEN       = "#22c55e"
GREEN_TINT  = "#10241b"
RED         = "#ef4444"
RED_TINT    = "#26161d"
PURPLE      = "#7c5cff"   # avatar / logo
ICONBOX     = "#212b3d"   # caixinha de ícone do menu (inativo)

# ── Forma ────────────────────────────────────────────────────
RADIUS      = 12          # cards
RADIUS_SM   = 8           # botões / chips
RADIUS_PILL = 999         # pills (status)

FAMILY = "Segoe UI"


def font(size: int = 13, weight: str = "normal") -> tuple:
    """Fonte padrão como tupla (aceita por qualquer widget tk/ctk)."""
    return (FAMILY, size, weight)


# Cor da pill/badge por status de teste.
def cor_status(status: str) -> tuple[str, str]:
    """Retorna (texto, fundo) para um status PASS/FAIL/—."""
    s = (status or "").upper()
    if s in ("PASS", "PASSOU", "OK"):
        return GREEN, GREEN_TINT
    if s in ("FAIL", "FALHOU", "ERRO"):
        return RED, RED_TINT
    return TXT_DIM, BG_PANEL_2
