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

- **Aluno** — também aceita `aluno_nome`, `student`
- **Nome** — também aceita `name`, `participante`
- **E-mail** — também aceita `email`, `correio`
- **Quantidade** — também aceita `qtd`, `qty`, `numero`, `n`

Exemplo (`participantes.csv`):

```csv
Aluno;Nome;E-mail;Quantidade
Ana Souza;Ana;ana@example.com;3
João Pereira;João;joao@example.com;2
```

> **Filtro de alunos repetidos:** a coluna **Aluno** identifica quem já participou.
> Ao gerar os códigos, alunos que constam no registro `alunos_rastreados.json`
> são ignorados (não recebem números novamente). As demais colunas (Nome,
> E-mail, Quantidade) são apenas dados de envio e não geram filtro algum.

Linhas inválidas (aluno vazio, nome vazio, e-mail sem formato válido ou quantidade menor que 1) são ignoradas com avisos no terminal.

---

## Formato das Saídas

Ao final da execução, são gerados no mesmo diretório da planilha de entrada:
### 1. CSV dos Códigos Sorteados (`codigos_sorteados_<data>_<hora>.csv`)

```csv
Aluno;Nome;E-mail;Códigos
Ana Souza;Ana;ana@example.com;4631, 3087, 1050
João Pereira;João;joao@example.com;5793, 0704
```

### 2. CSV do Relatório de Envio (`relatorio_envio_<data>_<hora>.csv`)

```csv
Aluno;Nome;E-mail;Códigos;Status;Data_Hora;Detalhes
Ana Souza;Ana;ana@example.com;4631, 3087, 1050;Sucesso;2026-08-28 10:15:20;Enviado com sucesso
João Pereira;João;joao@example.com;5793, 0704;Sucesso;2026-08-28 10:15:30;Enviado com sucesso
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
GIVEAWAY_SMTP_LOGIN=seu.email@dominio.com
GIVEAWAY_SMTP_PASS=SUA_SENHA_AQUI
GIVEAWAY_SMTP_FROM=caixa.compartilhada@dominio.com
GIVEAWAY_SMTP_TO=seu.email@dominio.com
```

---

## Atualização Automática do Executável

O executável verifica ao iniciar se há uma release mais recente publicada no
GitHub e, com confirmação do usuário, baixa e aplica a atualização (o `.exe`
atual é substituído ao fechar o programa, com rollback via `DracmaSort.exe.bak`).

### Sem configuração de credencial

As releases do repositório são **públicas**, então o updater funciona **sem
token e sem arquivos `.env`** — a distribuição é apenas o `DracmaSort.exe`.
O usuário final não precisa fornecer nenhuma credencial para verificar ou baixar
atualizações.

### Publicação de releases (ambiente de desenvolvimento)

Publicar uma nova versão continua exigindo o token de **escrita**
(`GITHUB_RELEASE_TOKEN`), definido **somente** no shell do desenvolvedor:

```powershell
$env:GITHUB_RELEASE_TOKEN = "seu_token_com_permissao_de_escrita"
uv run python main_exe.py --release
```

> O `GITHUB_RELEASE_TOKEN` é usado exclusivamente para criar a release e fazer
> upload do asset. Ele **nunca** é embutido no executável, nem vai para o build,
> nem é distribuído ao usuário final — os PATs de leitura anteriormente usados
> pelo updater foram descontinuados.

---

## Sobre a Não-Repetição

O arquivo `codigos_emitidos.json`, na raiz do projeto, guarda todos os números já sorteados (`0001` a `9999`). **Preserve este arquivo** para que os códigos nunca se repitam entre execuções futuras.

O arquivo `alunos_rastreados.json`, também na raiz do projeto, guarda os nomes dos alunos que já passaram pelo sistema. **Preserve este arquivo** para que um mesmo aluno não receba números de sorteio novamente em execuções futuras.

---

## Desenvolvimento e Testes

```powershell
uv run pytest        # Executa a suíte de testes unitários
uv run ruff check    # Linter de código
```

### Editando a Interface Gráfica

A janela da Central de Sorteios é definida em `assets/main_window.ui`
(Qt Designer) e carregada em tempo de execução. As folhas de estilo vivem em
`assets/style_light.qss` e `assets/style_dark.qss` (tema claro/escuro).

```powershell
# Abrir o layout no Qt Designer
uv run --with pyqt6-tools pyqt6-tools designer
```

- Os nomes dos objetos no `.ui` devem coincidir com os atributos usados no
  Python (`theme_button`, `import_button`, ...) e com os seletores do QSS.
- Propriedades que o `.ui` não serializa (tamanhos de splitter, stretches)
  são reaplicadas em `_apply_runtime_geometry()`, em `src/gui/ui.py`.
- **Assets sempre obrigatórios**: não há fallback de CSS. No desenvolvimento, o
  `ui`/`qss` é lido de `assets/` na raiz do repositório; no executável, os
  arquivos vêm empacotados dentro do binário (sem a pasta `assets/` ao lado).

---

## Estrutura do Projeto

```
Giveaways_Tools/
├── main.py              # Ponto de entrada raiz do script
├── main_ui.py           # Ponto de entrada da interface gráfica PyQt
├── main_exe.py          # Gera o executável Windows (PyInstaller) + --release
├── make_release.ps1     # Publica release + asset no GitHub (alternativa ao --release)
├── build_main_ui.ps1    # Script alternativo de build do executável
├── codigos_emitidos.json# Registro persistente de códigos sorteados
├── alunos_rastreados.json# Registro persistente de alunos já rastreados
├── pyproject.toml       # Dependências e configurações do projeto
├── .env.example         # Template das variáveis SMTP (carrega só GIVEAWAY_SMTP_*)
├── README.md            # Documentação completa
├── assets/              # Recursos de interface
│   ├── main_window.ui   # Layout da janela (Qt Designer)
│   ├── style_light.qss  # Folha de estilo do tema claro
│   ├── style_dark.qss   # Folha de estilo do tema escuro
│   └── png_to_ico.py    # Converte o ícone PNG em .ico (build)
├── src/
│   ├── code_gen/
│   │   ├── __init__.py   # Metadados do pacote
│   │   ├── __main__.py   # CLI por argumentos e diálogo visual
│   │   ├── cli.py        # Seleção de planilha compartilhada (terminal)
│   │   ├── main.py       # Fluxo interativo completo (envio, rate limit, tqdm)
│   │   ├── core.py       # Algoritmo de sorteio e persistência
│   │   ├── io.py         # Leitura de planilhas e exportação de CSVs/Relatórios
│   │   └── runtime.py    # Resolução da raiz da aplicação
│   ├── delivery/         # Camada de envio de e-mails (SMTP e loop em lote)
│   │   ├── __init__.py
│   │   ├── sender.py     # Loop de envio em lote compartilhado (TUI/UI)
│   │   └── smtp.py       # Envio de e-mails HTML via SMTP
│   ├── gui/              # Interface gráfica PyQt
│   │   ├── __init__.py
│   │   ├── ui.py         # Importação, revisão e envio + verificação de update
│   │   └── resources.py  # Resolução de assets (.ui/.qss)
│   └── updater/          # Atualizador automático via releases do GitHub
│       ├── __init__.py
│       ├── version.py    # Comparação semântica de versões
│       ├── github.py     # Consulta à última release
│       ├── download.py   # Download do asset com progresso
│       ├── updater.py    # Worker QThread: check → download → apply_update
│       └── _build_config.py # Config estática do updater (sem credenciais)
└── tests/               # Testes unitários com pytest
```
