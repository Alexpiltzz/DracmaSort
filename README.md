# Giveaways Tools — Gerador de Códigos de Sorteio

Gera códigos de sorteio únicos (4 dígitos, de `0001` a `9999`) a partir de uma
planilha de participantes com nome, e-mail e a quantidade de códigos de cada um.
Os códigos saem em um CSV separado, prontos para envio aos participantes.

## Recursos

- Aceita planilhas **Excel (.xlsx)** ou **CSV (.csv)** — o formato é detectado automaticamente
  (o CSV aceita vírgula ou ponto-e-vírgula).
- **Seleção manual do arquivo** por janela nativa do Windows (tkinter), com opção de
  passar o caminho como argumento.
- Códigos **aleatórios e sem repetição**, inclusive entre execuções diferentes:
  os códigos usados ficam registrados em `codigos_emitidos.json`.
- Respeita a coluna de **quantidade** de cada participante.
- Saída em CSV com delimitador `;` e UTF-8 com BOM, compatível com Excel pt-BR.

## Requisitos

- [uv](https://docs.astral.sh/uv/) (recomendado) ou Python 3.13+
- Este projeto usa o Python 3.13 instalado no sistema (necessário pelo tkinter do diálogo).
  A venv já está configurada para usá-lo.

## Instalação

```sh
uv sync
```

Isso cria a venv em `.venv` e instala as dependências (`openpyxl`) e o comando
`gerador-codigos`.

## Como usar

```sh
# Abre a janela para escolher a planilha
uv run gerador-codigos

# Ou informando o caminho da planilha
uv run gerador-codigos --arquivo participantes.xlsx

# Alternativa direta ao módulo
uv run python -m gerador_codigos
```

### Opções

| Opção | Descrição |
|---|---|
| `--arquivo` | Caminho da planilha de entrada (.xlsx ou .csv). Se omitido, abre o seletor de arquivos. |
| `--saida` | Caminho do CSV de saída. Padrão: `codigos_sorteados_<data>_<hora>.csv` na pasta da planilha. |
| `--registro` | Caminho do arquivo de códigos usados. Padrão: `codigos_emitidos.json` na raiz do projeto. |

## Formato da planilha de entrada

A primeira linha deve conter os cabeçalhos. Os nomes das colunas são flexíveis
(sem diferenciar maiúsculas ou acentos):

- **Nome** — também aceita `name`, `participante`
- **E-mail** — também aceita `email`, `correio`
- **Quantidade** — também aceita `qtd`, `qty`, `numero`, `n`

Exemplo (`participantes.csv`):

```csv
Nome;E-mail;Quantidade
Ana Souza;ana@example.com;3
João Pereira;joao@example.com;2
```

Linhas inválidas (nome vazio, e-mail sem formato válido, quantidade ausente ou
menor que 1) são ignoradas e listadas como avisos na saída do terminal.

## Formato da saída

`codigos_sorteados_<data>_<hora>.csv`, uma linha por participante com os códigos
separados por vírgula:

```csv
Nome;E-mail;Códigos
Ana Souza;ana@example.com;4631, 3087, 1050
João Pereira;joao@example.com;5793, 0704
```

## Sobre a não-repetição

O arquivo `codigos_emitidos.json`, na raiz do projeto, guarda todos os códigos já
sorteados. A cada execução, apenas códigos ainda livres são sorteados. **Preserve
esse arquivo** (ele pode ser versionado no Git ou copiado junto) para garantir que
os códigos nunca se repitam, mesmo rodando o script novamente. Os números vão de
`0001` a `9999` (9.999 códigos possíveis); ao esgotar, o script informa o erro.

## Desenvolvimento

```sh
uv run pytest        # testes
uv run ruff check    # lint
```

## Estrutura

```
src/gerador_codigos/
├── __main__.py    # CLI + diálogo de seleção de arquivo
├── core.py        # geração aleatória + registro de códigos usados
└── io.py          # leitura xlsx/csv e escrita do CSV de saída
tests/             # testes (pytest)
```