import sys
from pathlib import Path
from loguru import logger

def setup_logging(log_name: str = "automacao", json_output: bool = False):
    """
    Configura logging estruturado.
 
    - Terminal  : tudo (DEBUG pra cima) — acompanhamento em tempo real
    - Arquivo   : só erros — histórico limpo
    - JSON      : só erros — integração com n8n / orquestradores RPA
    """
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
 
    logger.remove()
 
    # ── Terminal ──────────────────────
    logger.add(
        sys.stdout,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
        level="DEBUG",
        colorize=True,
    )
 
    # ── Arquivo .log — somente erros ───────────────────────────
    logger.add(
        log_dir / f"{log_name}_{{time:YYYY-MM-DD}}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {function}:{line} — {message}",
        level="ERROR",
        rotation="00:00",
        retention="7 days",
        encoding="utf-8",
    )
 
    # ── JSON — somente erros ────────
    if json_output:
        logger.add(
            log_dir / f"{log_name}_events.jsonl",
            format="{message}",
            level="ERROR",
            serialize=True,
            rotation="10 MB",
            retention="7 days",
            encoding="utf-8",
        )
 
    return logger