# Giveaways Tools — Gerador de Códigos de Sorteio

Gera códigos de sorteio únicos (4 dígitos, de `0001` a `9999`) a partir de uma planilha de participantes com nome, e-mail e a quantidade de códigos de cada um. Os códigos saem em um CSV de saída e são enviados por e-mail com controle anti-spam, relatório de envio em CSV e barra de progresso com previsão de entrega (ETA).

---

## Recursos

- Aceita planilhas **Excel (.xlsx)** ou **CSV (.csv)** — o formato é detectado automaticamente (aceita `;` ou `,` e encodings `utf-8-sig`/`cp1252`).
- **Seleção manual do arquivo** por janela nativa do Windows (Tkinter) ou via linha de comando (`--arquivo`).
- **Códigos aleatórios e sem repetição**, inclusive entre execuções diferentes: os códigos usados ficam salvos em `codigos_emitidos.json`.
- **Login Interativo via CLI**: Solicita login, e-mail de origem (caixa compartilhada) e senha (com mascaramento seguro) na execução, com opção de usar o `.env` como fallback ao pressionar Enter.
- **Relatórios de Envio (CSV)**: Gera automaticamente um arquivo `relatorio_envio_YYYYMMDD_HHMMSS.csv` com o status de cada participante (`Sucesso`, `Falha` ou `Rejeitado`), data/hora e detalhes do disparo.
- **Proteção Anti-Spam / Rate Limiting**:
  - Delays aleatórios entre envios (7 a 10 segundos).
  - Pausa de segurança de **5 a 10 minutos** a cada **50 e-mails enviados** para prevenir bloqueios SMTP.
- **Barra de Progresso com Previsão (tqdm)**: Exibe a barra de progresso em tempo real no terminal com o número de envios, tempo decorrido e tempo estimado de conclusão (ETA).

---

## Requisitos

- [uv](https://docs.astral.sh/uv/) (recomendado) ou Python 3.13+
- Este projeto utiliza o Python 3.13 instalado no sistema (necessário pelo Tkinter do diálogo visual).

---

## Instalação

```powershell
uv sync
```

Isso cria o ambiente virtual em `.venv` e instala as dependências (`openpyxl`, `tqdm`, `PyQt6`).

---

## Como Usar

### 1. Forma Direta (Recomendada)

```powershell
# Execução interativa (abre a janela para selecionar a planilha)
uv run python main.py

# Informando o arquivo diretamente
uv run python main.py --arquivo participantes.xlsx

# Modo teste (envia apenas 1 e-mail de validação para GIVEAWAY_SMTP_TO)
uv run python main.py --arquivo participantes.xlsx --teste
```

### 2. Atalho Registrado no CLI

```powershell
uv run gerador-interativo --arquivo participantes.xlsx
```

### 3. Interface Gráfica

```powershell
# Abre a Central de Sorteios (PyQt)
uv run python main_ui.py

# Ou pelo atalho registrado
uv run gerador-grafico
```

A tela mostra os participantes válidos importados, os códigos gerados e o
status individual de cada envio. A aba **Mensagem** permite editar o assunto
e o corpo usando Markdown, com uma prévia visual do HTML gerado em tempo real.
Use `{nome}`, `{codigos}`, `{remetente}` e `{destinatario}` para inserir dados
automaticamente em cada e-mail. A opção **Simular envios** fica marcada por
padrão: ela gera o relatório e atualiza a tabela sem disparar mensagens reais.
Para um envio real, desmarque a opção, informe a senha SMTP e confirme a ação.
O envio acontece em segundo plano, então a janela permanece responsiva e pode
ser interrompido entre mensagens ou durante as pausas anti-spam.

O seletor **Tema** no cabeçalho alterna entre as paletas **Claro** (branco,
cinza suave, transparências e laranja) e **Escuro** (preto, cinza, transparências
e laranja). A aparência acrílica é criada pelas superfícies translúcidas e pelo
contraste entre os painéis, sem alterar a lógica do aplicativo.

---

## Formato da Planilha de Entrada

A primeira linha deve conter os cabeçalhos. Os nomes das colunas são flexíveis (sem diferenciar maiúsculas ou acentos):

- **Nome** — também aceita `name`, `participante`
- **E-mail** — também aceita `email`, `correio`
- **Quantidade** — também aceita `qtd`, `qty`, `numero`, `n`

Exemplo (`participantes.csv`):

```csv
Nome;E-mail;Quantidade
Ana Souza;ana@example.com;3
João Pereira;joao@example.com;2
```

Linhas inválidas (nome vazio, e-mail sem formato válido ou quantidade menor que 1) são ignoradas com avisos no terminal.

---

## Formato das Saídas

Ao final da execução, são gerados no mesmo diretório da planilha de entrada:

### 1. CSV dos Códigos Sorteados (`codigos_sorteados_<data>_<hora>.csv`)

```csv
Nome;E-mail;Códigos
Ana Souza;ana@example.com;4631, 3087, 1050
João Pereira;joao@example.com;5793, 0704
```

### 2. CSV do Relatório de Envio (`relatorio_envio_<data>_<hora>.csv`)

```csv
Nome;E-mail;Códigos;Status;Data_Hora;Detalhes
Ana Souza;ana@example.com;4631, 3087, 1050;Sucesso;2026-08-28 10:15:20;Enviado com sucesso
João Pereira;joao@example.com;5793, 0704;Sucesso;2026-08-28 10:15:30;Enviado com sucesso
```

---

## Mensagem de E-mail (Markdown convertido para HTML)

Na interface gráfica, o corpo da mensagem é escrito em Markdown e convertido
automaticamente para HTML antes do envio. O modelo padrão é:

```markdown
Olá, **{nome}**!

Agradecemos pela realização da matrícula.

Você recebeu os seguintes números para participar do nosso sorteio:

## {codigos}

Guarde estes números.

Atenciosamente,
**Colégio**
```

---

## Configuração do Envio (`.env` opcional)

As credenciais SMTP podem ser informadas no momento da execução (CLI interativo) ou pré-configuradas no arquivo `.env` na raiz do projeto:

```dotenv
GIVEAWAY_SMTP_HOST=smtp.office365.com
GIVEAWAY_SMTP_PORT=587
GIVEAWAY_SMTP_LOGIN=alex.fritsche@adm.educadventista.org
GIVEAWAY_SMTP_PASS=SUA_SENHA_AQUI
GIVEAWAY_SMTP_FROM=dpcab.anc@adm.educadventista.org
GIVEAWAY_SMTP_TO=alexpiltz.fritsche@gmail.com
```

---

## Sobre a Não-Repetição

O arquivo `codigos_emitidos.json`, na raiz do projeto, guarda todos os números já sorteados (`0001` a `9999`). **Preserve este arquivo** para que os códigos nunca se repitam entre execuções futuras.

---

## Desenvolvimento e Testes

```powershell
uv run pytest        # Executa a suíte de testes unitários (27 testes)
uv run ruff check    # Linter de código
```

---

## Estrutura do Projeto

```
Giveaways_Tools/
├── main.py              # Ponto de entrada raiz do script
├── main_ui.py            # Ponto de entrada da interface gráfica PyQt
├── codigos_emitidos.json# Registro persistente de códigos sorteados
├── pyproject.toml       # Dependências e configurações do projeto
├── README.md            # Documentação completa
├── src/
│   └── code_gen/
│       ├── __init__.py   # Metadados do pacote
│       ├── __main__.py   # CLI por argumentos e diálogo visual
│       ├── main.py       # Fluxo interativo completo (envio, rate limit, tqdm)
│       ├── ui.py         # Interface gráfica (importação, revisão e envio)
│       ├── core.py       # Algoritmo de sorteio e persistência
│       ├── io.py         # Leitura de planilhas e exportação de CSVs/Relatórios
│       └── smtp.py       # Envio de e-mails HTML via SMTP
└── tests/               # Testes unitários com pytest
```
