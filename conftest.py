"""
conftest.py (raiz) — configuração compartilhada do pytest para todo o AutoTest.

Faz:
  - garante a raiz do repo no sys.path (imports `fc`, `core`, `data`, `database`
    funcionam sem o `sys.path.insert` espalhado nos flows);
  - fixtures de alto nível (equivalente ao `pages.fixture.ts` do Playwright):
        fc          -> singleton da DSL, resetado ao fim da sessão
        fc_login    -> `fc` já autenticado na janela principal
        fc_modulo   -> factory que abre um módulo e devolve `fc`
        db / cursor -> conexão Firebird/InterBase (descoberta do alterdb.ini)
  - anexa screenshot de falha ao relatório HTML (pytest-html).

IMPORTANTE: os imports da stack desktop (`fc`, pywinauto, fdb) são LAZY — feitos
dentro das fixtures/hooks — para que a coleta rode num runner Linux (CI nuvem)
sem o Formula Certa instalado. Testes E2E exigem runner Windows com o app + banco.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ── markers (também declarados em pytest.ini) ────────────────────────
def pytest_configure(config):
    for marker in (
        "unit: testes puros, sem app/banco (rodam em qualquer runner)",
        "e2e: ponta-a-ponta — exige Formula Certa + Firebird (runner Windows)",
        "filiais: fluxo de Filiais",
        "notas: fluxo de Notas",
        "receitas: fluxo de Receitas",
        "produtos: fluxo de Produtos",
    ):
        config.addinivalue_line("markers", marker)


# ── fixtures da DSL ──────────────────────────────────────────────────
@pytest.fixture(scope="session")
def fc():
    """Singleton da DSL `fc`. Import lazy (não quebra coleta sem pywinauto)."""
    from fc import fc as _fc
    yield _fc
    _fc.reset()


@pytest.fixture
def fc_login(fc):
    """`fc` já autenticado na janela principal."""
    fc.login()
    return fc


@pytest.fixture
def fc_modulo(fc_login):
    """Factory: `abrir = fc_modulo; abrir('FCFiliais')` devolve `fc` com módulo aberto."""
    def _abrir(nome: str, **kwargs):
        fc_login.open_module(nome, **kwargs)
        return fc_login
    return _abrir


# ── fixtures de banco ────────────────────────────────────────────────
@pytest.fixture(scope="session")
def db():
    """Conexão Firebird/InterBase reutilizada na sessão (mesma fonte do fc.db)."""
    from database.connection import conectar
    conn = conectar()
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def cursor(db):
    cur = db.cursor()
    yield cur
    cur.close()


# ── evidências: screenshot de falha no relatório HTML ────────────────
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Em falha de um teste, captura screenshot e anexa ao pytest-html."""
    outcome = yield
    report = outcome.get_result()

    if report.when != "call" or not report.failed:
        return

    try:
        from core.actions import screenshot_on_failure
        caminho = screenshot_on_failure(f"pytest_{item.name}")
    except Exception:
        caminho = None

    if not caminho:
        return

    try:
        from pytest_html import extras as html_extras
        extras = list(getattr(report, "extras", []))
        extras.append(html_extras.image(str(caminho)))
        extras.append(html_extras.url(Path(caminho).as_uri(), name="screenshot"))
        report.extras = extras
    except Exception:
        pass  # pytest-html ausente — screenshot já ficou salvo em logs/screenshots
