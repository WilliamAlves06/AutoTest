# core/config.py
import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent.parent / "config.json"

def carregar() -> dict:
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}

_cfg = carregar()

LOGIN = _cfg.get("login", "")
SENHA = _cfg.get("senha", "")
BASE  = _cfg.get("base",  "")