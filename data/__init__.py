"""
data/ — massa de dados dos testes (equivalente ao `data/` / `fixtures/` do Playwright).

Centraliza códigos consultados e valores esperados, fora dos arquivos de fluxo.
Cada módulo aqui descreve UM cenário de negócio. Os flows importam destes módulos
em vez de manter constantes soltas:

    from data import receitas
    fc.field("produto").type(receitas.PRODUTO)
"""
