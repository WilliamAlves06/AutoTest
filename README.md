# 🤖 FC Automation — automação para o Formula Certa (Delphi)

[![CI](https://github.com/WilliamAlves06/AutoTest/actions/workflows/ci.yml/badge.svg)](https://github.com/WilliamAlves06/AutoTest/actions/workflows/ci.yml)

Framework de automação de testes **desktop** para o sistema legado **Formula Certa**
(Delphi/VCL). O QA escreve testes em comandos simples e legívei — e a aprovação
**de dados** (a mensagem visual de sucesso não basta).

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

`python app.py` abre o **AutoTest QA Studio** (interface escura, CustomTkinter — tema
central em [ui/theme.py](ui/theme.py)). A versão antiga em Tkinter clássico continua
disponível como fallback em [app_legacy.py](app_legacy.py). Menu lateral:

| Aba | Para quê |
|-----|----------|
| **Testes** | Lista e executa os testes em `flows/`, com resumo PASSOU/FALHOU e logs. |
| **Recorder** | Grava cliques/digitação e **gera o teste já na DSL `fc`** (`fc.field`/`fc.button` por alias), registrando campos novos nos mappings. Toggle **"DSL fc"** (ligado por padrão; desligue para o formato legado `wait_element`). |
| **Mapear** | Mapeia a janela e abre o **Editor de aliases** (👁 realce, 🎯 captura manual, 🔄 re-mapear, 📂 editar salvo). |
| **Modulos** | Cadastra a **inicialização** de cada módulo (exe + passos de menu) com **🎬 gravador de teclas/cliques** (clique no item → grava `@menuitem:i,j`). Grava em `modulos.json`. |
| **Configuracoes** | `exe_path`, login/senha, pasta base dos testes. |

---

## 📂 Estrutura do projeto

```
V1/
├── app.py                     # Entrypoint do QA Studio (GUI moderna em ui/)
├── app_legacy.py              # GUI antiga (Tkinter clássico) — fallback
├── ui/                        # GUI moderna (CustomTkinter): theme, widgets, dashboard, shell
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

### Recorder — gravar e gerar teste na DSL `fc`
A aba **Recorder** grava cliques/digitação/teclas (`core/recorder/action_detector.py`,
backend `pynput`+Win32) e, na exportação, gera um teste **já na DSL `fc`**:

- `core/recorder/fc_codegen.py` — converte as ações em `fc.login()` / `fc.open_module(...)` /
  `fc.field("alias").type(...).press("{ENTER}")` / `fc.button("alias").click()`, e deixa o
  TODO de validação no banco;
- `core/recorder/alias_resolver.py` — resolve cada elemento para um **alias**: reaproveita o
  alias-map do módulo (casando por `automation_id` ou `class+índice`) e, quando o campo é novo,
  **cria um alias e o registra no mapping** (merge, sem sobrescrever os existentes).

Adaptando a lógica do **codegen do Playwright** ao desktop:

- **Código ao vivo** — com "DSL fc" ligado, o painel mostra o teste `fc` sendo gerado
  **enquanto você interage** (regenera a cada ação), não só no Export.
- **Verificações (assertions)** — a toolbar *Verificações* tem `✓ visível` / `✓ texto` /
  `✓ valor`: clique no tipo e depois **no elemento na tela** → gera
  `fc.field("alias").should_be_visible()` / `.should_have_text(...)` / `.should_have_value(...)`
  (lê o valor atual do campo no momento do clique).

> É o análogo ao *codegen* do Playwright: em vez de coordenadas, sai código legível por alias —
> e o mapeamento cresce sozinho conforme você grava. Toggle **"DSL fc"** liga/desliga (o formato
> legado `wait_element` continua disponível).

### Registro de módulos — `modulos.json` + `fc/modules.py`
Editável pelo app (aba **Modulos**) ou na mão. Lido a cada chamada (edições valem na hora).

```json
{
  "FCFiliais":  { "exe": "FCFiliais.exe",  "menu": ["@menuitem:0,0"] },
  "FCReceitas": { "exe": "FCReceitas.exe", "menu": ["%a", "{RIGHT}{RIGHT}{ENTER}"] }
}
```

`menu` é uma lista de **passos** executados na janela principal. Cada passo pode ser:

| Passo | Significado |
|-------|-------------|
| `"%a"`, `"{DOWN 3}{ENTER}"`, `"f"` | **Teclas** (sintaxe `type_keys`): `%a`=ALT+A, `{DOWN 3}`=3× baixo, `{ENTER}`, letra. |
| `"@menuitem:i,j"` | **Item de menu por índice**, acionado com **clique real** calculado via `GetMenuItemRect` (não `%a`/`{ENTER}`/`.select()`). **Livre de resolução**, sem texto nem coordenada fixa — *recomendado*. `i`=menu de topo, `j`=subitem. Não combine com `"%a"` antes — o próprio passo abre o item de topo clicando nele. |
| `"@click:X,Y"` | **Clique de mouse** na coordenada (fallback; quebra em resoluções diferentes). |
| `[]` (lista vazia) | Só **anexa** ao processo já aberto, sem navegar. |

> **Por que `@menuitem` clica em vez de usar `.select()`/`{ENTER}`?** O menu do Formula
> Certa é **owner-drawn** e alguns itens (ex.: Filiais) validam permissão de módulo de um
> jeito que só passa com **clique físico** — acionar o mesmo item por `.select()` (Win32)
> ou `{ENTER}` cai num caminho que dispara "Modulo nao esta cadastrado para esse usuario",
> mesmo com o índice certo. Por isso `@menuitem:i,j` calcula a posição do item na tela via
> `GetMenuItemRect` (livre de resolução, sem coordenada fixa) e simula um clique real ali.
> Na aba **Modulos**, use **🎬 Gravar teclas/cliques** e **clique** no item do menu: o app
> descobre o índice e grava `@menuitem:i,j` sozinho.

---

## 📖 Referência da DSL (`fc.`)

> Esta seção é pra quem **só escreve teste** — você não precisa saber como cada comando
> funciona por dentro (UIA, alias-map, etc.). Trate cada um como uma instrução que você
> daria pra alguém testando manualmente: "digite tal coisa", "clique em tal botão",
> "confira no banco".

```python
from fc import fc
```

### Navegação — entrar no sistema e abrir telas

| Comando | O que faz |
|---------|-----------|
| `fc.login()` | Faz login no Formula Certa. |
| `fc.open_module("FCFiliais")` | Abre o módulo (ou aproveita se já estiver aberto). |
| `fc.tab("Estoques")` | Clica na aba "Estoques" da tela atual. Sub-aba: `fc.tab("Geral", "Dados Adicionais")`. |

### Campos — `fc.field("alias")`

Use para **o que você digita**: caixas de texto, combos, etc. O `"alias"` é o nome que
você deu ao campo na aba **Mapear**.

| Comando | O que faz |
|---------|-----------|
| `.type("texto")` | Digita no campo. |
| `.press("{ENTER}")` | Envia uma tecla (ex.: confirmar uma busca). |
| `.clear()` | Limpa o campo. |
| `.get_value()` | Lê o que está escrito no campo agora. |
| `.should_have_value("10")` | Verifica se o campo contém exatamente "10" — se não, o teste **reprova**. |
| `.should_exist()` | Verifica se o campo existe na tela. |
| `.should_be_visible()` | Verifica se o campo está visível. |

### Botões — `fc.button("alias")`

Use para **o que você clica**: salvar, consultar, ok, etc.

| Comando | O que faz |
|---------|-----------|
| `.click()` | Clica no botão. |
| `.double_click()` | Clique duplo. |
| `.should_exist()` / `.should_be_visible()` | Mesmas verificações dos campos. |

> 💡 **Dica:** `field` e `button` são só rótulos pra deixar o teste mais fácil de ler —
> os dois sabem `.click()`. Use `field` pra algo que você digita e `button` pra algo que
> você clica; se trocar por engano, o teste funciona do mesmo jeito.

### Janelas/diálogos — `fc.window("Título")`

Use para confirmações, avisos e modais que aparecem por cima da tela.

| Comando | O que faz |
|---------|-----------|
| `.ok()` | Confirma o diálogo (equivale a apertar Enter). |
| `.close()` | Fecha o diálogo (equivale a Alt+F4). |
| `.press("{ENTER}")` | Envia uma tecla pro diálogo. |
| `.should_exist()` | Verifica se o diálogo apareceu. |

### Banco — `fc.db`

| Comando | O que faz |
|---------|-----------|
| `fc.db.query("nome_sql", {"param": "v"})` | Busca **um** registro no banco, pra você comparar. Devolve `None` se não achar. |
| `fc.db.client.query_all("nome_sql", {"param": "v"})` | Igual, mas devolve **todas** as linhas (lista) — pra grids/múltiplos registros. |
| `fc.db.assert_saved(query=..., params=..., expected={...})` | Busca **e** já **aprova/reprova** o teste sozinho, comparando com o esperado. |

> Detalhes e exemplos completos na seção [Validação em banco](#-validação-em-banco-database) abaixo.

### Sessão

| Comando | O que faz |
|---------|-----------|
| `fc.reset()` | Encerra a sessão — chame sempre no fim do teste (no `finally`). |

> Todo comando devolve o próprio elemento, então dá pra **encadear**:
> `fc.field("produto").type("123").should_have_value("123")`.
>
> Os comandos `should_*` e `assert_saved` **reprovam o teste com uma mensagem clara**
> quando algo não bate — é assim que você sabe o motivo da falha sem precisar investigar.

---

## 🗄️ Validação em banco (`database/`)

> De novo: aqui é só **o que fazer**, não como funciona por dentro. Pense em `fc.db`
> como "ir conferir no banco" — o resto (driver, conexão, SQL) já está pronto.

### `fc.db.query("nome_sql", {"param": "valor"})` — buscar um registro

Cada query reutilizável é um arquivo `.sql` em `database/queries/`. Você chama pelo
**nome do arquivo, sem `.sql`**, e passa um dict com os parâmetros que o SQL espera:

```sql
-- database/queries/filial_consulta.sql
SELECT CDFIL, DESCRFIL, RAZAO, NRCNPJ FROM FC01000 WHERE CDFIL = :codigo
```
```python
registro = fc.db.query("filial_consulta", {"codigo": "10"})
# registro = {"CDFIL": "10", "DESCRFIL": "...", "RAZAO": "...", "NRCNPJ": "..."}
# registro é None se a filial 10 não existir no banco
```

Regras simples:
- A chave do dict (`"codigo"`) tem que ter o **mesmo nome** do `:placeholder` no `.sql`
  (`:codigo`) — é assim que o valor chega até a query.
- O resultado é a **primeira linha** encontrada, com as colunas em **maiúsculas** (como
  o Firebird devolve) — ou `None`, se não achar nada. Sempre trate o caso de `None`
  antes de usar o resultado.
- Precisa de mais de uma linha (ex.: validar um grid)? Use `fc.db.client.query_all(...)`
  — mesma ideia, mas devolve **todas** as linhas como uma lista de dicts.

### `fc.db.assert_saved(...)` — buscar **e** aprovar/reprovar sozinho

É o `fc.db.query(...)` de cima, só que automatizado: ele busca o registro, compara
**campo a campo** com o que você espera, imprime uma tabela (`CAMPO | ESPERADO | OBTIDO
| STATUS`, com ✔/✘) e **reprova o teste** (`AssertionError`) se qualquer campo não bater.

```python
fc.button("salvar").click()
fc.db.assert_saved(
    query="receita_salva",
    params={"produto": "51639"},
    expected={"CDCLI": "1", "CDPRO": "51639", "QTD": "200"},
)
```

**Quando usar qual:**

| Use... | Quando... |
|--------|-----------|
| `fc.db.query(...)` | Você quer **olhar** o registro e decidir o que fazer (ex.: comparar manualmente o que está na tela, num fluxo de **consulta**). |
| `fc.db.assert_saved(...)` | Você só quer que o teste **aprove ou reprove sozinho** comparando com valores esperados (ex.: ao fim de um fluxo de **inclusão/edição** que salva dados). |

> Configuração do banco em `database/connection.py` (`DB_CONFIG`: host, caminho do
> `.ib`/`.fdb`, usuário, senha) — não precisa tocar nisso pra escrever testes.

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
| Abertura do módulo não funciona com Enter | Item de menu Delphi (owner-drawn) ignora Enter | Use `@menuitem:i,j` em vez de `{ENTER}` — grave pelo 🎬 clicando no item. |
| Diálogo "Atenção! Modulo nao esta cadastrado para esse usuario" ao abrir módulo (mesmo no item certo) | O item foi acionado via `.select()`/Enter em vez de clique físico — alguns itens só validam permissão corretamente com clique real | `@menuitem:i,j` já resolve isso (clica de verdade, calculado via `GetMenuItemRect`); **não combine com `"%a"` antes** — é redundante e pode reabrir o mesmo caminho do Enter. |
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
