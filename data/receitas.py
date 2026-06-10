"""Massa de dados — Inclusão de Receita (FCReceitas)."""

CLIENTE = "1"
MEDICO = "1"
DIAS = "30"
PRODUTO = "51639"
QUANTIDADE = "200"

# Valores que DEVEM estar persistidos no banco para o teste passar.
# OBS.: a tabela/colunas reais da receita ainda precisam ser confirmadas no banco
# (ver MIGRACAO_PLANO.md / queries/receita_salva.sql). Estes nomes são provisórios.
ESPERADO_DB = {
    "CDCLI": CLIENTE,
    "CDMED": MEDICO,
    "CDPRO": PRODUTO,
    "QTD": QUANTIDADE,
    "DIAS": DIAS,
}
