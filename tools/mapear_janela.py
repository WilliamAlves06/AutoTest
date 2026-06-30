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
    "TToolButton",
    # Campos de texto / edicao
    "TEdit",
    "TMemo",
    "TwwDBEdit",
    "TDBEdit",
    "TDBMemo",
    "TwwDBRichEdit",
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
    "TwwDBDateTimePicker",
    # Grades
    "TwwDBGrid",
    "TDBGrid",
    "TStringGrid",
    # Rotulos
    "TLabel",
    # DevExpress (ExpressEditors / ExpressBars / ExpressGrid / ExpressPageControl)
    # — confirmado no .dfm de FC11 (form principal de Filiais): o modulo mistura
    # InfoPower (Tww*), componentes proprios (TFagron*) e DevExpress (Tcx*).
    "TcxButton",
    "TcxCheckBox",
    "TcxDBCheckBox",
    "TcxDBLookupComboBox",
    "TcxCustomComboBoxInnerEdit",
    "TcxGrid",
    "TcxPageControl",
    "TcxTabSheet",
    # JVCL
    "TJvDBComboBox",
)

# Conjunto para teste de pertinencia O(1) durante a varredura recursiva.
_RELEVANT_SET = frozenset(RELEVANT_CLASSES)

# Alguns controles (botoes de toolbar do DevExpress, rotulos estaticos) nao
# expoem class_name nenhum via UIA — so dao para identificar pelo control_type/
# friendly_class_name. Mapeia o control_type da UIA para um rotulo de exportacao.
_FALLBACK_CONTROL_TYPES = {
    "Button": "Button",
    "Edit": "Edit",
    "ComboBox": "ComboBox",
    "CheckBox": "CheckBox",
    "Text": "Static",
}

# friendly_class_name de elementos de moldura da janela (barra de titulo, menu)
# que tambem aparecem com class_name vazio mas nao sao campos do formulario.
_FALLBACK_EXCLUDE_FRIENDLY = frozenset({
    "TitleBar", "Menu", "MenuBar", "MenuItem", "ScrollBar",
})

# Legendas dos botoes de controle da janela (minimizar/maximizar/fechar) —
# tambem reportam control_type=Button com class_name vazio, mas nao sao campos.
_FALLBACK_EXCLUDE_TEXT = frozenset({
    "minimizar", "maximizar", "restaurar", "fechar",
    "minimize", "maximize", "restore", "close",
})


def _safe_friendly(ctrl) -> str:
    try:
        return ctrl.friendly_class_name() or ""
    except Exception:
        return ""


def _classificar_controle(ctrl, locator: ElementLocator) -> tuple[str, str] | None:
    """
    Decide se um controle deve ser exportado e sob qual rotulo de agrupamento.

    1. Se tiver class_name conhecido (VCL/DevExpress/JVCL em RELEVANT_CLASSES),
       agrupa por ele — comportamento original.
    2. Se class_name vier vazio (comum em botoes de toolbar e rotulos estaticos
       do DevExpress, que a UIA expoe sem ClassName), usa control_type/
       friendly_class_name como fallback — e descarta elementos de moldura da
       janela (titulo, menu, botoes minimizar/maximizar/fechar).

    Retorna (chave_de_agrupamento, rotulo_para_exportacao) ou None se irrelevante.
    """
    cls = locator._safe_class(ctrl)
    if cls:
        return (cls, cls) if cls in _RELEVANT_SET else None

    friendly = _safe_friendly(ctrl)
    if friendly in _FALLBACK_EXCLUDE_FRIENDLY:
        return None

    control_type = locator._safe_control_type(ctrl) or ""
    rotulo = _FALLBACK_CONTROL_TYPES.get(control_type)
    if rotulo is None:
        return None

    texto = (locator._safe_title(ctrl) or "").strip().lower()
    if texto in _FALLBACK_EXCLUDE_TEXT:
        return None

    return (f"?{rotulo}", rotulo)


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
        logger.warning(f"is_visible falhou (provavel erro COM): {exc}", exc_info=True)
        return None


def _safe_enabled(ctrl) -> bool | None:
    try:
        return bool(ctrl.is_enabled())
    except Exception as exc:
        logger.warning(f"is_enabled falhou (provavel erro COM): {exc}", exc_info=True)
        return None


def _safe_rectangle(ctrl) -> list[int] | None:
    try:
        rect = ctrl.rectangle()
        return [rect.left, rect.top, rect.right, rect.bottom]
    except Exception as exc:
        logger.warning(f"rectangle falhou (provavel erro COM): {exc}", exc_info=True)
        return None


def _safe_automation_id(ctrl) -> str:
    try:
        v = ctrl.automation_id()
        return str(v).strip() if v else ""
    except Exception:
        return ""


def _coletar_elemento(
    ctrl,
    locator: ElementLocator,
    rotulo: str,
    incluir_ocultos: bool,
) -> dict | None:
    visible = _safe_visible(ctrl)
    if not incluir_ocultos and visible is not True:
        return None

    titulo_ctrl = locator._safe_title(ctrl) or ""

    rectangle = _safe_rectangle(ctrl)
    if rectangle is None:
        logger.warning(f"Sem rectangle para {rotulo} '{titulo_ctrl}' — elemento ignorado")
        return None

    enabled = _safe_enabled(ctrl)
    if enabled is None:
        logger.warning(f"Sem is_enabled para {rotulo} '{titulo_ctrl}' — elemento ignorado")
        return None

    return {
        # class_name real do controle (pode vir vazio — ver _classificar_controle;
        # nesse caso control_type/automation_id sao as unicas formas de localiza-lo).
        "class_name": locator._safe_class(ctrl) or "",
        "control_type": locator._safe_control_type(ctrl) or "",
        "automation_id": _safe_automation_id(ctrl),
        "title": titulo_ctrl,
        "is_enabled": enabled,
        "is_visible": visible if visible is not None else False,
        "rectangle": rectangle,
    }


def _safe_handle(ctrl) -> int | None:
    try:
        return ctrl.handle
    except Exception:
        return None


def _varrer_recursivo(janela) -> tuple[list, int]:
    """
    Percorre TODA a arvore de controles em profundidade (depth-first), descendo
    explicitamente em qualquer container — paineis (TPanel), sessoes/group boxes
    (TGroupBox), page controls e abas (TPageControl/TTabSheet), scroll boxes etc.
    — em qualquer nivel de aninhamento.

    Garante que campos aninhados dentro de sessoes/paineis sejam alcancados, sem
    duplicar (dedup por handle nativo).

    Retorna (controles_coletados, total_de_falhas_em_children). Falhas aqui
    costumam ser erros COM (ex.: thread sem CoInitialize) que truncam a
    travessia silenciosamente — por isso sao contadas e logadas com traceback.
    """
    coletados: list = []
    vistos: set[int] = set()
    falhas = 0

    try:
        raizes = list(janela.children())
    except Exception as exc:
        logger.warning(f"children() da janela falhou (provavel erro COM): {exc}", exc_info=True)
        falhas += 1
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
            logger.warning(
                f"children() falhou em descendente '{_safe_class_for_log(ctrl)}' "
                f"(provavel erro COM): {exc}",
                exc_info=True,
            )
            falhas += 1
            filhos = []
        if filhos:
            pilha.extend(reversed(filhos))

    return coletados, falhas


def _safe_class_for_log(ctrl) -> str:
    try:
        return ctrl.class_name() or "?"
    except Exception:
        return "?"


def _assinatura_visual(ctrl) -> tuple:
    """
    Identidade visual estavel para deduplicar controles "sem janela" propria
    (ex.: TFagronButton/TLabel, pintados no canvas do painel pai — sem HWND).
    Esses controles podem ser descobertos duas vezes pela travessia
    (descendants() + varredura recursiva de paineis), cada vez com um
    `.handle` diferente para o mesmo elemento visual — entao o dedup por
    handle nao os pega. O par (control_type, texto, automation_id, retangulo)
    identifica o elemento de forma estavel independente de qual caminho da
    travessia o descobriu.
    """
    try:
        r = ctrl.rectangle()
        rect = (r.left, r.top, r.right, r.bottom)
    except Exception:
        rect = None
    try:
        ctrl_type = str(ctrl.element_info.control_type)
    except Exception:
        ctrl_type = None
    try:
        texto = ctrl.window_text()
    except Exception:
        texto = None
    try:
        auto_id = ctrl.automation_id()
    except Exception:
        auto_id = None
    return (ctrl_type, texto, auto_id, rect)


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
    assinaturas: set[tuple] = set()
    ordenados: list = []

    def _ja_visto(ctrl) -> bool:
        """Marca o controle como visto; retorna True se ja apareceu antes.
        Usa handle quando disponivel; senao cai para a assinatura visual
        (controles sem HWND propria — ver _assinatura_visual)."""
        handle = _safe_handle(ctrl)
        if handle is not None:
            if handle in handles:
                return True
            handles.add(handle)
            return False
        assinatura = _assinatura_visual(ctrl)
        if assinatura in assinaturas:
            return True
        assinaturas.add(assinatura)
        return False

    try:
        base = list(janela.descendants())
    except Exception as exc:
        logger.warning(f"descendants() da janela falhou (provavel erro COM): {exc}", exc_info=True)
        base = []

    for ctrl in base:
        if _ja_visto(ctrl):
            continue
        ordenados.append(ctrl)

    extras = 0
    coletados_recursivo, falhas = _varrer_recursivo(janela)
    for ctrl in coletados_recursivo:
        if _ja_visto(ctrl):
            continue
        ordenados.append(ctrl)
        extras += 1

    if extras:
        _emitir(
            on_progress,
            f"  +{extras} controles adicionais via varredura recursiva de paineis/sessoes.",
        )
    if falhas:
        _emitir(
            on_progress,
            f"  Aviso: {falhas} falha(s) ao listar filhos durante a travessia "
            f"(possivel COM nao inicializado na thread) — veja o log para detalhes.",
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

    # Classifica cada controle: por class_name conhecido (RELEVANT_CLASSES) ou,
    # quando a UIA nao expoe class_name (botoes de toolbar/rotulos do DevExpress),
    # por control_type/friendly_class_name (ver _classificar_controle). Preserva
    # a ordem depth-first de descendants(), mantendo found_index consistente com
    # window.child_window(found_index=...) para os grupos de classe conhecida.
    por_grupo: dict[str, list] = defaultdict(list)
    rotulos: dict[str, str] = {}
    ordem_fallback: list[str] = []
    for ctrl in todos:
        classificacao = _classificar_controle(ctrl, locator)
        if classificacao is None:
            continue
        chave, rotulo = classificacao
        if chave not in por_grupo:
            rotulos[chave] = rotulo
            if chave not in _RELEVANT_SET:
                ordem_fallback.append(chave)
        por_grupo[chave].append(ctrl)

    # Classes conhecidas primeiro (na ordem de RELEVANT_CLASSES, compativel com
    # mapeamentos anteriores), depois os grupos de fallback na ordem em que
    # surgiram na arvore (botoes de toolbar, rotulos estaticos sem class_name).
    chaves = [c for c in RELEVANT_CLASSES if c in por_grupo] + ordem_fallback

    for chave in chaves:
        controles = por_grupo[chave]
        rotulo = rotulos[chave]

        _emitir(on_progress, f"Varrendo {rotulo}...")
        n_classe = 0
        for ctrl in controles:
            try:
                item = _coletar_elemento(ctrl, locator, rotulo, incluir_ocultos)
                if item is None:
                    continue

                tree_instance += 1
                item["found_index"] = class_counters[chave]
                item["instance"] = tree_instance
                class_counters[chave] += 1
                elementos.append(item)
                n_classe += 1
            except Exception as exc:
                logger.warning(f"Erro ao processar {rotulo}: {exc}")
                continue

        _emitir(on_progress, f"  {rotulo}: {n_classe} exportados (total {len(elementos)})")

    # Posição RELATIVA à janela (origem = canto da janela). É o localizador estável
    # usado pelo recorder para cruzar o clique com o alias — independe de
    # automation_id (volátil) e found_index (enumeração divergente).
    _anexar_rect_relativo(janela, elementos)

    return elementos


def _anexar_rect_relativo(janela, elementos: list[dict]) -> None:
    """Adiciona `rect` = [l,t,r,b] relativo ao canto da janela a cada elemento."""
    origem = _safe_rectangle(janela)
    if not origem:
        return
    ox, oy = origem[0], origem[1]
    for el in elementos:
        abs_rect = el.get("rectangle")
        if not abs_rect or len(abs_rect) != 4:
            continue
        l, t, r, b = abs_rect
        el["rect"] = [l - ox, t - oy, r - ox, b - oy]


def merge_key(el: dict) -> tuple:
    """Identidade estavel p/ mesclagem entre passes de varredura: automation_id
    quando disponivel (estavel no Delphi); senao control_type+title+class_name."""
    aid = (el.get("automation_id") or "").strip()
    if aid:
        return ("aid", aid)
    return ("ct", el.get("control_type") or "", el.get("title") or "", el.get("class_name") or "")


def mesclar_elementos(base: list[dict], novos: list[dict]) -> tuple[list[dict], int]:
    """Funde `novos` em `base` por merge_key(), preservando a 1a ocorrencia de
    cada chave (mesmo automation_id ja coletado nao e duplicado). Retorna
    (lista_resultante, quantidade_de_novos_adicionados)."""
    chaves = {merge_key(el) for el in base}
    resultado = list(base)
    adicionados = 0
    for el in novos:
        k = merge_key(el)
        if k in chaves:
            continue
        chaves.add(k)
        resultado.append(el)
        adicionados += 1
    return resultado, adicionados


def _safe_select_tab(tab_ctrl, on_progress: Callable[[str], None] | None) -> bool:
    """
    Tenta selecionar a aba `tab_ctrl` (TcxTabSheet ou seu header). Cascata, da
    estrategia menos intrusiva para a mais intrusiva:

      1. tab_ctrl.select()      -- UIA SelectionItemPattern (sem coordenadas;
                                    so funciona se o controle DevExpress expuser
                                    o padrao).
      2. tab_ctrl.click_input() -- clique de mouse no centro do retangulo do
                                    proprio controle (fallback quase universal
                                    para controles owner-drawn).

    Retorna True se um dos passos nao lancou excecao — isso NAO garante que a
    aba de fato mudou; quem chama deve confirmar relendo a TcxTabSheet ativa
    (ver `_aba_ativa_titulo`).
    """
    try:
        tab_ctrl.select()
        _emitir(on_progress, "  [diag] select() funcionou na aba.")
        return True
    except Exception as exc:
        _emitir(on_progress, f"  [diag] select() falhou em aba (provavel sem SelectionItemPattern): {exc}")

    try:
        tab_ctrl.click_input()
        _emitir(on_progress, "  [diag] click_input() funcionou na aba.")
        return True
    except Exception as exc:
        _emitir(on_progress, f"  Aviso: falha ao selecionar aba — {exc}")
        return False


def _descobrir_abas(
    pagecontrol_ctrl,
    locator: ElementLocator,
    on_progress: Callable[[str], None] | None,
) -> list:
    """
    Retorna a lista de wrappers de "header" de cada aba do TcxPageControl, na
    ordem visual. Cascata:

      1. children(control_type="TabItem") direto no pagecontrol — se a
         DevExpress expuser os headers das abas como TabItem.
      2. children() sem filtro, descartando o(s) que ocupam quase toda a
         altura do pagecontrol (esse e o pane de conteudo da aba ativa, nao um
         header) — heuristica best-effort.
      3. Se nada for encontrado de forma confiavel, retorna [] — o caller cai
         no fallback de Ctrl+Tab (ver `_ciclar_e_varrer_por_tab`).
    """
    try:
        headers = list(pagecontrol_ctrl.children(control_type="TabItem"))
        _emitir(on_progress, f"  [diag] children(control_type=TabItem): {len(headers)} candidato(s).")
        if headers:
            return headers
    except Exception as exc:
        _emitir(on_progress, f"  [diag] children(control_type=TabItem) falhou: {exc}")

    try:
        candidatos = list(pagecontrol_ctrl.children())
    except Exception as exc:
        _emitir(on_progress, f"  [diag] children() do TcxPageControl falhou: {exc}")
        return []

    pc_rect = _safe_rectangle(pagecontrol_ctrl)
    _emitir(
        on_progress,
        f"  [diag] TcxPageControl.children() sem filtro: {len(candidatos)} candidato(s); "
        f"rect do pagecontrol={pc_rect}.",
    )
    headers = []
    for idx, c in enumerate(candidatos):
        rect = _safe_rectangle(c)
        cls = locator._safe_class(c)
        ctrl_type = locator._safe_control_type(c)
        if rect is None or pc_rect is None:
            _emitir(on_progress, f"  [diag] candidato {idx}: class={cls!r} control_type={ctrl_type!r} sem rectangle — descartado.")
            continue
        altura_relativa = (rect[3] - rect[1]) / max(1, pc_rect[3] - pc_rect[1])
        # heuristica: headers ocupam uma faixa baixa (<35%) da altura total;
        # o pane de conteudo (TcxTabSheet ativa) ocupa quase tudo.
        aceito = altura_relativa < 0.35
        _emitir(
            on_progress,
            f"  [diag] candidato {idx}: class={cls!r} control_type={ctrl_type!r} rect={rect} "
            f"altura_relativa={altura_relativa:.2f} -> {'aceito' if aceito else 'descartado'}.",
        )
        if aceito:
            headers.append(c)
    return headers


def _aba_ativa_titulo(elementos: list[dict]) -> str | None:
    """Le o title da (unica) TcxTabSheet presente neste passe de varredura."""
    for el in elementos:
        if el.get("class_name") == "TcxTabSheet":
            return el.get("title") or ""
    return None


def _sheets_donas(elementos: list[dict]) -> list[tuple[str, list[int], int]]:
    """TcxTabSheets que mandam neste passe -> [(titulo, rect_abs, area)].

    Usa apenas as abas VISIVEIS (is_visible): num passe so uma aba esta ativa por
    nivel, e e ela quem contem os campos recem-coletados. Varias TcxTabSheets do
    mesmo PageControl compartilham o mesmo retangulo, entao a visibilidade — nao a
    geometria — e quem desempata qual e a ativa. Sem nenhuma visivel (raro), cai
    para a primeira TcxTabSheet, espelhando `_aba_ativa_titulo`.
    """
    visiveis: list[tuple[str, list[int], int]] = []
    primeira: tuple[str, list[int], int] | None = None
    for el in elementos:
        if el.get("class_name") != "TcxTabSheet":
            continue
        r = el.get("rectangle")
        if not r or len(r) != 4:
            continue
        area = max(1, r[2] - r[0]) * max(1, r[3] - r[1])
        item = (el.get("title") or "", r, area)
        if primeira is None:
            primeira = item
        if el.get("is_visible"):
            visiveis.append(item)
    if visiveis:
        return visiveis
    return [primeira] if primeira is not None else []


def _marcar_aba(elementos: list[dict]) -> None:
    """Anota `el['aba']` = caminho de abas (externa->interna) que contem o campo.

    O dono e a(s) TcxTabSheet(s) visivel(eis) cujo retangulo contem o CENTRO do
    elemento. Abas aninhadas (ex.: 'Livros/Mapas' -> 'Anvisa') geram um caminho com
    varios niveis, ordenado pela area (a externa e maior, a interna e inset). Campos
    FORA de qualquer aba (toolbar incluir/alterar, campo de consulta) ficam sem `aba`.
    """
    sheets = _sheets_donas(elementos)
    if not sheets:
        return
    for el in elementos:
        if el.get("class_name") in ("TcxTabSheet", "TcxPageControl"):
            continue
        r = el.get("rectangle")
        if not r or len(r) != 4:
            continue
        cx, cy = (r[0] + r[2]) // 2, (r[1] + r[3]) // 2
        donos = [
            (area, titulo)
            for (titulo, sr, area) in sheets
            if sr[0] <= cx <= sr[2] and sr[1] <= cy <= sr[3]
        ]
        if donos:
            donos.sort(reverse=True)  # area desc -> da aba externa para a interna
            el["aba"] = [titulo for _, titulo in donos]


def _ciclar_e_varrer_por_tab(
    janela,
    pagecontrol_ctrl,
    locator: ElementLocator,
    incluir_ocultos: bool,
    on_progress: Callable[[str], None] | None,
    max_abas: int = 12,
) -> list[list[dict]]:
    """
    Usado quando `_descobrir_abas()` nao retorna headers utilizaveis: varre a
    aba atual, foca o TcxPageControl e manda Ctrl+Tab, varre de novo, repete —
    ate detectar que voltou a aba inicial (pelo title da TcxTabSheet ativa) ou
    ate `max_abas` iteracoes (protecao contra loop infinito se a deteccao de
    "voltou ao inicio" falhar).

    O `.set_focus()` no pagecontrol antes do Ctrl+Tab e deliberado: sem ele a
    tecla vai pro foco corrente da janela (ex.: um campo de texto na aba
    ativa), que normalmente NAO repassa Ctrl+Tab pro page control — suspeito
    de ser a causa de o Ctrl+Tab nao mudar de aba nas tentativas anteriores.

    Retorna uma lista de listas de elementos, uma por passe/aba.
    """
    passes: list[list[dict]] = []
    titulo_inicial = None
    for i in range(max_abas):
        elementos = _varrer_janela(janela, locator, incluir_ocultos, on_progress)
        passes.append(elementos)
        titulo_atual = _aba_ativa_titulo(elementos)
        _emitir(on_progress, f"  [diag] Ctrl+Tab passe {i}: aba ativa = {titulo_atual!r}.")
        if i == 0:
            titulo_inicial = titulo_atual
        elif titulo_atual == titulo_inicial:
            _emitir(on_progress, "  [diag] titulo da aba voltou ao inicial — ciclo completo, parando.")
            break  # ciclo completo — voltou pro inicio
        try:
            pagecontrol_ctrl.set_focus()
        except Exception as exc:
            _emitir(on_progress, f"  [diag] set_focus() no TcxPageControl falhou: {exc}")
        try:
            janela.type_keys("^{TAB}")
        except Exception as exc:
            _emitir(on_progress, f"  [diag] type_keys Ctrl+Tab falhou: {exc}")
            break
    return passes


def varrer_todas_as_abas(
    janela,
    locator: ElementLocator,
    incluir_ocultos: bool,
    on_progress: Callable[[str], None] | None,
) -> list[dict]:
    """
    Varre a janela uma vez por aba de cada TcxPageControl encontrado, mesclando
    os resultados num unico conjunto de elementos. Se a janela nao tiver
    TcxPageControl (ou tiver so uma aba), e equivalente a uma unica chamada de
    `_varrer_janela` — sem custo extra.

    Best-effort: se a selecao de uma aba falhar, registra aviso via
    `on_progress` e segue para a proxima, preservando o que ja foi coletado.
    """
    elementos = _varrer_janela(janela, locator, incluir_ocultos, on_progress)
    _marcar_aba(elementos)  # passe inicial: aba ativa ao abrir o modulo

    todos_ctrls = _arvore_completa(janela, on_progress)
    pagecontrols = [c for c in todos_ctrls if locator._safe_class(c) == "TcxPageControl"]

    if not pagecontrols:
        return elementos  # nao ha abas — comportamento identico ao de hoje

    for pc in pagecontrols:
        _emitir(on_progress, "Detectado TcxPageControl — varrendo abas adicionais...")
        headers = _descobrir_abas(pc, locator, on_progress)

        if len(headers) <= 1:
            _emitir(on_progress, "  Headers de aba nao identificados — usando Ctrl+Tab.")
            passes = _ciclar_e_varrer_por_tab(janela, pc, locator, incluir_ocultos, on_progress)
            for passe in passes[1:]:  # passes[0] ja esta em elementos
                _marcar_aba(passe)
                elementos, n = mesclar_elementos(elementos, passe)
                _emitir(on_progress, f"  +{n} elemento(s) novo(s) (Ctrl+Tab).")
            continue

        _emitir(on_progress, f"  {len(headers)} aba(s) detectada(s).")
        for i, header in enumerate(headers):
            ok = _safe_select_tab(header, on_progress)
            if not ok:
                _emitir(on_progress, f"  Aviso: nao foi possivel selecionar aba {i + 1}/{len(headers)} — pulando.")
                continue
            passe = _varrer_janela(janela, locator, incluir_ocultos, on_progress)
            _marcar_aba(passe)
            elementos, n = mesclar_elementos(elementos, passe)
            titulo = _aba_ativa_titulo(passe) or f"aba {i + 1}"
            _emitir(on_progress, f"  Aba '{titulo}': +{n} elemento(s) novo(s).")

    return elementos


def mapear_janela(
    titulo: str | None = None,
    *,
    processo: str | None = None,
    exe_path: str | None = None,
    timeout_janela: float = 30,
    incluir_ocultos: bool = True,
    on_progress: Callable[[str], None] | None = None,
    varrer_todas_abas: bool = False,
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
        varrer_todas_abas: Se True, alem da aba ativa, percorre e mescla todas as
            abas de qualquer TcxPageControl encontrado (mais lento — ver
            `varrer_todas_as_abas`).

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
    if varrer_todas_abas:
        _emitir(on_progress, "Modo 'todas as abas' ativado — pode levar varios minutos.")
        # Sink dedicado: o on_progress de quem chama pode ser efemero (ex.: um
        # label de status que se sobrescreve) — este arquivo registra TODA
        # mensagem (incl. DEBUG) desta varredura, sempre, independente da UI.
        log_dir = ROOT / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        sink_id = logger.add(
            log_dir / "mapear_abas_debug.log",
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {function}:{line} — {message}",
            encoding="utf-8",
            mode="w",
        )
        try:
            elementos = varrer_todas_as_abas(janela, locator, incluir_ocultos, on_progress)
        finally:
            logger.remove(sink_id)
    else:
        elementos = _varrer_janela(janela, locator, incluir_ocultos, on_progress)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = _slug_titulo(titulo or "", processo)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"mapeamento_{slug}_{ts}.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(elementos, f, ensure_ascii=False, indent=2)

    _emitir(on_progress, f"Total exportado: {len(elementos)}")
    # Elementos sem class_name (fallback por control_type) sao agrupados pelo
    # control_type no resumo, senao todos cairiam juntos sob a chave vazia "".
    def _chave_resumo(item: dict) -> str:
        return item["class_name"] or f"(sem class_name) {item.get('control_type', '?')}"

    for chave, count in sorted(Counter(_chave_resumo(e) for e in elementos).items()):
        logger.info(f"  {chave}: {count}")

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
    parser.add_argument(
        "--todas-abas",
        action="store_true",
        help="Varre automaticamente todas as abas de TcxPageControl (mais lento).",
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
            varrer_todas_abas=args.todas_abas,
        )
        print(f"Arquivo gerado: {out_path}")
        return 0
    except Exception as exc:
        logger.error(f"Falha no mapeamento: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
