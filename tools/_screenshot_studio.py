"""Captura screenshots do QA Studio para validação visual (não é teste)."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ui.app_shell import StudioApp  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "logs"
OUT.mkdir(exist_ok=True)


def _grab(app, nome):
    app.lift()
    app.attributes("-topmost", True)
    for _ in range(8):
        app.update_idletasks()
        app.update()
    time.sleep(0.4)
    app.update()
    x, y = app.winfo_rootx(), app.winfo_rooty()
    w, h = app.winfo_width(), app.winfo_height()
    from PIL import ImageGrab
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    destino = OUT / f"studio_{nome}.png"
    img.save(destino)
    print("saved", destino)


def main():
    app = StudioApp()
    app.geometry("1280x820+40+20")
    for tela in ("testes", "config"):
        app.mostrar(tela)
        _grab(app, tela)
    app.destroy()


if __name__ == "__main__":
    main()
