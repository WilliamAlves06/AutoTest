# core/config.py
import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent.parent / "config.json"


def carregar_config() -> dict:
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def salvar_config(cfg: dict) -> None:
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)