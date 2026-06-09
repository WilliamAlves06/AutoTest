"""
database/firebird_client.py
Cliente de alto nível para consultas reutilizáveis no banco do Formula Certa.

- Carrega SQL de `database/queries/<nome>.sql`.
- Suporta parâmetros nomeados (`:produto`) e os converte para posicionais (`?`),
  já que o `fdb` usa paramstyle `qmark`. Isso mantém o SQL legível e independente
  do driver (útil para a futura troca p/ firebird-driver).
- Retorna a primeira linha como `dict` {coluna: valor}.
"""

from __future__ import annotations

import re
from pathlib import Path

from loguru import logger

from .connection import conectar

_QUERIES_DIR = Path(__file__).parent / "queries"
_PARAM_RE = re.compile(r":(\w+)")


def _carregar_sql(nome: str) -> str:
    """Lê database/queries/<nome>.sql, removendo comentários de linha (-- ...).

    A remoção evita que um `:token` dentro de um comentário seja confundido
    com um parâmetro nomeado na conversão para posicional.
    """
    caminho = _QUERIES_DIR / f"{nome}.sql"
    if not caminho.exists():
        raise FileNotFoundError(f"Query não encontrada: {caminho}")
    linhas = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        pos = linha.find("--")
        linhas.append(linha[:pos] if pos != -1 else linha)
    return "\n".join(linhas)


def _converter_nomeados(sql: str, params: dict) -> tuple[str, list]:
    """Converte `:nome` -> `?` e ordena os valores conforme a ordem no SQL."""
    valores: list = []

    def _sub(match: re.Match) -> str:
        chave = match.group(1)
        if chave not in params:
            raise KeyError(f"Parâmetro ':{chave}' ausente em params={params}")
        valores.append(params[chave])
        return "?"

    sql_convertido = _PARAM_RE.sub(_sub, sql)
    return sql_convertido, valores


class FirebirdClient:
    """Conexão reutilizável + execução de queries nomeadas."""

    def __init__(self, config: dict | None = None):
        self._config = config
        self._conn = None

    # ── ciclo de vida ────────────────────────────────────────────
    def connect(self) -> "FirebirdClient":
        if self._conn is None:
            self._conn = conectar(self._config)
            logger.debug("Conexão com o banco aberta.")
        return self

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            logger.debug("Conexão com o banco fechada.")

    def __enter__(self) -> "FirebirdClient":
        return self.connect()

    def __exit__(self, *exc) -> None:
        self.close()

    # ── consultas ────────────────────────────────────────────────
    def query(self, nome_sql: str, params: dict | None = None) -> dict | None:
        """Executa a query nomeada e retorna a 1ª linha como dict (ou None)."""
        self.connect()
        sql = _carregar_sql(nome_sql)
        sql_exec, valores = _converter_nomeados(sql, params or {})

        cur = self._conn.cursor()
        try:
            cur.execute(sql_exec, valores)
            linha = cur.fetchone()
            if linha is None:
                return None
            colunas = [d[0] for d in cur.description]
            return dict(zip(colunas, linha))
        finally:
            cur.close()

    def query_all(self, nome_sql: str, params: dict | None = None) -> list[dict]:
        """Igual a `query`, mas retorna todas as linhas."""
        self.connect()
        sql = _carregar_sql(nome_sql)
        sql_exec, valores = _converter_nomeados(sql, params or {})

        cur = self._conn.cursor()
        try:
            cur.execute(sql_exec, valores)
            colunas = [d[0] for d in cur.description]
            return [dict(zip(colunas, linha)) for linha in cur.fetchall()]
        finally:
            cur.close()
