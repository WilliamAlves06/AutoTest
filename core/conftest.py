import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from database.connection import conectar


@pytest.fixture(scope="session")
def db():
    """Conexão Firebird/InterBase reutilizada na sessão.

    Usa database.connection.conectar(), que descobre o banco a partir do
    alterdb.ini do Formula Certa (fonte única — mesma do fc.db).
    """
    conn = conectar()
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def cursor(db):
    cur = db.cursor()
    yield cur
    cur.close()
