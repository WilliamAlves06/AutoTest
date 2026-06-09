import time
import datetime
from pathlib import Path
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from pywinauto.base_wrapper import ElementNotEnabled, ElementNotVisible
from pywinauto import Application
import pyautogui

SCREENSHOT_DIR = Path("logs/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def conectar_ou_iniciar(exe_path: str, timeout: float = 3) -> Application:
    """Conecta ao processo em execucao ou inicia pelo caminho do exe."""
    try:
        app = Application(backend="uia").connect(path=exe_path, timeout=timeout)
        logger.info("Conectado ao sistema ja aberto.")
        return app
    except Exception:
        logger.info("Sistema nao estava aberto — iniciando...")
        return Application(backend="uia").start(exe_path)


def screenshot_on_failure(label: str = "erro") -> Path | None:
    """Tira screenshot e salva com timestamp. Nao propaga erro se Pillow/pyscreeze falhar."""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SCREENSHOT_DIR / f"{label}_{ts}.png"
    try:
        pyautogui.screenshot(str(path))
        logger.warning(f"Screenshot salvo: {path}")
        return path
    except Exception as exc:
        saved = _screenshot_win32(path)
        if saved:
            logger.warning(f"Screenshot salvo (win32): {path}")
            return path
        logger.warning(f"Screenshot indisponivel: {exc}")
        return None


def _screenshot_win32(path: Path) -> bool:
    """Captura tela via Win32 (funciona sem Pillow / Python 3.14)."""
    try:
        import win32gui
        import win32ui
        import win32con
        import win32api

        width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
        top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)

        hdesktop = win32gui.GetDesktopWindow()
        desktop_dc = win32gui.GetWindowDC(hdesktop)
        img_dc = win32ui.CreateDCFromHandle(desktop_dc)
        mem_dc = img_dc.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(img_dc, width, height)
        mem_dc.SelectObject(bmp)
        mem_dc.BitBlt((0, 0), (width, height), img_dc, (left, top), win32con.SRCCOPY)

        bmp_path = path.with_suffix(".bmp")
        bmp.SaveBitmapFile(mem_dc, str(bmp_path))

        mem_dc.DeleteDC()
        win32gui.ReleaseDC(hdesktop, desktop_dc)
        img_dc.DeleteDC()
        win32gui.DeleteObject(bmp.GetHandle())

        if bmp_path != path and bmp_path.exists():
            try:
                from PIL import Image
                Image.open(bmp_path).save(path)
                bmp_path.unlink(missing_ok=True)
            except Exception:
                path = bmp_path
        return path.exists()
    except Exception:
        return False
 
def wait_element(
    window,
    title: str = None,
    class_name: str = None,
    found_index: int = None,
    auto_id: str = None,
    control_type: str = None,
    timeout: float = 15.0,
    label: str = "elemento",
) -> object:
    kwargs = {}
    if title:
        kwargs["title"] = title
    if class_name:
        kwargs["class_name"] = class_name
    if auto_id:
        kwargs["auto_id"] = str(auto_id)
    if control_type:
        kwargs["control_type"] = control_type
    if found_index is not None:
        kwargs["found_index"] = found_index

    deadline = time.time() + timeout
    last_exc = None

    while time.time() < deadline:
        try:
            el = window.child_window(**kwargs)
            el.wait("visible enabled", timeout=2)
            logger.debug(f"Elemento encontrado: {label}")
            return el
        except Exception as e:
            last_exc = e
            time.sleep(0.3)

    screenshot_on_failure(f"timeout_{label.replace(' ', '_')}")
    raise TimeoutError(
        f"Elemento '{label}' não encontrado após {timeout}s. Último erro: {last_exc}"
    )

@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(0.5),
    retry=retry_if_exception_type((ElementNotEnabled, ElementNotVisible, Exception)),
    reraise=True,
)
def safe_click(element, label: str = "botão"):
    """Clica com retry automático."""
    logger.info(f"Clicando: {label}")
    element.set_focus()
    element.click_input()

@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(0.3),
    reraise=True,
)
def safe_type(element, text: str, label: str = "campo"):
    """Digita texto com retry automático."""
    logger.info(f"Digitando em [{label}]: {'*' * len(text) if 'senha' in label.lower() else text}")
    element.set_focus()
    element.type_keys(text, with_spaces=True)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(0.2),
    reraise=True,
)
def safe_press_keys(element, keys: str, label: str = "tecla"):
    """Envia teclas especiais no mesmo controle (Enter, Tab, etc.)."""
    logger.info(f"Tecla em [{label}]: {keys}")
    element.set_focus()
    element.type_keys(keys)
    time.sleep(0.15)


def _is_login_window_title(title: str) -> bool:
    t = title or ""
    return "Autentica" in t or "Autenticacao" in t


def _is_main_window_title(title: str) -> bool:
    t = title or ""
    if _is_login_window_title(t):
        return False
    return "FórmulaCerta" in t or "FormulaCerta" in t


def precisa_realizar_login(
    titulos_visiveis: list[str],
    principal_habilitada: bool = False,
) -> bool:
    """
    Regra pura para testes: True se deve autenticar.
    Login visivel sempre exige autenticacao; shell sem principal habilitada tambem.
    """
    if any(_is_login_window_title(t) for t in titulos_visiveis):
        return True
    if principal_habilitada:
        return False
    if any(_is_main_window_title(t) for t in titulos_visiveis):
        return True
    return True


def _janela_habilitada(win) -> bool:
    try:
        return win.is_enabled()
    except Exception:
        return True


def obter_janela_login_visivel(app) -> object | None:
    """Retorna a janela de autenticacao se estiver visivel."""
    try:
        for win in app.windows(visible_only=True):
            title = win.window_text() or ""
            if _is_login_window_title(title):
                logger.info(f"Tela de login detectada: '{title}'")
                return win
    except Exception:
        pass
    return None


def obter_janela_principal_habilitada(app) -> object | None:
    """Retorna a janela principal somente se estiver habilitada (nao bloqueada por login)."""
    if obter_janela_login_visivel(app) is not None:
        return None
    try:
        for win in app.windows(visible_only=True):
            title = win.window_text() or ""
            if _is_main_window_title(title) and _janela_habilitada(win):
                logger.info(f"Janela principal habilitada: '{title}'")
                return win
    except Exception:
        pass
    return None


def aguardar_login_ou_none(app, timeout: float = 15.0) -> object | None:
    """
    Aguarda a tela de login aparecer apos startup.
    Retorna a janela de login ou None se a principal ja estiver habilitada.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        login = obter_janela_login_visivel(app)
        if login is not None:
            return login
        if obter_janela_principal_habilitada(app) is not None:
            return None
        time.sleep(0.5)
    return obter_janela_login_visivel(app)


def wait_main_window(app, timeout: float = 20.0, label: str = "Principal") -> object:
    """Aguarda a janela principal habilitada, ignorando a tela de login."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        main = obter_janela_principal_habilitada(app)
        if main is not None:
            try:
                main.wait("visible", timeout=2)
            except Exception:
                pass
            title = main.window_text() or ""
            logger.info(f"Janela principal visivel: '{title}'")
            return main
        time.sleep(0.5)

    screenshot_on_failure(f"janela_nao_encontrada_{label.replace(' ', '_')}")
    raise TimeoutError(f"Janela principal '{label}' nao apareceu em {timeout}s")


def obter_janela_principal_visivel(app) -> object | None:
    """Retorna a janela principal habilitada (alias de obter_janela_principal_habilitada)."""
    return obter_janela_principal_habilitada(app)


def wait_window(app, title_re: str, timeout: float = 20.0, label: str = "janela") -> object:
    """Aguarda uma janela aparecer pelo regex do título."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            win = app.window(title_re=title_re)
            win.wait("visible", timeout=2)
            logger.info(f"Janela visível: {label} ({title_re})")
            return win
        except Exception:
            time.sleep(0.5)
 
    screenshot_on_failure(f"janela_nao_encontrada_{label.replace(' ', '_')}")
    raise TimeoutError(f"Janela '{label}' não apareceu em {timeout}s")

def wait_app_by_exe(exe_name: str, timeout: float = 20.0) -> Application:
    """
    Aguarda um processo pelo nome do .exe e conecta nele.
    Útil quando a janela abre em um processo separado do principal.
    """
    import psutil
    deadline = time.time() + timeout

    while time.time() < deadline:
        for proc in psutil.process_iter(["name", "pid"]):
            if proc.info["name"] and exe_name.lower() in proc.info["name"].lower():
                try:
                    app = Application(backend="uia").connect(process=proc.info["pid"])
                    logger.info(f"Conectado ao processo: {proc.info['name']} (PID {proc.info['pid']})")
                    return app
                except Exception as e:
                    logger.debug(f"Processo encontrado mas falhou ao conectar: {e}")
        time.sleep(0.5)

    screenshot_on_failure(f"processo_nao_encontrado_{exe_name}")
    raise TimeoutError(f"Processo '{exe_name}' não encontrado em {timeout}s")

def wait_window_exact(app, title: str, timeout: float = 20.0, label: str = "janela") -> object:
    """Aguarda janela por título exato."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            win = app.window(title=title)
            win.wait("visible", timeout=2)
            logger.info(f"Janela visível: {label}")
            return win
        except Exception:
            time.sleep(0.3)
 
    screenshot_on_failure(f"janela_nao_encontrada_{label.replace(' ', '_')}")
    raise TimeoutError(f"Janela '{label}' não apareceu em {timeout}s")
