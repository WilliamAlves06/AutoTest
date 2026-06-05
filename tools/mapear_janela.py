"""
tools/mapear_janela.py
Varre uma janela Delphi/VCL aberta e exporta controles relevantes em JSON.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from loguru import logger

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.actions import (
    conectar_ou_iniciar,
    wait_app_by_exe,
    wait_window,
    wait_window_exact,
)
from core.config import carregar_config
from core.logging_setup import setup_logging
from core.recorder.locator import ElementLocator

RELEVANT_CLASSES = (
    # Botoes
    "TButton",
    "TBitBtn",
    "TSpeedButton",
    "TFagronButton",
    # Campos de texto / edicao
    "TEdit",
    "TMemo",
    "TwwDBEdit",
    "TDBEdit",
    "TDBMemo",
    # Combos / lookups
    "TComboBox",
    "TDBComboBox",
    "TwwDBComboBox",
    "TwwDBLookupCombo",
    "TwwDBLookupComboDlg",
    # Selecao
    "TCheckBox",
    "TDBCheckBox",
    "TRadioButton",
    "TRadioGroup",
    "TDateTimePicker",
    # Grades
    "TwwDBGrid",
    "TDBGrid",
    "TStringGrid",
    # Rotulos
    "TLabel",
)

# Conjunto para teste de pertinencia O(1) durante a varredura recursiva.
_RELEVANT_SET = frozenset(RELEVANT_CLASSES)

OUTPUT_DIR = ROOT / "output"
_DEFAULT_EXE = r"C:\Fcerta\fcerta.exe"
_REGEX_PREFIX = "regex:"
_REGEX_META = re.compile(r"[$*+?{}\[\]|\\()]")
_PARECE_EXE = re.compile(r"^[\w.-]+\.exe$", re.IGNORECASE)

_ALIASES_PROCESSO = {
    "filiais": "FCFiliais.exe",
    "receitas": "FCReceitas.exe",
    "produtos": "FCProdutos.exe",
    "notas": "FCNotas.exe",
}


def _parece_nome_processo(valor: str) -> bool:
    valor = valor.strip()
    if not valor or valor.startswith(_REGEX_PREFIX):
        return False
    if valor.lower().endswith(".exe"):
        return True
    if _PARECE_EXE.match(valor):
        return True
    # Nome curto de modulo sem espacos (Filiais, FCFiliais)
    if " " not in valor and len(valor) <= 32 and re.match(r"^[\w.-]+$", valor):
        base = valor.lower().removesuffix(".exe")
        if base in _ALIASES_PROCESSO or base.startswith("fc"):
            return True
    return False


def resolver_entrada_mapeamento(
    titulo: str | None,
    processo: str | None,
) -> tuple[str | None, str | None]:
    """Normaliza titulo/processo (publico para UI)."""
    return _resolver_entrada(titulo, processo)


def _slug_titulo(titulo: str, processo: str | None = None, max_len: int = 40) -> str:
    base = titulo or processo or "janela"
    slug = re.sub(r"[^\w\s-]", "", base, flags=re.UNICODE)
    slug = re.sub(r"[-\s]+", "_", slug).strip("_")
    if not slug:
        slug = "janela"
    return slug[:max_len]


def _normalizar_processo(nome: str) -> str:
    nome = nome.strip()
    if nome and not nome.lower().endswith(".exe"):
        nome = f"{nome}.exe"
    return nome


def _canonicalizar_processo(nome: str) -> str:
    """Filiais.exe -> FCFiliais.exe; evita buscar janela com nome de exe."""
    nome = _normalizar_processo(nome)
    base = nome[:-4].lower() if nome.lower().endswith(".exe") else nome.lower()
    canon = _ALIASES_PROCESSO.get(base)
    if canon:
        if canon.lower() != nome.lower():
            logger.info(f"Processo '{nome}' resolvido para '{canon}'.")
        return canon
    if base.startswith("fc"):
        return nome
    if base:
        guess = f"FC{base.capitalize()}.exe"
        logger.info(f"Processo '{nome}' interpretado como '{guess}'.")
        return guess
    return nome


def _resolver_entrada(
    titulo: str | None,
    processo: str | None,
) -> tuple[str | None, str | None]:
    """Auto-detecta nome de processo no campo titulo; retorna (titulo, processo)."""
    titulo = (titulo or "").strip() or None
    processo = (processo or "").strip() or None

    if titulo and _parece_nome_processo(titulo):
        logger.warning(
            f"'{titulo}' e nome de processo — movido para conexao via .exe (nao e titulo da janela)."
        )
        processo = processo or titulo
        titulo = None

    if processo:
        processo = _canonicalizar_processo(processo)

    if titulo and _parece_nome_processo(titulo):
        raise ValueError(
            f"'{titulo}' parece nome de processo (.exe), nao titulo da janela. "
            "Use o campo Processo (ex.: FCFiliais.exe) ou o atalho FCFiliais."
        )

    return titulo, processo


def _parse_titulo_busca(titulo: str) -> tuple[str, bool]:
    """Retorna (padrao, usa_regex). Prefixo regex: explícito."""
    if titulo.startswith(_REGEX_PREFIX):
        return titulo[len(_REGEX_PREFIX) :].strip(), True
    if _REGEX_META.search(titulo):
        return titulo, True
    return titulo, False


def _listar_processos_fc() -> list[str]:
    import psutil

    nomes: list[str] = []
    for proc in psutil.process_iter(["name"]):
        name = proc.info.get("name") or ""
        if name.lower().startswith("fc") and name.lower().endswith(".exe"):
            if name not in nomes:
                nomes.append(name)
    return sorted(nomes)


def _obter_janela(app, titulo: str | None, timeout: float, processo: str | None):
    if titulo:
        if _parece_nome_processo(titulo):
            raise ValueError(
                f"'{titulo}' e processo, nao titulo. Preencha o campo Processo ou use regex:.*Filiais.*"
            )
        padrao, usa_regex = _parse_titulo_busca(titulo)
        if usa_regex:
            return wait_window(app, padrao, timeout=timeout, label=padrao)
        return wait_window_exact(app, padrao, timeout=timeout, label=padrao)

    if processo:
        janela = app.top_window()
        janela.wait("visible", timeout=min(timeout, 10))
        logger.info(f"Janela top_window: '{janela.window_text()}'")
        return janela

    raise ValueError("Informe o titulo da janela ou o processo do modulo (.exe).")


def _conectar_app(
    *,
    processo: str | None,
    exe_path: str,
    timeout_janela: float,
):
    if processo:
        logger.info(f"Conectando ao processo {processo}...")
        try:
            return wait_app_by_exe(processo, timeout=timeout_janela)
        except TimeoutError as exc:
            em_exec = _listar_processos_fc()
            extra = ""
            if em_exec:
                extra = f"\nProcessos FC abertos: {', '.join(em_exec)}"
            raise TimeoutError(
                f"{exc}. Abra o modulo no Fcerta antes de mapear.{extra}"
            ) from exc

    logger.info(f"Conectando via {exe_path}...")
    return conectar_ou_iniciar(exe_path)


def _emitir(on_progress: Callable[[str], None] | None, msg: str) -> None:
    logger.info(msg)
    if on_progress:
        on_progress(msg)


def _safe_visible(ctrl) -> bool | None:
    try:
        return bool(ctrl.is_visible())
    except Exception as exc:
        logger.debug(f"is_visible falhou: {exc}")
        return None


def _safe_enabled(ctrl) -> bool | None:
    try:
        return bool(ctrl.is_enabled())
    except Exception as exc:
        logger.debug(f"is_enabled falhou: {exc}")
        return None


def _safe_rectangle(ctrl) -> list[int] | None:
    try:
        rect = ctrl.rectangle()
        return [rect.left, rect.top, rect.right, rect.bottom]
    except Exception as exc:
        logger.debug(f"rectangle falhou: {exc}")
        return None


def _coletar_elemento(
    ctrl,
    locator: ElementLocator,
    class_name: str,
    incluir_ocultos: bool,
) -> dict | None:
    visible = _safe_visible(ctrl)
    if not incluir_ocultos and visible is not True:
        return None

    rectangle = _safe_rectangle(ctrl)
    if rectangle is None:
        logger.warning(f"Sem rectangle para {class_name} — elemento ignorado")
        return None

    enabled = _safe_enabled(ctrl)
    if enabled is None:
        logger.warning(f"Sem is_enabled para {class_name} — elemento ignorado")
        return None

    return {
        "class_name": class_name,
        "title": locator._safe_title(ctrl) or "",
        "is_enabled": enabled,
        "is_visible": visible if visible is not None else False,
        "rectangle": rectangle,
    }


def _safe_handle(ctrl) -> int | None:
    try:
        return ctrl.handle
    except Exception:
        return None


def _varrer_recursivo(janela) -> list:
    """
    Percorre TODA a arvore de controles em profundidade (depth-first), descendo
    explicitamente em qualquer container — paineis (TPanel), sessoes/group boxes
    (TGroupBox), page controls e abas (TPageControl/TTabSheet), scroll boxes etc.
    — em qualquer nivel de aninhamento.

    Garante que campos aninhados dentro de sessoes/paineis sejam alcancados, sem
    duplicar (dedup por handle nativo).
    """
    coletados: list = []
    vistos: set[int] = set()

    try:
        raizes = list(janela.children())
    except Exception as exc:
        logger.debug(f"children() da janela falhou: {exc}")
        raizes = []

    pilha = list(reversed(raizes))
    while pilha:
        ctrl = pilha.pop()
        handle = _safe_handle(ctrl)
        if handle is not None:
            if handle in vistos:
                continue
            vistos.add(handle)

        coletados.append(ctrl)

        # Desce SEMPRE no controle, seja ele um campo ou um container. Assim
        # campos dentro de paineis/sessoes em qualquer nivel sao alcancados.
        try:
            filhos = list(ctrl.children())
        except Exception as exc:
            logger.debug(f"children() falhou em descendente: {exc}")
            filhos = []
        if filhos:
            pilha.extend(reversed(filhos))

    return coletados


def _arvore_completa(
    janela,
    on_progress: Callable[[str], None] | None,
) -> list:
    """
    Lista completa de descendentes em qualquer nivel, sem duplicar.

    Usa primeiro `descendants()` (mesma enumeracao que `child_window` emprega em
    tempo de execucao) para preservar a ordem usada no calculo de `found_index`.
    Em seguida reforca com uma varredura recursiva explicita por `.children()`,
    anexando ao final apenas controles que `descendants()` nao tenha alcancado —
    garantindo abrangencia em paineis/sessoes sem alterar os indices ja validos.
    """
    handles: set[int] = set()
    ordenados: list = []

    try:
        base = list(janela.descendants())
    except Exception as exc:
        logger.warning(f"descendants() da janela falhou: {exc}")
        base = []

    for ctrl in base:
        handle = _safe_handle(ctrl)
        if handle is not None:
            if handle in handles:
                continue
            handles.add(handle)
        ordenados.append(ctrl)

    extras = 0
    for ctrl in _varrer_recursivo(janela):
        handle = _safe_handle(ctrl)
        if handle is not None and handle in handles:
            continue
        if handle is not None:
            handles.add(handle)
        ordenados.append(ctrl)
        extras += 1

    if extras:
        _emitir(
            on_progress,
            f"  +{extras} controles adicionais via varredura recursiva de paineis/sessoes.",
        )

    return ordenados


def _varrer_janela(
    janela,
    locator: ElementLocator,
    incluir_ocultos: bool,
    on_progress: Callable[[str], None] | None,
) -> list[dict]:
    elementos: list[dict] = []
    class_counters: dict[str, int] = defaultdict(int)
    tree_instance = 0

    _emitir(on_progress, "Coletando arvore completa de controles (todos os niveis)...")
    todos = _arvore_completa(janela, on_progress)
    _emitir(on_progress, f"  {len(todos)} controles na arvore (todos os niveis).")

    # Agrupa por classe relevante preservando a ordem depth-first de descendants(),
    # mantendo o found_index consistente com window.child_window(found_index=...).
    por_classe: dict[str, list] = defaultdict(list)
    for ctrl in todos:
        cls = locator._safe_class(ctrl)
        if cls in _RELEVANT_SET:
            por_classe[cls].append(ctrl)

    for class_name in RELEVANT_CLASSES:
        controles = por_classe.get(class_name)
        if not controles:
            continue

        _emitir(on_progress, f"Varrendo {class_name}...")
        n_classe = 0
        for ctrl in controles:
            try:
                item = _coletar_elemento(ctrl, locator, class_name, incluir_ocultos)
                if item is None:
                    continue

                tree_instance += 1
                item["found_index"] = class_counters[class_name]
                item["instance"] = tree_instance
                class_counters[class_name] += 1
                elementos.append(item)
                n_classe += 1
            except Exception as exc:
                logger.warning(f"Erro ao processar {class_name}: {exc}")
                continue

        _emitir(on_progress, f"  {class_name}: {n_classe} exportados (total {len(elementos)})")

    return elementos


def mapear_janela(
    titulo: str | None = None,
    *,
    processo: str | None = None,
    exe_path: str | None = None,
    timeout_janela: float = 30,
    incluir_ocultos: bool = True,
    on_progress: Callable[[str], None] | None = None,
) -> Path:
    """
    Conecta ao sistema ou modulo, localiza a janela e exporta controles em JSON.

    Args:
        titulo: Titulo exato, regex:... ou padrao regex. Opcional se processo informado.
        processo: Nome do .exe do modulo (ex. FCFiliais.exe) — usa wait_app_by_exe.
        exe_path: Caminho do exe principal; se None, le de config.json.
        timeout_janela: Segundos para aguardar processo/janela.
        incluir_ocultos: Se True, exporta controles de abas ocultas (is_visible=False).
        on_progress: Callback opcional para feedback na UI.

    Returns:
        Path do arquivo JSON gerado.
    """
    titulo, processo = _resolver_entrada(titulo, processo)

    if not titulo and not processo:
        raise ValueError("Informe o titulo da janela ou o processo do modulo (.exe).")

    cfg = carregar_config()
    exe_path = exe_path or cfg.get("exe_path", _DEFAULT_EXE)

    _emitir(on_progress, "Conectando ao aplicativo...")
    app = _conectar_app(
        processo=processo,
        exe_path=exe_path,
        timeout_janela=timeout_janela,
    )

    _emitir(on_progress, "Localizando janela...")
    janela = _obter_janela(app, titulo, timeout_janela, processo)

    locator = ElementLocator()
    _emitir(on_progress, "Iniciando varredura (telas grandes podem levar 1-3 min)...")
    elementos = _varrer_janela(janela, locator, incluir_ocultos, on_progress)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = _slug_titulo(titulo or "", processo)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"mapeamento_{slug}_{ts}.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(elementos, f, ensure_ascii=False, indent=2)

    _emitir(on_progress, f"Total exportado: {len(elementos)}")
    for cls_name, count in sorted(Counter(e["class_name"] for e in elementos).items()):
        logger.info(f"  {cls_name}: {count}")

    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mapeia controles Delphi/VCL de uma janela aberta e exporta JSON.",
    )
    parser.add_argument(
        "--titulo",
        default=None,
        help="Titulo da janela, regex:... ou regex implicito. Opcional com --processo.",
    )
    parser.add_argument(
        "--processo",
        default=None,
        help="Processo do modulo (ex.: FCFiliais.exe) — conecta via wait_app_by_exe.",
    )
    parser.add_argument(
        "--exe",
        default=None,
        help="Caminho do executavel principal (padrao: config.json exe_path)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30,
        help="Timeout em segundos para aguardar processo/janela (padrao: 30)",
    )
    parser.add_argument(
        "--somente-visiveis",
        action="store_true",
        help="Exportar apenas controles com is_visible=True (padrao: incluir abas ocultas)",
    )
    args = parser.parse_args()

    setup_logging(log_name="mapear_janela")

    incluir_ocultos = not args.somente_visiveis

    if not args.titulo and not args.processo:
        parser.error("Informe --titulo e/ou --processo.")

    try:
        out_path = mapear_janela(
            args.titulo,
            processo=args.processo,
            exe_path=args.exe,
            timeout_janela=args.timeout,
            incluir_ocultos=incluir_ocultos,
        )
        print(f"Arquivo gerado: {out_path}")
        return 0
    except Exception as exc:
        logger.error(f"Falha no mapeamento: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
