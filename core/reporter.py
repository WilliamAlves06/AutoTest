from loguru import logger

def imprimir_inicio(nome_ct: str, descricao: str):
    logger.info("=" * 55)
    logger.info(f"  CT: {nome_ct}")
    logger.info(f"  {descricao}")
    logger.info("=" * 55)

def imprimir_etapa(mensagem: str):
    logger.info(f"→ {mensagem}")

def imprimir_resultado(resultados: list[dict]):
    """
    resultados = [
        {"campo": "NRLOT", "esperado": "123", "obtido": "123", "status": "PASS"},
    ]
    """
    logger.info("-" * 55)
    logger.info(f"  {'CAMPO':<20} {'ESPERADO':<15} {'OBTIDO':<15} STATUS")
    logger.info("-" * 55)

    total_pass = 0
    total_fail = 0

    for r in resultados:
        icone = "✔" if r["status"] == "PASS" else "✘"
        linha = f"  {r['campo']:<20} {str(r['esperado']):<15} {str(r['obtido']):<15} {icone} {r['status']}"

        if r["status"] == "PASS":
            logger.success(linha)
            total_pass += 1
        else:
            logger.error(linha)
            logger.error(f"  DETALHE: campo '{r['campo']}' esperado '{r['esperado']}' mas obtido '{r['obtido']}'")
            total_fail += 1

    logger.info("-" * 55)

    if total_fail == 0:
        logger.success(f"  RESULTADO: {total_pass}/{total_pass + total_fail} validações passaram")
    else:
        logger.error(f"  RESULTADO: {total_fail} falha(s) | {total_pass} passou(aram)")

    logger.info("=" * 55)

def imprimir_erro_critico(mensagem: str):
    logger.info("=" * 55)
    logger.error(f"  ERRO CRÍTICO: {mensagem}")
    logger.info("=" * 55)
