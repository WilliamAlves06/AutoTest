"""
database/connection.py
Abstração fina de driver de banco para o Formula Certa.

O banco usado é descoberto AUTOMATICAMENTE a partir do mesmo arquivo que o
Formula Certa lê — `C:\\Fcerta\\alterdb.ini` — para nunca ficar dessincronizado:
    [SERVIDOR] NOMESERVIDOR  -> host
    [PATH]     PATHPAR       -> pasta do banco (arquivo ALTERDB.ib)

Hoje usamos `fdb`. A troca futura para `firebird-driver` fica isolada em `conectar()`.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger

# Arquivo de configuração do próprio Formula Certa e nome do banco principal.
_ALTERDB_INI = Path(r"C:\Fcerta\alterdb.ini")
_DB_FILENAME = "ALTERDB.ib"

# Usado se o alterdb.ini não for encontrado/legível.
_DEFAULT = {
    "host":     "localhost",
    "database": r"C:\bancoDeDados\teste\ALTERDB.ib",
    "user":     "SYSDBA",
    "password": "masterkey",
}


def _ler_ini() -> dict:
    """Extrai host (NOMESERVIDOR) e caminho do banco (PATHPAR) do alterdb.ini.

    Parse tolerante (o .ini do FC tem seções malformadas/duplicadas).
    """
    cfg = dict(_DEFAULT)
    try:
        texto = _ALTERDB_INI.read_text(encoding="latin-1", errors="ignore")
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"alterdb.ini não lido ({exc}) — usando DB padrão.")
        return cfg

    for raw in texto.splitlines():
        ln = raw.strip()
        if "=" not in ln or ln.startswith("["):
            continue
        chave, _, val = ln.partition("=")
        chave = chave.strip().upper()
        val = val.strip()
        if not val:
            continue
        if chave == "PATHPAR":
            cfg["database"] = str(Path(val) / _DB_FILENAME)
        elif chave == "NOMESERVIDOR":
            cfg["host"] = val
    return cfg


# Descoberto na importação; pode ser sobrescrito passando config em conectar().
DB_CONFIG = _ler_ini()


def conectar(config: dict | None = None):
    """Abre uma conexão DB-API com o banco do Formula Certa.

    Único ponto a alterar quando migrarmos `fdb -> firebird-driver`.
    """
    cfg = config or DB_CONFIG

    try:
        import fdb
    except ImportError as exc:  # pragma: no cover - ambiente sem driver
        raise RuntimeError("Driver 'fdb' não instalado. Rode: pip install fdb") from exc

    logger.debug(f"Conectando ao banco {cfg['host']}:{cfg['database']}")
    return fdb.connect(
        host=cfg["host"],
        database=cfg["database"],
        user=cfg["user"],
        password=cfg["password"],
    )
