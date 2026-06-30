"""
AutoTest QA Studio — app web local (FastAPI + uvicorn).

Abre o navegador automaticamente em http://127.0.0.1:8765 — sem servidor
remoto, sem build step. Substitui a interface desktop (app.py).

    python run_web.py
"""

import threading
import webbrowser

import uvicorn

from webapp.server import app

HOST = "127.0.0.1"
PORT = 8765


def _abrir_browser() -> None:
    webbrowser.open(f"http://{HOST}:{PORT}")


if __name__ == "__main__":
    threading.Timer(1.0, _abrir_browser).start()
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
