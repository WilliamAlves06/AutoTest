-- Receita persistida no banco do Formula Certa.
-- ATENÇÃO: a tabela/colunas reais precisam ser confirmadas via metadados
-- (ver seção "Verificação" do plano). FC11100 é Notas, NÃO Receitas.
-- Ajuste o nome da tabela e das colunas após inspecionar o alterdb.ib.
SELECT
    CDCLI,
    CDMED,
    CDPRO,
    QTD,
    DIAS
FROM RECEITAS
WHERE CDPRO = :produto
