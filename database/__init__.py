"""
database/
Validação obrigatória em banco (Firebird/InterBase) do Formula Certa.

Uso típico:
    from database.assertions import assert_saved
    assert_saved(query="receita_salva", params={"produto": "51639"},
                 expected={"CDCLI": "1", "CDPRO": "51639", "QTD": "200"})
"""

from .firebird_client import FirebirdClient
from .assertions import assert_saved
from .validators import comparar, todos_passaram

__all__ = ["FirebirdClient", "assert_saved", "comparar", "todos_passaram"]
