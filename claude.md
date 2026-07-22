# CLAUDE.md — Guia do projeto AutoTest (FC Automation)

> Este arquivo existe pra você (Claude Code) entender o projeto **antes** de tocar em
> qualquer arquivo. Leia inteiro antes da primeira alteração. Regra de ouro: **reaproveite
> o que já existe — não crie arquitetura nova pra resolver problema que já tem solução no
> repo.**

## O que é o projeto

Framework de automação de testes **desktop** para o sistema legado **Formula Certa**
(Delphi/VCL), rodando em Windows. É um "Cypress Desktop": o QA escreve testes com uma
DSL legível (`fc.login()`, `fc.field("alias").type(...)`, `fc.button("alias").click()`)
e todo fluxo que altera dado só é aprovado se o **banco** (Firebird/InterBase) confirmar
— a mensagem visual de sucesso na tela nunca é suficiente.

Tem também um app web local (`python run_web.py`, FastAPI + SPA estática) — o "QA
Studio" — com abas para mapear telas, gravar testes (recorder), cadastrar abertura de
módulos e rodar os testes.

## Princípios inegociáveis (não violar)

1. **Sem coordenadas de mouse, sem TAB pra navegar, sem sequência de teclado pra
   localizar campo.** Localização é via UI Automation (UIA): `automation_id`,
   `class_name`, `found_index`, `instance`, hierarquia de janela/aba.
2. **`{ENTER}` só é usado como *commit* de valor** (disparar lookup do Delphi), nunca
   para navegar entre campos.
3. **Validação obrigatória no banco.** Todo teste que inclui/edita dado termina com
   `fc.db.assert_saved(...)` ou `fc.db.query(...)` + comparação manual. Teste que só
   confia na tela não está completo.
4. **Aliases, não localizadores crus no teste.** O teste nunca deve conter
   `found_index`/`class_name`/coordenada — isso vive só nos JSONs de `mappings/`.
5. **Attach-first.** `fc.open_module(...)` sempre tenta anexar ao processo já aberto
   antes de navegar pelo menu.

## Estrutura do projeto (não reorganizar sem pedir)

```
run_web.py            # entrypoint do app web (FastAPI/uvicorn) → :8765
autotest.py            # `from autotest import *` — atalho usado pelos flows
config.json             # caminhos (exe_path, pasta base) — SEM segredos, versionado
.env                    # credenciais FC_LOGIN/FC_SENHA — NUNCA versionado
modulos.json             # como cada módulo abre (exe + passos de menu)

webapp/                # app web: server.py, routes_*.py, mapear_engine.py, static/
data/                   # massa de dados dos testes (filiais.py, receitas.py, ...)
fc/                     # a DSL
  __init__.py           #   expõe o singleton `fc` (classe FC)
  context.py            #   FCContext: janela principal, módulo ativo, alias-map
  elements.py            #   Field / Button / Window (.type/.click/.should_*)
  locator_engine.py       #   alias -> elemento vivo (ordem de estratégias)
  mapping_store.py         #   lê/grava alias-maps
  modules.py               #   lê/grava modulos.json
  db_facade.py              #   fc.db
database/               # validação em banco (Firebird)
  connection.py, firebird_client.py, validators.py, assertions.py, queries/*.sql
mappings/               # alias-maps por janela: mappings/<Módulo>/<Janela>.json
core/                   # base de UI/log reaproveitada pela DSL
  actions.py             #   wait_element/wait_window/wait_app_by_exe/safe_*,
                          #   screenshot_on_failure() [já existe, ver seção evidências]
  login_flow.py, logging_setup.py, reporter.py, config.py
tools/                  # scripts utilitários (ex.: mapear_janela.py, _screenshot_studio.py)
flows/                  # os testes de verdade, organizados por módulo
  Filiais/consulta_filial.py, Receitas/CT-168635.py, ...
logs/                   # logs + screenshots de falha (gerado, não versionado)
output/                 # JSON de mapeamentos (gerado)
conftest.py              # fixtures pytest (fc, fc_login, fc_modulo, db, cursor) +
                          # hook pytest_runtest_makereport (screenshot em falha)
.github/workflows/ci.yml # CI: lint (ruff) + smoke import + testes unit no Windows
```

## Convenções de código (seguir exatamente o estilo existente)

- **Comentários, docstrings e mensagens de log em português.** Nomes de função também
  costumam ser em português (`etapa_abrir_modulo`, `etapa_validar`, `_checar_dialogo_erro`).
- **Logging com `loguru`** (`from loguru import logger`), nunca `print()` cru no meio da
  lógica de produção — `logger.info/success/warning/error`.
- **Imports lazy dentro de fixtures/funções** quando a lib depende de Windows
  (`pywinauto`, `fdb`, `win32*`) — assim a coleta de teste roda também em runner Linux
  (CI hoje só roda lint + unit no Windows; ver `conftest.py` e `ci.yml`).
- **Toda API pública da DSL retorna `self` (ou o elemento)** pra permitir encadeamento:
  `fc.field("produto").type("123").should_have_value("123")`.
- **Nunca falhar o teste por um problema da própria instrumentação** (ex.: se um
  screenshot falhar, loga warning e segue — não lança exceção que mascare o motivo
  real da falha do teste). Ver `screenshot_on_failure` em `core/actions.py` como
  referência desse padrão (fallback pyautogui → win32, nunca propaga erro).
- **Sem segredo em código.** Login/senha só via `core/config.py` (`carregar_config()`),
  nunca hardcoded num flow.
- **`fc.reset()` sempre no `finally`** de um teste — encerra sessão/conexão de banco.

## Evidências já existentes (não duplicar, estender)

Hoje o projeto já tira screenshot **automaticamente em caso de falha**:

- `core/actions.py::screenshot_on_failure(label)` — salva em `logs/screenshots/`
  como `{label}_{timestamp}.png`; tenta `pyautogui`, cai pro fallback Win32
  (`_screenshot_win32`) se faltar Pillow; nunca lança exceção, só loga warning.
- `conftest.py::pytest_runtest_makereport` — no hook de falha do pytest, chama
  `screenshot_on_failure` e anexa o PNG ao relatório `pytest-html` via `extras`.
- `tools/_screenshot_studio.py` — script à parte, só pra capturar telas do **QA
  Studio** (a ferramenta em si) para documentação; não é evidência de teste.

Qualquer feature nova de evidência (ex.: `fc.print()`) deve **reaproveitar** a lógica
de captura já existente (extrair o fallback Win32 para uma função compartilhada, não
copiar/colar), e não deve remover ou quebrar o comportamento de screenshot em falha
que já está em produção.

## Coisas que o Claude Code NÃO deve fazer sem perguntar antes

- Trocar a estrutura de pastas do projeto (`fc/`, `core/`, `database/`, `flows/`, etc.).
- Trocar o driver de banco (`fdb`) ou a lib de UI Automation (`pywinauto`).
- Editar `mappings/**/*.json` "para simplificar" — são gerados pela aba **Mapear**,
  não devem ser reescritos à mão pelo agente.
- Adicionar dependências novas ao `requirements.txt` sem necessidade clara (o projeto
  já lista as libs principais no README — pywinauto, pynput, loguru, tenacity,
  pyautogui/pywin32, psutil, fdb, pytest, python-dotenv, pytest-html, ruff).
- Criar um segundo mecanismo de configuração paralelo a `core/config.py`.
- Reescrever `conftest.py` do zero — só **estender** as fixtures/hooks existentes.
- Mudar a regra de aprovação do teste (tela + banco batendo é obrigatório; nunca
  aprovar só porque a tela mostrou "salvo").

## Como rodar / validar uma mudança

```powershell
python -m pytest flows\Filiais\consulta_filial.py -v   # teste específico
python -m pytest tests -m unit                          # só unit (roda em CI/Linux-friendly)
ruff check fc database data ui tests conftest.py core/config.py core/recorder/fc_codegen.py core/recorder/alias_resolver.py
python run_web.py                                        # sobe o QA Studio em :8765
```

CI (`.github/workflows/ci.yml`) roda em **Windows** (por causa de `pywin32`/
`pywinauto`): lint (ruff) → smoke de import → testes unitários (`-m unit`, sem abrir
o Formula Certa). Fluxos E2E (`-m e2e`) exigem runner self-hosted Windows com o app +
banco — não rodam na nuvem.

## Referência rápida da DSL (`fc.`)

```python
from fc import fc

fc.login()
fc.open_module("FCFiliais")
fc.tab("Estoques")                                 # aba da tela atual

fc.field("alias").type("texto").press("{ENTER}")
fc.field("alias").clear().get_value()
fc.field("alias").should_have_value("10")
fc.field("alias").should_exist() / .should_be_visible()

fc.button("alias").click() / .double_click()

fc.window("Título").ok() / .close() / .press("{ENTER}") / .should_exist()

fc.db.query("nome_sql", {"param": "v"})            # 1 registro (dict) ou None
fc.db.client.query_all("nome_sql", {"param": "v"}) # todas as linhas
fc.db.assert_saved(query=..., params=..., expected={...})  # aprova/reprova sozinho

fc.reset()   # sempre no finally
```

Aliases vêm de `mappings/<Módulo>/<Janela>.json`, criados pela aba **Mapear** do app
web — nunca invente um alias que não existe no mapping.

---

**Quando for implementar algo neste projeto:** confira se já existe um módulo/função
fazendo algo parecido (ex.: captura de tela já existe em `core/actions.py`), reaproveite
o padrão de logging/erro/estrutura de pastas, escreva em português seguindo o estilo
do resto do código, e pare para perguntar antes de qualquer mudança estrutural que não
esteja explicitamente pedida.