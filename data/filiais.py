"""Massa de dados — Consulta de Filial (FCFiliais / tabela FC01000)."""

# Código da filial consultada no fluxo.
CODIGO_CONSULTA = "10"

# Campos da TELA validados contra o banco (alias_na_tela -> coluna_no_banco).
# A Razão Social é a prova de que a consulta trouxe a filial certa.
MAPA_TELA_BANCO = {
    "Razao_Social": "RAZAO",
}
