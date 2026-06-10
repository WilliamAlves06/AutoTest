# 🤖 FC Automation — automação para o Formula Certa (Delphi)

[![CI](https://github.com/WilliamAlves06/AutoTest/actions/workflows/ci.yml/badge.svg)](https://github.com/WilliamAlves06/AutoTest/actions/workflows/ci.yml)

Framework de automação de testes **desktop** para o sistema legado **Formula Certa**
(Delphi/VCL). O QA escreve testes em comandos simples e legíveis — **sem TAB, sem
coordenadas de mouse, sem conhecer os detalhes do Delphi** — e a aprovação é
**obrigatoriamente validada no banco de dados** (a mensagem visual de sucesso não basta).

```python
fc.login()
fc.open_module("FCFiliais")
fc.field("Consulta_Campo").type("10").press("{ENTER}")
fc.db.query("filial_consulta", {"codigo": "10"})   # confere no banco
```

---

## 📋 Índice

1. [Para iniciantes — como começar a escrever um teste](#-para-iniciantes--como-começar-a-escrever-um-teste)
2. [Princípios do framework](#-princípios-do-framework)
3. [Instalação e pré-requisitos](#-instalação-e-pré-requisitos)
4. [As abas do app](#-as-abas-do-app)
5. [Estrutura do projeto](#-estrutura-do-projeto)
6. [Arquitetura técnica](#-arquitetura-técnica)
7. [Referência da DSL (`fc.`)](#-referência-da-dsl-fc)
8. [Validação em banco (`database/`)](#-validação-em-banco-database)
9. [Anatomia de um teste](#-anatomia-de-um-teste)
10. [Como rodar](#-como-rodar)
11. [Troubleshooting](#-troubleshooting)
12. [Boas práticas](#-boas-práticas)

---

## 🟢 Para iniciantes — como começar a escrever um teste

> Esta seção é para quem **nunca** mexeu no projeto. A ideia central:
> você escreve o teste com comandos parecidos com instruções humanas
> (“faça login”, “abra o módulo”, “digite no campo X”, “confira no banco”).

### Parte 1 — Preparar a tela (você faz **uma vez** por tela)

Antes de escrever um teste para uma tela, ela precisa estar “ensinada” ao sistema.
Tudo pela interface do app (`python app.py`):

| Passo | Aba | O que fazer |
|------|-----|-------------|
| **1. Configurar** | **Configuracoes** | Caminho do `fcerta.exe`, **login/senha** e a pasta dos testes. Uma vez só. |
| **2. Mapear + nomear** | **Mapear** | Abra a tela no Formula Certa → **Mapear agora** (fotografa os campos) → **Editar aliases** (dê **nomes fáceis** aos campos, ex.: `Razao_Social`, `consultar`) → **Salvar**. |
| **3. Ensinar a abrir** | **Modulos** | Cadastre como o módulo abre a partir da tela principal — use **🎬 Gravar teclas/cliques** e **clique** no item do menu (grava o índice, livre de resolução). |

Na aba **Mapear → Editar aliases** você ainda tem:
- **👁** — pisca o campo real na tela para você saber qual é (lê a posição **ao vivo**);
- **🎯 Capturar manual** — clica no campo na tela para pegar os que o automático não pegou;
- **🔄 Re-mapear (mesclar)** — re-mapeia e adiciona só os campos novos, sem perder os já nomeados;
- **📂 Editar alias-map salvo** — reabrir um mapa já salvo para ajustar.

> Esses 3 passos são o “ensino” da tela. Feito isso, escrever testes é rápido.

### Parte 2 — Escrever o teste

Todo teste tem sempre **4 momentos** (veja [flows/Filiais/consulta_filial.py](flows/Filiais/consulta_filial.py)):

```python
# 1. ENTRAR no sistema
fc.login()
fc.open_module("FCFiliais")

# 2. AGIR na tela (sem TAB, sem coordenada — chama pelo nome/alias)
fc.field("Consulta_Campo").type("10").press("{ENTER}")

# 3. VALIDAR no banco (não basta a tela mostrar — tem que estar no banco)
registro = fc.db.query("filial_consulta", {"codigo": "10"})

# 4. FINALIZAR — só passa se o que está na tela bate com o banco
```

Os nomes entre aspas (`"Razao_Social"`, `"consultar"`) são **os aliases que você criou
na aba Mapear**.

### Parte 3 — Rodar

- Pela aba **Testes** do app (seleciona e clica Executar), **ou**
- No terminal: `python flows/Filiais/consulta_filial.py`

Mostra ✅ se passou / ❌ com o motivo, e tira screenshot automático em caso de falha.

### Resumo do passo a passo

1. **Configuracoes** → sistema/login (1×).
2. **Mapear** → fotografa a tela e dá **nomes** aos campos (1× por tela).
3. **Modulos** → ensina a **abrir** o módulo (1× por módulo).
4. **Escreve o teste**: *entrar → agir → validar no banco → finalizar*.
5. **Roda** pela aba Testes.

---

## 🎯 Princípios do framework

**NÃO usa:** coordenadas de mouse · posição X/Y · TAB para navegar · sequências de
teclado para localizar campos · `sleep` excessivo · localizadores frágeis.

**USA:** UI Automation (UIA) · foco **direto** no componente · mapeamento automático ·
`class_name` / `automation_id` / `found_index` / `instance` / hierarquia de janelas ·
**validação obrigatória em banco**.

### Regra oficial de aprovação
Um teste só é aprovado quando: executa sem erro → localiza os componentes → executa as
ações → o registro é encontrado no banco → **todos os campos conferem**. Caso contrário,
**reprovado** — mesmo que a tela tenha mostrado “salvo com sucesso”.

---

## 📥 Instalação e pré-requisitos

- **SO:** Windows 10/11 · **Python:** 3.10+ (o projeto usa um `.venv` com Python 3.14)
- **Aplicação:** Formula Certa (`fcerta.exe`) acessível
- **Banco:** Firebird/InterBase acessível (ex.: `alterdb.ib`)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Dependências principais: `pywinauto` (UIA), `pynput` (captura de teclado/mouse),
`loguru`, `tenacity`, `pyautogui`/`pywin32`, `psutil`, `fdb`, `pytest`,
`python-dotenv` (segredos), `pytest-html` (relatório), `ruff` (lint/CI).

---

## 🔐 Configuração e credenciais (`config.json` + `.env`)

Há **uma única** fonte de configuração: [`core/config.py`](core/config.py). Ela junta:

| Origem | O que guarda | Versionado? |
|--------|--------------|-------------|
| [`config.json`](config.json) | caminhos (`base`, `exe_path`, `recorder`) — **sem segredos** | ✅ sim |
| `.env` | **credenciais** (`FC_LOGIN`, `FC_SENHA`) e, opcional, `FC_EXE_PATH` | ❌ **não** (no `.gitignore`) |

`carregar_config()` resolve tudo (env sobrepõe o json) e devolve `login`/`senha`
prontos — o resto do código nunca precisa saber a origem. `salvar_config()` grava
os caminhos no `config.json` e **roteia os segredos para o `.env`**, então a aba
**Configurações** continua funcionando sem nunca vazar senha para o git.

**Primeiro uso:** copie o exemplo e preencha (ou use a aba Configurações):

```powershell
copy .env.example .env   # depois edite FC_LOGIN / FC_SENHA
```

> Nos testes, use `from core.config import LOGIN, SENHA, EXE_PATH` ou
> `carregar_config()`. **Nunca** escreva usuário/senha direto no arquivo do teste.

---

## 🖥️ As abas do app

`python app.py` abre o painel com o menu lateral:

| Aba | Para quê |
|-----|----------|
| **Testes** | Lista e executa os testes em `flows/`, com resumo PASSOU/FALHOU e logs. |
| **Recorder** | Grava interações para gerar esqueleto de teste. |
| **Mapear** | Mapeia a janela e abre o **Editor de aliases** (👁 realce, 🎯 captura manual, 🔄 re-mapear, 📂 editar salvo). |
| **Modulos** | Cadastra a **inicialização** de cada módulo (exe + passos de menu) com **🎬 gravador de teclas/cliques** (clique no item → grava `@menuitem:i,j`). Grava em `modulos.json`. |
| **Configuracoes** | `exe_path`, login/senha, pasta base dos testes. |

---

## 📂 Estrutura do projeto

```
V1/
├── app.py                     # App (Tkinter) — abas Testes/Recorder/Mapear/Modulos/Config
├── config.json                # caminhos: exe_path, pasta base, recorder (SEM segredos)
├── .env                       # credenciais FC_LOGIN/FC_SENHA (gitignored — ver .env.example)
├── modulos.json               # inicialização dos módulos (exe + passos de menu: teclas/@menuitem)
├── requirements.txt
│
├── data/                      # Massa de dados dos testes (códigos, valores esperados)
│   ├── filiais.py  notas.py  receitas.py  produtos.py
│
├── fc/                        # A DSL "estilo Cypress"
│   ├── __init__.py            #   expõe o objeto `fc`
│   ├── context.py             #   estado: janela principal, módulo ativo, aliases
│   ├── elements.py            #   Field / Button / Window (.type/.click/.should_*)
│   ├── locator_engine.py      #   alias -> elemento (prioridade de estratégias)
│   ├── mapping_store.py       #   lê/grava os alias-maps
│   ├── modules.py             #   lê/grava modulos.json
│   └── db_facade.py           #   fc.db
│
├── database/                  # Validação em banco (Firebird/InterBase)
│   ├── connection.py          #   conexão (driver fdb, troca futura isolada aqui)
│   ├── firebird_client.py     #   FirebirdClient.query()  (carrega queries/*.sql)
│   ├── validators.py          #   comparar() / todos_passaram()
│   ├── assertions.py          #   assert_saved()  (a regra de aprovação)
│   └── queries/*.sql          #   consultas reutilizáveis (parâmetros :nome)
│
├── mappings/                  # Alias-maps — nomes amigáveis dos campos por janela
│   └── FCFiliais/Filiais.json
│
├── core/                      # Base de UI/log (reutilizada pela DSL)
│   ├── actions.py             #   wait_element/wait_window/wait_app_by_exe/safe_*
│   ├── login_flow.py          #   login_ou_obter_principal()
│   ├── logging_setup.py       #   setup_logging()
│   ├── reporter.py            #   imprimir_resultado() (tabela PASS/FAIL)
│   └── config.py
│
├── pages/                     # Telas do app
│   ├── mapear_ui.py           #   aba Mapear + AliasEditorWindow
│   ├── modulos_ui.py          #   aba Módulos (cadastro + gravador de teclas/cliques)
│   └── ...
│
├── tools/
│   └── mapear_janela.py       # O mapeador (varre a árvore UIA da janela)
│
├── flows/                     # Os testes (organizados por módulo)
│   └── Filiais/consulta_filial.py
│
├── logs/                      # Logs + screenshots de falha (gerado)
└── output/                    # JSON de mapeamentos (gerado)
```

---

## 🏗️ Arquitetura técnica

O fluxo de um teste atravessa estas camadas:

```
 alias-map (mappings/)         modulos.json
        │                           │
        ▼                           ▼
   fc.field("x") ─► locator_engine ─► core/actions (UIA) ─► Formula Certa
        │                                                        │
        └──────────────► fc.db ─► database/ ─► Firebird ◄────────┘
                                   (compara tela × banco)
```

### Mapeador — `tools/mapear_janela.py`
Varre a árvore de controles da janela (pywinauto **backend UIA**) em duas fases
(`descendants()` + recursão por contêineres/abas ocultas), classifica e exporta cada
elemento como JSON com `class_name`, `control_type`, `automation_id`, `title`,
`found_index`, `instance`, `rectangle`. Captura botões mesmo sem HWND (dedup por
assinatura visual) e DevExpress/`TFagronButton`.

> **Limitação conhecida (Delphi):** rótulos `TLabel` são desenhados no canvas (sem HWND)
> e **não aparecem no UIA**. Por isso o editor de aliases usa o **👁 realce** (mostra o
> campo na tela) em vez de tentar ler o texto do rótulo.

### Alias-map — `mappings/<Módulo>/<Janela>.json`
Padroniza os localizadores sob um **alias**. O QA usa só o alias; nunca precisa conhecer
`found_index`/`instance`/`class_name`.

```json
{
  "module": "FCFiliais",
  "window": "Filiais",
  "elements": [
    { "alias": "Razao_Social", "automation_id": "854414",
      "class_name": "TDBEdit", "control_type": "Edit", "found_index": 9, "instance": 11 },
    { "alias": "consultar", "title": "Consultar", "control_type": "Button", "found_index": 3 }
  ]
}
```

**Convenção de aliases** (mantém os mappings legíveis e estáveis):

| Tipo | Convenção | Exemplos |
|------|-----------|----------|
| Campos (input) | substantivo em `Snake_Case` ou minúsculo do rótulo na tela | `Razao_Social`, `cliente`, `quantidade` |
| Botões | verbo de ação, minúsculo | `consultar`, `incluir`, `salvar`, `ok_requisicao` |
| Botão "OK" de uma janela | `ok_<janela>` (evita colisão entre telas) | `ok_embalagem`, `ok_requisicao` |
| Grids/listas | `grid_<o quê>` | `grid_notas` |

Regras: **um alias por elemento** dentro da janela; nomes **sem espaços/acentos**;
prefira o termo que o usuário vê na tela. Aliases provisórios (com `found_index` a
confirmar) ganham a marca `"_todo": true` no JSON até serem validados ao vivo.

> A massa de dados (códigos digitados, valores esperados) fica em [`data/`](data/),
> **não** nos arquivos de fluxo — assim o mesmo teste roda com cenários diferentes.

### Locator Engine — `fc/locator_engine.py`
Resolve `fc.field("alias")` para um elemento **vivo**, tentando nesta ordem
(a primeira que casar vence):

1. `automation_id` — o mais estável nos forms Delphi;
2. `class_name` + `title` — botões/labels com texto;
3. `control_type` + `title` — botões “desenhados” sem `class_name`;
4. `class_name` + `found_index`;
5. `class_name` + `instance` (ordem depth-first, estilo AutoIt).

> Como o `automation_id` é estável, a localização **não quebra** quando o
> `found_index` muda (ex.: ao inserir uma aba nova). Isso também é o que permite o
> **🔄 Re-mapear (mesclar)** casar elementos antigos × novos sem perder aliases.

### DSL — `fc/` (`context.py`, `elements.py`, `db_facade.py`)
- `FCContext` guarda a janela principal, o módulo ativo (`app`/janela) e o alias-map carregado.
- `fc.open_module(nome)` é **attach-first**: anexa ao processo se já estiver aberto;
  senão executa os passos de `menu` (de `modulos.json`) — teclas, `@menuitem:i,j` ou `@click`.
- `Field/Button/Window` fazem foco direto + ações de `core/actions.py`.

### Registro de módulos — `modulos.json` + `fc/modules.py`
Editável pelo app (aba **Modulos**) ou na mão. Lido a cada chamada (edições valem na hora).

```json
{
  "FCFiliais":  { "exe": "FCFiliais.exe",  "menu": ["%a", "@menuitem:0,0"] },
  "FCReceitas": { "exe": "FCReceitas.exe", "menu": ["%a", "{RIGHT}{RIGHT}{ENTER}"] }
}
```

`menu` é uma lista de **passos** executados na janela principal. Cada passo pode ser:

| Passo | Significado |
|-------|-------------|
| `"%a"`, `"{DOWN 3}{ENTER}"`, `"f"` | **Teclas** (sintaxe `type_keys`): `%a`=ALT+A, `{DOWN 3}`=3× baixo, `{ENTER}`, letra. |
| `"@menuitem:i,j"` | **Item de menu por índice** (Win32 `.select()`). **Livre de resolução**, sem texto nem coordenada — *recomendado*. `i`=menu de topo, `j`=subitem. |
| `"@click:X,Y"` | **Clique de mouse** na coordenada (fallback; quebra em resoluções diferentes). |
| `[]` (lista vazia) | Só **anexa** ao processo já aberto, sem navegar. |

> **Por que `@menuitem`?** O menu do Formula Certa é **owner-drawn**: nem Win32 nem UIA
> expõem os textos dos itens, então não dá para “achar o item Filiais” pelo nome nem
> clicar de forma estável por coordenada. O `@menuitem:i,j` aciona o **comando interno**
> do menu pelo índice — funciona em qualquer resolução. Na aba **Modulos**, use
> **🎬 Gravar teclas/cliques** e **clique** no item do menu: o app descobre o índice
> (`GetMenuItemRect`) e grava `@menuitem:i,j` sozinho.

---

## 📖 Referência da DSL (`fc.`)

```python
from fc import fc
```

| Categoria | Comando | O que faz |
|-----------|---------|-----------|
| Navegação | `fc.login()` | Abre/loga no Formula Certa, guarda a janela principal. |
| | `fc.open_module("FCFiliais")` | Anexa ou abre o módulo (via `modulos.json`) e carrega os aliases. |
| Campos | `fc.field("alias").type("texto")` | Foca o campo e digita (sem TAB). |
| | `.press("{ENTER}")` | Envia teclas no campo (commit, não navegação). |
| | `.clear()` | Limpa o campo. |
| | `.get_value()` | Lê o conteúdo atual. |
| | `.should_have_value("x")` | Assert: o campo contém o valor. |
| | `.should_exist()` / `.should_be_visible()` | Asserts de presença/visibilidade. |
| Botões | `fc.button("alias").click()` / `.double_click()` | Clica no botão. |
| Janelas | `fc.window("Confirmação").ok()` / `.close()` / `.press("...")` | Trata modais/avisos. |
| Banco | `fc.db.query("nome_sql", {"param": "v"})` | Roda `database/queries/nome_sql.sql` → `dict`. |
| | `fc.db.assert_saved(query=..., params=..., expected={...})` | **Aprova só se o banco bater** com o esperado. |
| Sessão | `fc.reset()` | Limpa o estado (usar no fim do teste). |

Asserts `should_*` e `assert_saved` falham com **AssertionError** (estilo Cypress).

---

## 🗄️ Validação em banco (`database/`)

Pacote com **abstração de driver** (hoje `fdb`; troca futura para `firebird-driver`
isolada em `connection.py`).

- **Queries reutilizáveis** em `database/queries/*.sql` com parâmetros nomeados:
  ```sql
  -- database/queries/filial_consulta.sql
  SELECT CDFIL, DESCRFIL, RAZAO, NRCNPJ FROM FC01000 WHERE CDFIL = :codigo
  ```
- **`FirebirdClient.query("filial_consulta", {"codigo": "10"})`** → `dict` `{COLUNA: valor}`
  (converte `:nome` → `?` por baixo).
- **`comparar(obtido, esperado)`** → lista no formato de `core/reporter.imprimir_resultado()`
  (tabela `CAMPO | ESPERADO | OBTIDO | STATUS`).
- **`assert_saved(query, expected, params)`** → roda, compara, imprime a tabela e
  **levanta AssertionError** se algum campo divergir. É a regra de aprovação para fluxos
  de inclusão/edição.

Exemplo (fluxo que salva um registro):
```python
fc.button("salvar").click()
fc.db.assert_saved(
    query="receita_salva",
    params={"produto": "51639"},
    expected={"CDCLI": "1", "CDPRO": "51639", "QTD": "200"},
)
```

> Configuração do banco em `database/connection.py` (`DB_CONFIG`: host, caminho do
> `.ib`/`.fdb`, usuário, senha).

---

## 🧩 Anatomia de um teste

Modelo recomendado (igual a [flows/Filiais/consulta_filial.py](flows/Filiais/consulta_filial.py)):

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.logging_setup import setup_logging
from core.reporter import imprimir_inicio, imprimir_resultado
from database.validators import comparar, todos_passaram
from fc import fc

CODIGO_FILIAL = "10"

def etapa_abrir_modulo():
    fc.login()
    fc.open_module("FCFiliais")

def etapa_consultar():
    fc.field("Consulta_Campo").type(CODIGO_FILIAL).press("{ENTER}")

def etapa_validar():
    registro = fc.db.query("filial_consulta", {"codigo": CODIGO_FILIAL})
    if registro is None:
        raise AssertionError(f"Filial {CODIGO_FILIAL} não existe no banco.")
    tela = {"RAZAO": fc.field("Razao_Social").get_value()}
    resultados = comparar(tela, {"RAZAO": registro["RAZAO"]})
    imprimir_resultado(resultados)
    if not todos_passaram(resultados):
        raise AssertionError("Tela divergente do banco.")

def run() -> int:
    setup_logging(log_name="Filiais_consulta", json_output=True)
    imprimir_inicio("Consulta Filial", f"Consultar e validar a filial {CODIGO_FILIAL}")
    try:
        etapa_abrir_modulo(); etapa_consultar(); etapa_validar()
        return 0
    except AssertionError as e:
        from core.actions import screenshot_on_failure
        screenshot_on_failure("filial_consulta_reprovada")
        return 1
    finally:
        fc.reset()

if __name__ == "__main__":
    sys.exit(run())
```

Também funciona em **pytest** (fixture roda o fluxo, `test_*` faz a validação) — veja o
arquivo de exemplo.

---

## ▶️ Como rodar

```powershell
# Direto
python flows\Filiais\consulta_filial.py

# Pytest
python -m pytest flows\Filiais\consulta_filial.py -v

# Ou pela aba "Testes" do app
python app.py
```

Logs em `logs/` (terminal colorido + arquivo de erro + `*.jsonl`). Screenshots de falha
em `logs/screenshots/`.

---

## 🆘 Troubleshooting

| Sintoma | Causa provável | O que fazer |
|---------|----------------|-------------|
| `Alias 'x' não existe no módulo` | O alias não está no alias-map | Aba **Mapear → Editar aliases**, crie/renomeie e salve. |
| `Não foi possível localizar o elemento` | Localizador desatualizado (tela mudou) | **🔄 Re-mapear (mesclar)** ou recapturar o campo. |
| `FCXxxx.exe não está aberto e não há menu configurado` | `menu` vazio em `modulos.json` e módulo fechado | Aba **Modulos** → grave a abertura (🎬) clicando no item do menu (`@menuitem`). |
| Abertura do módulo não funciona com Enter | Item de menu Delphi (owner-drawn) ignora Enter | Use `@menuitem:i,j` (índice Win32) em vez de `{ENTER}` — grave pelo 🎬 clicando no item. |
| Realce/captura demora muito | (já otimizado) conexão fria | O 1º clique conecta (~0,5 s); os seguintes são instantâneos (cache). |
| Reprovou mas a tela mostrou “salvo” | É o esperado — validação é no banco | Confira a query/`expected`; ajuste a tabela/colunas reais. |
| `Filial/registro não existe no banco` | Tabela/coluna erradas na query | Ajuste o `.sql` em `database/queries/`. |
| Erro de COM em thread | UIA chamado fora de thread com COM | As telas já inicializam COM nas threads de trabalho; siga esse padrão. |

---

## ✅ Boas práticas

1. **Nomeie bem os aliases** — `produto`, `quantidade`, `consultar` (não `edit18`).
2. **Sem TAB para navegar** — use `fc.field("alias")`. `press("{ENTER}")` só como *commit* de valor.
3. **Valide no banco** — todo fluxo que altera dados termina com `fc.db.assert_saved(...)`.
4. **Um alias-map por janela** — em `mappings/<Módulo>/<Janela>.json`; mantenha versionado.
5. **Cadastre a abertura do módulo** uma vez (aba **Modulos**) e reutilize com `fc.open_module(...)`.
6. **`fc.reset()` no fim** — limpa estado/conexão entre testes.
7. **Screenshots só em falha** — já é automático no `except`.

---

**Produto-alvo:** um “Cypress Desktop” para o Formula Certa — mapeamento automático de
telas Delphi, localização sem TAB/coordenadas, DSL legível, validação obrigatória em
banco e evidências automáticas, escalável para todos os módulos migrados.
