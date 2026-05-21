# 🤖 AutoTest - Framework de Automação de Testes para Desktop

Um framework robusto e extensível para automação de testes em aplicações desktop Windows desenvolvidas em Delphi/VCL. Combina interação com UI (`pywinauto`), logging estruturado (`loguru`), retry automático (`tenacity`) e validação de dados em banco de dados.

---

## 📋 Índice

1. [O que é este projeto?](#o-que-é-este-projeto)
2. [Arquitetura e Conceitos](#arquitetura-e-conceitos)
3. [Pré-requisitos](#pré-requisitos)
4. [Instalação](#instalação)
5. [Estrutura do Projeto](#estrutura-do-projeto)
6. [Módulos Core - Guia Completo](#módulos-core---guia-completo)
7. [Como Executar Testes Existentes](#como-executar-testes-existentes)
8. [Tutorial: Criando um Novo Teste do Zero](#tutorial-criando-um-novo-teste-do-zero)
9. [Exemplos Práticos](#exemplos-práticos)
10. [Troubleshooting](#troubleshooting)
11. [Boas Práticas](#boas-práticas)

---

## 🎯 O que é este projeto?

**AutoTest** é uma automação de testes para aplicações desktop que:

- **Interage com a UI** — clica botões, digita texto, navega janelas
- **Valida dados** — consulta banco de dados (InterBase/Firebird)
- **Registra tudo** — logs estruturados com timestamps, screenshots em falhas
- **Faz retry automático** — reexecuta ações que falharam por instabilidade
- **Relata resultados** — formata saída de validações em tabelas legíveis

### Exemplo Prático do Fluxo

```
┌─────────────────────────────────────────┐
│  1. Abrir sistema (fcerta.exe)          │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  2. Fazer login (usuário/senha)         │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  3. Navegar menu (teclado)              │
│     Arquivo → Módulo → SubMódulo        │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  4. Preencher formulário                │
│     - Pesquisar dados                   │
│     - Digitar campos                    │
│     - Clicar botões                     │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  5. Validar banco de dados              │
│     - SELECT na tabela                  │
│     - Comparar valores esperados        │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  6. Gerar relatório de resultado        │
│     ✔ PASS / ✘ FAIL                    │
└─────────────────────────────────────────┘
```

---

## 🏗️ Arquitetura e Conceitos

### Três Camadas

| Camada | Responsável | Arquivo |
|--------|-------------|---------|
| **Ações de UI** | Espera elementos, clica, digita | `core/actions.py` |
| **Logging** | Registra eventos em terminal, arquivo, JSON | `core/logging_setup.py` |
| **Relatório** | Formata validações (PASS/FAIL) | `core/reporter.py` |

### Fluxo de Execução

```
Fluxo (CT-192043.py)
  ├─ Configurações (constantes no topo)
  ├─ Etapas de Automação (etapa_conectar_ou_iniciar, etapa_login, etc.)
  │   └─ Usa funções de core/actions.py
  ├─ Validações (consultas ao banco, asserts)
  │   └─ Usa funções de core/reporter.py
  └─ Logging (em todas as etapas)
      └─ Usa core/logging_setup.py
```

---

## ⚙️ Pré-requisitos

- **Sistema Operacional**: Windows 7 ou superior
- **Python**: 3.10 ou superior
- **Aplicação sob teste**: FórmulaCerta (fcerta.exe) com acesso direto
- **Banco de dados**: InterBase/Firebird acessível
- **Permissões**: Acesso à pasta de instalação da aplicação

### Verificar Python

```powershell
python --version
# Saída esperada: Python 3.10.x ou superior
```

---

## 📥 Instalação

### 1. Clone ou baixe o projeto

```powershell
# Opção 1: Git
git clone <URL-do-repositório>
cd "c:\QA\teste automatizados\V1"

# Opção 2: Extrair ZIP manualmente e navegar
cd "c:\QA\teste automatizados\V1"
```

### 2. Crie um ambiente virtual (recomendado)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Instale as dependências

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

**Dependências instaladas:**
- `pywinauto` — automação UI Windows
- `loguru` — logging estruturado
- `tenacity` — retry automático
- `pyautogui` — captura de tela
- `fdb` — conexão com InterBase/Firebird

### 4. Verifique a instalação

```powershell
python -c "import pywinauto, loguru, tenacity, fdb; print('✓ Todas as dependências instaladas')"
```

---

## 📂 Estrutura do Projeto

```
c:\QA\teste automatizados\V1\
│
├── README.md                           # Este arquivo
├── requirements.txt                    # Dependências Python
│
├── core/                               # Módulos reutilizáveis
│   ├── actions.py                      # Funções de automação UI
│   ├── logging_setup.py                # Configuração de logs
│   ├── reporter.py                     # Formatação de relatórios
│   └── conftest.py                     # Fixtures pytest (opcional)
│
├── flows/                              # Casos de teste (testes reais)
│   ├── Notas/
│   │   └── CT-192043.py               # Teste: Validação de Nota Fiscal
│   │
│   ├── Receitas/
│   │   └── CT-168635.py               # Teste: Preenchimento de Receita
│   │
│   └── Produtos/
│       └── Produtos_flow.py           # Teste: Fluxo de Produtos
│
└── logs/                               # Saída de execução (gerado automaticamente)
    ├── screenshots/                    # Screenshots de erro
    ├── CT-192043_2026-05-21.log       # Logs de erro
    └── CT-192043_events.jsonl         # Eventos em JSON
```

---

## 📚 Módulos Core - Guia Completo

### 1. `core/actions.py` — Automação de UI

Este módulo contém funções de baixo nível para interagir com a aplicação.

#### 🔹 `wait_element(window, title, class_name, found_index, timeout, label)`

**O que faz:** Procura um elemento (botão, campo de texto, etc.) dentro de uma janela até que apareça ou timeout.

**Parâmetros:**
- `window`: Objeto da janela (obtido via `wait_window()`)
- `title` (opcional): Título exato do elemento
- `class_name` (opcional): Classe UI do elemento (ex: "TFagronButton")
- `found_index` (opcional): Se houver múltiplos elementos com mesma classe, qual índice
- `timeout`: Segundos para aguardar (padrão 15)
- `label`: Descrição para logs

**Retorna:** Objeto do elemento encontrado

**Exemplo:**

```python
from pywinauto import Application
from core.actions import wait_element, wait_window
from core.logging_setup import setup_logging

setup_logging(log_name="meu_teste")

# Conectar ao aplicativo
app = Application(backend="uia").start(r"C:\Fcerta\fcerta.exe")

# Aguardar uma janela
janela = wait_window(app, "Principal", timeout=10, label="Janela Principal")

# Procurar um botão por classe
botao_salvar = wait_element(
    janela,
    class_name="TFagronButton",
    title="Salvar",
    timeout=5,
    label="Botão Salvar"
)

# Procurar o 2º elemento da classe TwwDBEdit
campo_email = wait_element(
    janela,
    class_name="TwwDBEdit",
    found_index=2,
    timeout=5,
    label="Campo Email"
)
```

**O que acontece internamente:**
1. Loop com timeout
2. A cada 0.3s tenta encontrar o elemento
3. Se encontrar, espera 2s para ficar visível e habilitado
4. Se não encontrar, faz screenshot e lança `TimeoutError`

---

#### 🔹 `safe_click(element, label)`

**O que faz:** Clica em um elemento com retry automático (tenta até 3 vezes se falhar).

**Parâmetros:**
- `element`: Objeto do elemento
- `label`: Descrição para logs

**Exemplo:**

```python
from core.actions import safe_click

# Clicar em um botão
safe_click(botao_salvar, label="Botão Salvar")

# Internamente:
# 1. Foca o elemento
# 2. Clica
# 3. Se falhar, aguarda 0.5s e tenta novamente (máx 3 vezes)
```

**Saída do log:**
```
13:45:23 | INFO     | safe_click:63 — Clicando: Botão Salvar
```

---

#### 🔹 `safe_type(element, text, label)`

**O que faz:** Digita texto em um campo com retry automático.

**Parâmetros:**
- `element`: Objeto do campo
- `text`: Texto a digitar
- `label`: Descrição para logs

**Comportamento especial:**
- Se a label contiver "senha", o texto é mascarado com `*` no log
- Aguarda o campo ganhar foco antes de digitar

**Exemplo:**

```python
from core.actions import safe_type, wait_element

# Digitar em um campo de texto
campo_usuario = wait_element(janela, title="Usuário")
safe_type(campo_usuario, "FAGRONTECH", label="Campo Usuário")

# Digitar senha (será mostrada como ***)
campo_senha = wait_element(janela, title="Senha")
safe_type(campo_senha, "321", label="Campo Senha")
```

**Saída do log:**
```
13:45:24 | INFO     | safe_type:74 — Digitando em [Campo Usuário]: FAGRONTECH
13:45:24 | INFO     | safe_type:74 — Digitando em [Campo Senha]: ***
```

---

#### 🔹 `wait_window(app, title_re, timeout, label)`

**O que faz:** Aguarda uma janela aparecer pelo título (suporta regex).

**Parâmetros:**
- `app`: Objeto da aplicação
- `title_re`: Regex do título (ex: `".*Principal.*"`)
- `timeout`: Segundos para aguardar
- `label`: Descrição para logs

**Exemplo:**

```python
from core.actions import wait_window

# Aguardar janela com regex
janela_principal = wait_window(
    app,
    r".*FórmulaCerta.*",
    timeout=20,
    label="Janela Principal"
)

# Aguardar diálogo de confirmação
dialogo = wait_window(
    app,
    "Confirmação",
    timeout=10,
    label="Diálogo de Confirmação"
)
```

---

#### 🔹 `wait_window_exact(app, title, timeout, label)`

**O que faz:** Aguarda uma janela pelo título **exato** (sem regex).

**Exemplo:**

```python
from core.actions import wait_window_exact

# Aguardar janela de login (título exato)
login = wait_window_exact(
    app,
    "FórmulaCerta Autenticação de Usuário",
    timeout=25,
    label="Janela de Login"
)
```

---

#### 🔹 `wait_app_by_exe(exe_name, timeout)`

**O que faz:** Procura um processo Windows pelo nome do .exe e conecta nele (útil para módulos que abrem em processo separado).

**Parâmetros:**
- `exe_name`: Nome do executável (ex: "FCNotas.exe")
- `timeout`: Segundos para aguardar

**Retorna:** Objeto `Application` conectado ao processo

**Exemplo:**

```python
from core.actions import wait_app_by_exe

# Abrir menu Notas (abre FCNotas.exe separado)
main.type_keys("%a")  # Alt+A para menu
time.sleep(0.5)
main.type_keys("{RIGHT}{DOWN}{DOWN}{ENTER}")

# Aguardar o processo FCNotas abrir
app_notas = wait_app_by_exe("FCNotas.exe", timeout=20)

# Agora usar app_notas como referência para as ações
notas_window = app_notas.top_window()
notas_window.set_focus()
```

---

#### 🔹 `screenshot_on_failure(label)`

**O que faz:** Captura uma screenshot da tela (útil para debug quando falha).

**Parâmetros:**
- `label`: Descrição para o nome do arquivo

**Retorna:** Path do arquivo salvo

**Exemplo:**

```python
from core.actions import screenshot_on_failure

try:
    elemento = wait_element(janela, title="Salvar")
except TimeoutError:
    # Captura screenshot manualmente
    screenshot_on_failure("botao_salvar_nao_encontrado")
    raise
```

**Saída:**
```
logs/screenshots/botao_salvar_nao_encontrado_20260521_134523.png
```

---

### 2. `core/logging_setup.py` — Logging Estruturado

Este módulo configura logs em três destinos: **terminal**, **arquivo**, **JSON**.

#### 🔹 `setup_logging(log_name, json_output)`

**Parâmetros:**
- `log_name`: Prefixo do arquivo (ex: "Notas_flow")
- `json_output`: True para gerar arquivo JSON também

**Exemplo:**

```python
from core.logging_setup import setup_logging
from loguru import logger

# Configurar logs
setup_logging(log_name="meu_teste", json_output=True)

# Usar logger
logger.debug("Mensagem de debug")
logger.info("Mensagem informativa")
logger.success("✓ Sucesso")
logger.warning("⚠ Aviso")
logger.error("✘ Erro")
```

**Saída no terminal:**
```
13:45:23 | DEBUG    | minha_funcao:42 — Mensagem de debug
13:45:23 | INFO     | minha_funcao:43 — Mensagem informativa
13:45:23 | SUCCESS  | minha_funcao:44 — ✓ Sucesso
13:45:23 | WARNING  | minha_funcao:45 — ⚠ Aviso
13:45:23 | ERROR    | minha_funcao:46 — ✘ Erro
```

**Arquivos gerados:**
- `logs/meu_teste_2026-05-21.log` — Apenas erros
- `logs/meu_teste_events.jsonl` — Eventos em JSON

---

### 3. `core/reporter.py` — Relatório de Validações

Este módulo formata resultados de testes em tabelas legíveis.

#### 🔹 `imprimir_inicio(nome_ct, descricao)`

**O que faz:** Imprime cabeçalho do teste.

**Exemplo:**

```python
from core.reporter import imprimir_inicio

imprimir_inicio("CT-192043", "Validação de Nota Fiscal - FC11100")
```

**Saída:**
```
═══════════════════════════════════════════════════════════════
  CT: CT-192043
  Validação de Nota Fiscal - FC11100
═══════════════════════════════════════════════════════════════
```

---

#### 🔹 `imprimir_etapa(mensagem)`

**O que faz:** Imprime uma etapa do teste.

**Exemplo:**

```python
from core.reporter import imprimir_etapa

imprimir_etapa(f"Verificando se nota 8484 existe na FC11100...")
```

**Saída:**
```
→ Verificando se nota 8484 existe na FC11100...
```

---

#### 🔹 `imprimir_resultado(resultados)`

**O que faz:** Imprime tabela de validações com status PASS/FAIL.

**Parâmetros:**
- `resultados`: Lista de dicts com keys: `campo`, `esperado`, `obtido`, `status`

**Exemplo:**

```python
from core.reporter import imprimir_resultado

# Após consultar banco de dados
cursor.execute("SELECT CDPRO FROM FC11100 WHERE NRNOT = ?", (8484,))
row = cursor.fetchone()
cdpro_obtido = row[0] if row else "NULL"

# Validar
imprimir_resultado([
    {
        "campo": "CDPRO",
        "esperado": "51639",
        "obtido": str(cdpro_obtido),
        "status": "PASS" if str(cdpro_obtido) == "51639" else "FAIL"
    },
    {
        "campo": "NRLOT",
        "esperado": "123",
        "obtido": "123",
        "status": "PASS"
    }
])
```

**Saída:**
```
───────────────────────────────────────────────────────────────
  CAMPO                ESPERADO        OBTIDO          STATUS
───────────────────────────────────────────────────────────────
  CDPRO                51639           51639           ✔ PASS
  NRLOT                123             123             ✔ PASS
───────────────────────────────────────────────────────────────
  RESULTADO: 2/2 validações passaram
═══════════════════════════════════════════════════════════════
```

---

## 🚀 Como Executar Testes Existentes

### Opção 1: Executar diretamente

```powershell
# Teste de Notas
python flows\Notas\CT-192043.py

# Teste de Receitas
python flows\Receitas\CT-168635.py

# Teste de Produtos
python flows\Produtos\Produtos_flow.py
```

### Opção 2: Executar com pytest

```powershell
# Um arquivo específico
pytest flows\Notas\CT-192043.py -v

# Todos os testes
pytest flows\ -v

# Com output reduzido
pytest flows\ -q
```

### Verificar os logs

```powershell
# Ver log de erro
cat logs\CT-192043_2026-05-21.log

# Ver eventos JSON
cat logs\CT-192043_events.jsonl
```

---

## 📖 Tutorial: Criando um Novo Teste do Zero

Vamos criar um teste chamado `CT-200000.py` para validar uma funcionalidade fictícia.

### Passo 1: Criar a estrutura do arquivo

```powershell
# Criar pasta se necessário
New-Item -ItemType Directory -Path "flows\MeuModulo" -Force

# Criar arquivo
New-Item -ItemType File -Path "flows\MeuModulo\CT-200000.py"
```

### Passo 2: Copiar template e configurar constantes

```python
# ========== CT-200000.py ==========
import sys
import time
from pathlib import Path
from pywinauto import Application
from loguru import logger
import fdb

# Adicionar pasta raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.logging_setup import setup_logging
from core.actions import (
    wait_element,
    wait_window,
    wait_app_by_exe,
    wait_window_exact,
    safe_click,
    safe_type,
    screenshot_on_failure,
)
from core.reporter import imprimir_inicio, imprimir_etapa, imprimir_resultado

# ─────────────────────────────────────────
# CONFIGURAÇÃO — SISTEMA
# ─────────────────────────────────────────
EXE_PATH  = r"C:\Fcerta\fcerta.exe"
WIN_LOGIN = "FórmulaCerta Autenticação de Usuário"
USUARIO   = "FAGRONTECH"
SENHA     = "321"

# ─────────────────────────────────────────
# CONFIGURAÇÃO — TESTE
# ─────────────────────────────────────────
CAMPO_ESPERADO = "valor_teste"

# ─────────────────────────────────────────
# CONFIGURAÇÃO — BANCO
# ─────────────────────────────────────────
DB_CONFIG = {
    "host":     "localhost",
    "database": r"C:\bancoDeDados\formulaInjetaveis\alterdb.ib",
    "user":     "SYSDBA",
    "password": "masterkey",
}
```

### Passo 3: Criar funções de etapa

```python
# ─────────────────────────────────────────
# FLUXO
# ─────────────────────────────────────────

def etapa_conectar_ou_iniciar() -> Application:
    """Conecta ao processo em execução ou inicia um novo."""
    try:
        app = Application(backend="uia").connect(path=EXE_PATH, timeout=3)
        logger.info("Conectado ao sistema já aberto.")
        return app
    except Exception:
        logger.info("Sistema não estava aberto — iniciando...")
        return Application(backend="uia").start(EXE_PATH)

def etapa_login(app: Application):
    """Aguarda tela de login, preenche usuário e senha."""
    logger.info("Aguardando tela de login...")
    login = wait_window_exact(app, WIN_LOGIN, timeout=25, label="Login")
    login.set_focus()
    safe_type(login, USUARIO, label="usuário")
    login.type_keys("{ENTER}")
    safe_type(login, SENHA, label="senha")
    login.type_keys("{ENTER}{ENTER}")
    logger.success("Login enviado.")

def etapa_abrir_menu_meuperfil(main) -> None:
    """Abre menu Arquivo → Meu Módulo via atalho de teclado."""
    logger.info("Abrindo menu Arquivo (ALT+A)...")
    main.set_focus()
    time.sleep(0.3)
    main.type_keys("%a")  # ALT+A
    time.sleep(0.4)
    main.type_keys("{RIGHT}{ENTER}")  # Navegar
    logger.info("Módulo aberto.")

def etapa_preencher_formulario():
    """Interage com o formulário do módulo."""
    logger.info("Iniciando preenchimento do formulário...")
    
    # Aguardar a janela do módulo
    app_modulo = wait_app_by_exe("FCMeuModulo.exe", timeout=20)
    janela = app_modulo.top_window()
    janela.set_focus()
    
    # Procurar campo de texto
    campo = wait_element(
        janela,
        class_name="TwwDBEdit",
        found_index=0,
        timeout=5,
        label="Campo Principal"
    )
    
    # Digitar valor
    safe_type(campo, CAMPO_ESPERADO, label="Campo Principal")
    
    # Clicar botão Salvar
    botao_salvar = wait_element(
        janela,
        title="Salvar",
        class_name="TFagronButton",
        timeout=5,
        label="Botão Salvar"
    )
    safe_click(botao_salvar, label="Salvar")
    
    logger.success("Formulário preenchido com sucesso.")
```

### Passo 4: Criar validações

```python
# ─────────────────────────────────────────
# VALIDAÇÕES
# ─────────────────────────────────────────

def validar_no_banco():
    """Consulta banco de dados para validar dados salvos."""
    imprimir_inicio("CT-200000", "Validação de Dados - Meu Módulo")
    
    conn = fdb.connect(
        host=DB_CONFIG["host"],
        database=DB_CONFIG["database"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
    )
    cursor = conn.cursor()
    
    try:
        imprimir_etapa(f"Verificando se valor '{CAMPO_ESPERADO}' foi salvo...")
        
        cursor.execute("SELECT COUNT(*) FROM MINHA_TABELA WHERE CAMPO = ?", (CAMPO_ESPERADO,))
        count = cursor.fetchone()[0]
        
        # Primeiro resultado
        imprimir_resultado([{
            "campo": "REGISTRO EXISTE",
            "esperado": "> 0",
            "obtido": str(count),
            "status": "PASS" if count > 0 else "FAIL"
        }])
        
        assert count > 0, f"Registro com valor '{CAMPO_ESPERADO}' não encontrado"
        
        # Se tudo ok, sucesso
        logger.success("✓ Validação concluída com sucesso")
        return True
        
    except Exception as e:
        logger.error(f"✘ Validação falhou: {e}")
        return False
    finally:
        cursor.close()
        conn.close()
```

### Passo 5: Criar função main

```python
# ─────────────────────────────────────────
# EXECUÇÃO PRINCIPAL
# ─────────────────────────────────────────

def run():
    """Executa o fluxo completo."""
    setup_logging(log_name="CT-200000_flow", json_output=True)
    
    logger.info("=" * 60)
    logger.info("🚀 INÍCIO DO FLUXO: CT-200000")
    logger.info("=" * 60)
    
    try:
        # Conectar
        logger.info("📍 [1/4] Conectando ao sistema...")
        app = etapa_conectar_ou_iniciar()
        logger.success("✓ Conectado")
        
        # Login
        try:
            main = wait_window(app, r".*FórmulaCerta.*", timeout=5, label="Principal")
            logger.info("Sistema já autenticado")
        except TimeoutError:
            logger.info("Realizando login...")
            etapa_login(app)
            main = wait_window(app, r".*FórmulaCerta.*", timeout=20, label="Principal")
            logger.success("✓ Login realizado")
        
        # Abrir módulo
        logger.info("📍 [2/4] Abrindo módulo...")
        etapa_abrir_menu_meuperfil(main)
        logger.success("✓ Módulo aberto")
        
        # Preencher formulário
        logger.info("📍 [3/4] Preenchendo formulário...")
        etapa_preencher_formulario()
        logger.success("✓ Formulário preenchido")
        
        # Validar
        logger.info("📍 [4/4] Validando no banco...")
        resultado = validar_no_banco()
        
        logger.info("=" * 60)
        if resultado:
            logger.success("🎉 FLUXO FINALIZADO COM SUCESSO")
        else:
            logger.error("❌ FLUXO FALHOU NA VALIDAÇÃO")
        logger.info("=" * 60)
        
        return 0 if resultado else 1
    
    except Exception as e:
        import traceback
        logger.info("=" * 60)
        logger.error(f"❌ FALHA CRÍTICA: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        logger.info("=" * 60)
        screenshot_on_failure("falha_geral_CT200000")
        return 1

if __name__ == "__main__":
    sys.exit(run())
```

### Passo 6: Executar

```powershell
python flows\MeuModulo\CT-200000.py
```

---

## 💡 Exemplos Práticos

### Exemplo 1: Clicar e aguardar confirmação

```python
from core.actions import safe_click, wait_window

# Clicar em "Deletar"
safe_click(botao_deletar, label="Botão Deletar")

# Aguardar diálogo de confirmação
confirmacao = wait_window(app, "Confirmação", timeout=10, label="Confirmação")

# Clicar "Sim"
botao_sim = wait_element(confirmacao, title="Sim")
safe_click(botao_sim, label="Botão Sim")
```

### Exemplo 2: Pesquisar em grid

```python
from core.actions import wait_element, safe_type, safe_click
import time

# Preencher campo de pesquisa
campo_busca = wait_element(janela, title="Pesquisar", timeout=5)
safe_type(campo_busca, "8484", label="Campo Pesquisa")

# Clicar botão Pesquisar
botao_pesquisar = wait_element(janela, title="Pesquisar", class_name="TFagronButton")
safe_click(botao_pesquisar, label="Pesquisar")
time.sleep(0.5)

# Encontrar grid
grid = wait_element(janela, class_name="TwwDBGrid", timeout=5)

# Duplo clique para abrir primeiro item
grid.set_focus()
grid.double_click_input()
```

### Exemplo 3: Navegação por teclado

```python
# ALT+A para menu
janela.type_keys("%a")
time.sleep(0.3)

# Seta direita + down + enter
janela.type_keys("{RIGHT}{DOWN}{ENTER}")
time.sleep(0.3)

# Tab para próximo campo
janela.type_keys("{TAB 2}")  # 2x TAB

# Enter para confirmar
janela.type_keys("{ENTER}")
```

### Exemplo 4: Validação com banco de dados

```python
import fdb
from core.reporter import imprimir_resultado

conn = fdb.connect(
    host="localhost",
    database=r"C:\bancoDeDados\formulaInjetaveis\alterdb.ib",
    user="SYSDBA",
    password="masterkey",
)
cursor = conn.cursor()

# Executar query
cursor.execute("SELECT CDPRO, NRLOT FROM FC11100 WHERE NRNOT = ?", ("8484",))
row = cursor.fetchone()

cdpro = row[0] if row else "NULL"
nrlot = row[1] if row else "NULL"

# Formatar resultado
imprimir_resultado([
    {
        "campo": "CDPRO",
        "esperado": "51639",
        "obtido": str(cdpro),
        "status": "PASS" if str(cdpro) == "51639" else "FAIL"
    },
    {
        "campo": "NRLOT",
        "esperado": "123",
        "obtido": str(nrlot),
        "status": "PASS" if str(nrlot) == "123" else "FAIL"
    }
])

cursor.close()
conn.close()
```

---

## 🆘 Troubleshooting

### Problema: `TimeoutError: Elemento 'X' não encontrado`

**Causa:** Elemento não apareceu dentro do timeout.

**Solução:**
1. Aumentar timeout: `timeout=30` em vez de `timeout=15`
2. Verificar class_name: Inspecionar a aplicação com ferramentas como Inspect.exe
3. Verificar se a janela pai está correta

```python
# ❌ Errado
elemento = wait_element(app.top_window(), class_name="TwwDBEdit", timeout=5)

# ✓ Correto
janela_certa = wait_window(app, "Título da Janela", timeout=10)
elemento = wait_element(janela_certa, class_name="TwwDBEdit", timeout=5)
```

---

### Problema: `AttributeError: 'generator' object has no attribute 'execute'`

**Causa:** `db_cursor()` é uma função geradora (usa `yield`), não retorna cursor direto.

**Solução:**

```python
# ❌ Errado
cursor = db_cursor()  # Retorna um gerador
cursor.execute("SELECT ...")  # Erro!

# ✓ Correto (opção 1: usar com fixture pytest)
@pytest.fixture
def cursor_connection(db_cursor):
    return next(db_cursor())

def test_algo(cursor_connection):
    cursor_connection.execute("SELECT ...")

# ✓ Correto (opção 2: usar fdb direto)
conn = fdb.connect(
    host=DB_CONFIG["host"],
    database=DB_CONFIG["database"],
    user=DB_CONFIG["user"],
    password=DB_CONFIG["password"],
)
cursor = conn.cursor()
cursor.execute("SELECT ...")
cursor.close()
conn.close()
```

---

### Problema: Aplicação não responde / UI travada

**Causa:** Timing inadequado.

**Solução:**

```python
# Adicionar delays estratégicos
time.sleep(0.5)  # Aguardar renderização

# Usar retry com delay maior
from tenacity import retry, wait_fixed, stop_after_attempt

@retry(
    stop=stop_after_attempt(5),
    wait=wait_fixed(1),  # Aumentar espera
    reraise=True
)
def minha_acao():
    elemento = wait_element(janela, ...)
    elemento.click_input()
```

---

### Problema: Screenshot não está sendo gerado

**Causa:** Pasta não existe.

**Solução:**

```python
from pathlib import Path

# Garantir pasta existe
SCREENSHOT_DIR = Path("logs/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
```

---

### Problema: Logs não aparecem

**Causa:** `setup_logging()` não foi chamado.

**Solução:**

```python
# Sempre chamar no início
from core.logging_setup import setup_logging

setup_logging(log_name="meu_teste", json_output=True)

# Agora usar logger
from loguru import logger
logger.info("Teste iniciado")
```

---

## ✅ Boas Práticas

### 1. Sempre usar labels descritivos

```python
# ❌ Ruim
wait_element(janela, class_name="TFagronButton")

# ✓ Bom
wait_element(
    janela,
    class_name="TFagronButton",
    title="Salvar",
    timeout=5,
    label="Botão Salvar Principal"
)
```

### 2. Estruturar em etapas

```python
# ✓ Bom
def run():
    logger.info("📍 [1/5] Conectando...")
    app = etapa_conectar()
    
    logger.info("📍 [2/5] Fazendo login...")
    etapa_login(app)
    
    logger.info("📍 [3/5] Navegando...")
    etapa_navegar(app)
```

### 3. Usar try/except em áreas críticas

```python
try:
    dialogo = wait_window(app, "Confirmação", timeout=5)
    dialogo.type_keys("{ENTER}")
except TimeoutError:
    logger.warning("Diálogo não apareceu, continuando...")
    # Continuar fluxo
```

### 4. Validar antes de usar

```python
row = cursor.fetchone()
valor = row[0] if row else "NULL"  # Evitar None errors

assert valor != "NULL", "Registro não encontrado"
```

### 5. Documentar variáveis globais

```python
# ─────────────────────────────────────────
# CONFIGURAÇÃO — SISTEMA
# ─────────────────────────────────────────
# Caminho do executável da aplicação
EXE_PATH = r"C:\Fcerta\fcerta.exe"

# Título exato da janela de login
WIN_LOGIN = "FórmulaCerta Autenticação de Usuário"

# Credenciais de acesso (ATENÇÃO: considerar usar variáveis de ambiente)
USUARIO = "FAGRONTECH"
SENHA = "321"
```

### 6. Usar screenshots estratégicos

```python
# Não fazer screenshot a toda hora (lentifica)
# Apenas em:
# - Falhas detectadas
# - Validações críticas
# - Pontos de decisão

try:
    elemento = wait_element(...)
except TimeoutError:
    screenshot_on_failure("timeout_elemento_critico")
    raise
```

---

## 📝 Resumo

| Situação | Função |
|----------|--------|
| Aguardar elemento aparecer | `wait_element()` |
| Clicar em elemento | `safe_click()` |
| Digitar em campo | `safe_type()` |
| Aguardar janela | `wait_window()` ou `wait_window_exact()` |
| Procurar por .exe | `wait_app_by_exe()` |
| Capturar erro visual | `screenshot_on_failure()` |
| Configurar logs | `setup_logging()` |
| Imprimir resultado | `imprimir_resultado()` |

---

## 🤝 Contribuindo

Para adicionar novos testes:

1. Crie uma pasta em `flows/<modulo>/`
2. Siga o padrão de `CT-192043.py`
3. Use as funções de `core/`
4. Documente o teste

---

## 📞 Suporte

- Verifique a pasta `logs/` para erros detalhados
- Screenshots automáticas aparecem em `logs/screenshots/`
- Eventos JSON em `logs/*_events.jsonl`

---

**Última atualização:** Maio 2026
