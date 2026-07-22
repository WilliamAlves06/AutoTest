"""
core/evidence.py — sessao de evidencias (prints manuais + automaticos) por execucao
de teste, organizadas em logs/evidencias/{AAAA-MM}/{DD}/{HH-MM-SS}_{teste}/.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from loguru import logger

from core.actions import tirar_print

EVIDENCIAS_DIR = Path("logs/evidencias")

_INVALIDOS = re.compile(r'[\\/:*?"<>|]')


def _sanitizar(nome: str) -> str:
    return _INVALIDOS.sub("_", nome).strip()[:150]


class EvidenceSession:
    def __init__(self, nome_teste: str):
        self.nome_teste = nome_teste
        self.inicio = datetime.now()
        self.registros: list[dict] = []
        self.dir = (
            EVIDENCIAS_DIR
            / self.inicio.strftime("%Y-%m")
            / self.inicio.strftime("%d")
            / f"{self.inicio.strftime('%H-%M-%S')}_{_sanitizar(nome_teste)}"
        )
        self.dir.mkdir(parents=True, exist_ok=True)

    def _resolver_destino(self, nome_arquivo: str) -> Path:
        destino = self.dir / f"{nome_arquivo}.png"
        contador = 2
        while destino.exists():
            destino = self.dir / f"{nome_arquivo} ({contador}).png"
            contador += 1
        return destino

    def capturar(self, label: str) -> Path | None:
        nome_arquivo = _sanitizar(label)
        destino = self._resolver_destino(nome_arquivo)
        sucesso = False
        try:
            sucesso = tirar_print(destino)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Print de evidencia falhou [{label}]: {exc}")

        self.registros.append(
            {
                "arquivo": destino.name if sucesso else None,
                "label": label,
                "horario": datetime.now().isoformat(),
                "sucesso": sucesso,
            }
        )

        if sucesso:
            logger.info(f"Print de evidencia salvo: {destino}")
            return destino
        logger.warning(f"Print de evidencia indisponivel: {label}")
        return None

    def finalizar(self, status: str) -> None:
        manifest = {
            "teste": self.nome_teste,
            "inicio": self.inicio.isoformat(),
            "fim": datetime.now().isoformat(),
            "status": status,
            "prints": self.registros,
        }
        try:
            (self.dir / "manifest.json").write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Nao consegui gravar manifest.json: {exc}")


_sessao_atual: EvidenceSession | None = None


def iniciar_sessao(nome_teste: str) -> EvidenceSession:
    global _sessao_atual
    _sessao_atual = EvidenceSession(nome_teste)
    return _sessao_atual


def sessao_ativa() -> EvidenceSession | None:
    return _sessao_atual
