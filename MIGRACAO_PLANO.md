# Plano de Migração — AutoTest → fluxo estilo Playwright

> Arquivo de contexto do projeto. Convergir o AutoTest (automação desktop Delphi/VCL
> via `pywinauto`) para o fluxo de trabalho do projeto **playwright_QA** (POM, fixtures,
> dados separados, specs de negócio, relatório, CI/CD) — **sem perder** o mapeamento
> e as configurações atuais, apenas centralizando.

Repositórios de referência:
- Legado: https://github.com/WilliamAlves06/AutoTest
- Modelo: https://github.com/WilliamAlves06/playwright_QA

---

## Princípio central

A migração **já começou**. O pacote `fc/` é o equivalente ao `page.` do Playwright
(DSL fluente) e os `mappings/*.json` já são Page Objects externalizados.
**Não reescrever — convergir** e adicionar o que falta (fixtures padronizadas,
relatório HTML, CI).

### Mapa de arquitetura (Playwright → AutoTest)

| Conceito Playwright            | Equivalente no AutoTest                         | Estado     |
|--------------------------------|-------------------------------------------------|------------|
| Page Object (`pages/*.ts`)     | `mappings/<Módulo>/<Janela>.json` + `fc/`       | Parcial    |
| Fluent API (`page.login()`)    | `fc.login()`, `fc.button(...).click()`          | Pronto     |
| Fixtures (`pages.fixture.ts`)  | `conftest.py` (raiz) + fixtures `fc_*`          | Em curso   |
| `data/`, `fixtures/users.ts`   | `data/*.py` + `.env`                            | Pronto     |
| `tests/*.spec.ts`              | `flows/` (convergindo p/ DSL `fc`)              | Em curso   |
| HTML report + Trace            | `pytest-html` + `core/reporter.py` + loguru     | Em curso   |
| GitHub Actions                 | `.github/workflows/ci.yml`                       | Em curso   |

### Regras de "mais fluido"
- `config.json` + `.env` são a **única** fonte de configuração (nenhuma constante de
  sistema/credencial nos flows).
- Credenciais ficam no `.env` (gitignored), nunca no arquivo versionado.
- `mappings/*.json` é a **única** fonte de seletores (nada de `wait_element` inline nos flows).
- Toda massa de dados de teste fica em `data/`.

---

## Fases

### Fase 0 — Fundação  ✅
- [x] Loader único `core/config.py` (config.json + `.env`), usado também pelo `app.py`.
- [x] `login`/`senha` movidos para `.env` (python-dotenv); removidos do `config.json` versionado; `.env` no `.gitignore`.
- [x] Pasta `data/` com a massa de dados (`filiais/notas/receitas/produtos`).
- [x] Flows DSL (Filiais/Receitas) lendo de `data/`.
- [x] Convenção de aliases e config documentadas no README.

### Fase 1 — Page Objects (mappings) completos
- [ ] Gerar `mappings/FCNotas/Notas.json` (mapear FC11100 pela aba Mapear).  *(requer app vivo)*
- [ ] Gerar `mappings/FCProdutos/Produtos.json`.  *(requer app vivo)*
- [ ] Confirmar os `found_index` provisórios em `mappings/FCReceitas/Receitas.json` (`_todo`).
- [x] `mappings/FCFiliais/Filiais.json` validado (curado).
- [ ] Criar mapping da janela principal e de login.

### Fase 2 — Migrar flows para a DSL `fc`
- [ ] Converter `flows/Notas/CT-192043.py` para `fc.*` + mapping.
- [ ] Converter `flows/Produtos/Produtos_flow.py`.
- [x] `flows/Receitas/CT-168635.py` na DSL.
- [x] `flows/Filiais/consulta_filial.py` na DSL (modelo de referência).
- [ ] Remover `wait_element`/`safe_type` inline dos flows.
- [ ] Padronizar nomes para `test_*.py`.

### Fase 3 — Fixtures e estrutura de testes
- [ ] `conftest.py` na raiz com fixtures: app conectado, login feito, módulo aberto.
- [ ] Fixture que injeta `fc` pronto por módulo (escopo `session`/`module`).
- [ ] Separar *arrange* (etapas) das *asserts* (`test_*`).
- [ ] `pytest.ini` com markers por módulo (`notas`, `receitas`, `produtos`, `e2e`, `unit`).

### Fase 4 — Relatório e evidências
- [ ] `pytest-html` (relatório HTML por execução).
- [ ] Anexar `screenshot_on_failure` automaticamente ao relatório.
- [ ] Padronizar logs JSONL + reporter por execução (timestamp/pasta).
- [ ] (Opcional) Allure.

### Fase 5 — CI/CD (GitHub Actions)
- [ ] Workflow em PR/push: lint (`ruff`) + import smoke (runner Ubuntu).
- [ ] Job de testes unitários puros (`database/validators.py`, `fc/mapping_store.py`, utils).
- [ ] **Atenção:** o E2E desktop NÃO roda em runner de nuvem — exige *runner self-hosted Windows*
      com `fcerta.exe` + Firebird.
- [ ] Publicar relatório HTML como artifact + badge no README.

### Fase 6 — GUI redesign (Figma)
- [ ] Aplicar o design system do Figma na tela Testes (`app.py`/`pages/testes.py`).
- [ ] Refazer `pages/configuracoes.py`, `pages/recorder_ui.py`, `pages/mapear_ui.py`, `pages/modulos_ui.py`.
- [ ] Extrair tema central (cores/fontes). Avaliar **CustomTkinter**/**PySide6** p/ chegar perto do Figma.
- Figma: https://www.figma.com/design/gZ1JuoH25ewfcFLiaL3WxL

### Extra — Recorder estilo Playwright
- [ ] Gravar interações (clique/digitação/foco) e gerar um `test_*.py` já na DSL `fc`,
      resolvendo cada elemento para um alias do mapping (codegen).

---

## Ordem de execução sugerida
1. **Fase 0** (feita) destrava o resto.
2. **Fase 1 + 2** módulo a módulo (Notas → Receitas → Produtos), validando cada um *(precisa do app vivo)*.
3. **Fase 3** (fixtures), que depende dos flows já no padrão `fc`.
4. **Fase 4 e 5** em paralelo.
5. **Fase 6** é independente.
