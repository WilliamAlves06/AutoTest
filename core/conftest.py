import pytest
import fdb

DB_CONFIG = {
    "host":     "localhost",
    "database": r"C:\bancoDeDados\NFCE-205607\alterdb.ib",  # ajusta o caminho
    "user":     "SYSDBA",
    "password": "masterkey",
}

@pytest.fixture(scope="session")
def db():
    """Conexão InterBase reutilizada em todos os testes da sessão."""
    conn = fdb.connect(
        host=DB_CONFIG["host"],
        database=DB_CONFIG["database"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )
    yield conn
    conn.close()

@pytest.fixture(scope="session")
def cursor(db):
    cur = db.cursor()
    yield cur
    cur.close()