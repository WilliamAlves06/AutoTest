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
 
def screenshot_on_failure(label: str = "erro") -> Path:
    """Tira screenshot e salva com timestamp."""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SCREENSHOT_DIR / f"{label}_{ts}.png"
    pyautogui.screenshot(str(path))
    logger.warning(f"Screenshot salvo: {path}")
    return path
 
def wait_element(
    window,
    title: str = None,
    class_name: str = None,
    found_index: int = None,
    timeout: float = 15.0,
    label: str = "elemento",
) -> object:
    kwargs = {}
    if title:
        kwargs["title"] = title
    if class_name:
        kwargs["class_name"] = class_name
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
