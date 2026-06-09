-- Filial cadastrada (tabela FC01000).
-- CDFIL = código da filial; RAZAO = razão social; DESCRFIL = descrição; NRCNPJ = CNPJ.
SELECT
    CDFIL,
    DESCRFIL,
    RAZAO,
    NRCNPJ
FROM FC01000
WHERE CDFIL = :codigo
