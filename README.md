# AutoTest

Projeto de automação de testes para aplicações desktop.

Este repositório contém uma automação de teste baseada em Python para fluxos de produtos e receitas, incluindo backend Flask para executar os testes e um frontend simples para monitorar a execução (frontend em produção).

## Tecnologias utilizadas

- Python
- Flask
- pywinauto
- pyautogui
- loguru
- tenacity

## Estrutura do projeto

- `app.py` - API Flask para executar fluxos de teste e consultar logs/status.
- `flows/` - Scripts de automação dos casos de teste.
  - `Receitas/CT-168635.py`
  - `Produtos/Produtos_flow.py`
  - `Notas/CT-192043.py`
- `core/` - módulos de suporte, como ações, relatório e configuração de logs.
- `front_end/` - interface web estática para interagir com a API.
- `requirements.txt` - dependências Python necessárias.
- `logs/` - pasta de logs e screenshots geradas pelos testes.

## Pré-requisitos

- Windows
- Python 3.10 ou superior instalado
- Git instalado (opcional, se preferir clonar o repositório)

## Como baixar o projeto

### Opção 1: clonar com Git

1. Abra o prompt de comando ou PowerShell.
2. Navegue até a pasta onde deseja salvar o projeto.
3. Execute:

```powershell
git clone <URL-do-repositório>
```

4. Entre na pasta do projeto:

```powershell
cd "c:\QA\teste automatizados\V1"
```

> Substitua `<URL-do-repositório>` pelo endereço do repositório Git.

### Opção 2: baixar o ZIP

1. Faça o download do arquivo ZIP do repositório.
2. Extraia o conteúdo em uma pasta de sua escolha.
3. Abra o PowerShell na pasta extraída.

## Instalação das dependências

Execute o comando abaixo no diretório do projeto:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Como executar o projeto

1. No diretório do projeto, execute:

```powershell
python app.py
```

2. Abra o navegador e acesse:

```text
http://127.0.0.1:5000
```

3. Use o frontend ou faça chamadas à API para rodar os fluxos.

## Como executar um fluxo diretamente

Se quiser executar um fluxo Python diretamente, rode:

```powershell
python flows\Receitas\CT-168635.py
```

Substitua o caminho pelo script de fluxo desejado.

## Observações

- Essa automação foi criada para rodar em ambiente Windows com aplicações desktop Delphi/VCL.
- Certifique-se de que a aplicação sob teste esteja aberta e acessível antes de iniciar os testes.
- Caso precise alterar ou adicionar novos fluxos, coloque os scripts em `flows/` e atualize `app.py` se quiser que sejam descobertos pela API.
