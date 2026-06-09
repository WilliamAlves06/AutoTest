"""
fc/db_facade.py
Fachada `fc.db` — validação obrigatória em banco a partir da DSL.

Mantém um FirebirdClient reutilizado durante o teste e delega para
database.assertions.assert_saved (a "Regra Oficial de Aprovação").
"""

from __future__ import annotations

from database.firebird_client import FirebirdClient
from database import assertions as _assertions


class DBFacade:
    def __init__(self):
        self._client: FirebirdClient | None = None

    @property
    def client(self) -> FirebirdClient:
        if self._client is None:
            self._client = FirebirdClient()
        return self._client

    def assert_saved(self, query: str, expected: dict, params: dict | None = None) -> list[dict]:
        """Aprova o teste só se todos os campos esperados existirem no banco."""
        return _assertions.assert_saved(
            query=query, expected=expected, params=params, client=self.client
        )

    def query(self, nome_sql: str, params: dict | None = None) -> dict | None:
        return self.client.query(nome_sql, params)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
