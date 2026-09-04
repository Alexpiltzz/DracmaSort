# Plano de Melhorias — Persistência de Configurações na UI

> Documento de acompanhamento do trabalho de persistência de preferências da
> interface gráfica (QSettings). Sua finalidade é registrar as recomendações
> levantadas na revisão e o status de cada uma, para verificação posterior.

## Contexto

A UI (`src/gui/ui.py`) passou a persistir via `QSettings`:

- **Modelo de e-mail**: `email/subject` e `email/body` (salvo a cada edição via `textChanged`).
- **Configuração SMTP**: `smtp/host`, `smtp/port`, `smtp/login` e `smtp/from`.
  **A senha NÃO é persistida** — carregada sempre do `.env` (decisão de segurança).

Storage nativo: registro do Windows (`HKCU`), config INI no Linux/macOS.

## Revisão — Apontamentos

### 1. `settings.sync()` a cada keystroke — mitigar

- **Onde**: `_save_message_template()` e `_save_smtp_config()`.
- **Problema**: `sync()` força flush no disco a cada tecla digitada. O
  `QSettings` já faz flush no destrutor e em intervalos periódicos; o `sync()`
  explícito por keystroke é redundante e gera I/O desnecessário.
- **Proposta**: manter o auto-save por `textChanged` (robustez contra fechamento
  abrupto) mas **remover o `sync()`** das rotinas de save, mantendo apenas um
  `sync()` único no `closeEvent` como garantia de flush final.

### 2. `closeEvent` não salva o estado final — adicionar rede de segurança

- **Problema**: o salvamento atual depende exclusivamente de sinais. Valores
  definidos programaticamente fora dos caminhos de sinal não são persistidos.
- **Proposta**: no `closeEvent`, chamar `_save_message_template()` e
  `_save_smtp_config()` antes de `event.accept()`. Em conjunto com o item 1,
  substitui o `sync()` por keystroke por um único flush no fechamento.

### 3. Falta teste de persistência — criar

- **Problema**: `tests/test_ui.py` cobre o fluxo existente, mas não valida o
  ciclo salvar/carregar do `QSettings`.
- **Proposta**: criar testes que montem um `QSettings` apontando para um arquivo
  INI temporário (via `QSettings.setDefaultFormat`/caminho customizado) e validem:
  - round-trip de `subject`/`body` (gravado → carregado);
  - round-trip de `host`/`port`/`login`/`from`;
  - prioridade: valor salvo > `.env` (fallback);
  - senha nunca persistida.
- **Nota**: como `MainWindow` usa `uic.loadUi`, o teste pode instanciar a janela
  com um `app` QApplication fixture (padrão já presente em `tests/test_ui.py`).

### 4. Duas fontes de verdade (`.env` vs `QSettings`) — documentar

- **Situação atual**: `.env` guarda credenciais SMTP (incl. senha); `QSettings`
  guarda preferências da UI. É a arquitetura correta para o requisito de segurança.
- **Proposta**: **nada a implementar agora**. Apenas garantir que a precedência
  funcione: `QSettings` (valor salvo na UI) > `.env` (fallback). Idealmente
  expressar esta regra em um teste (item 3).

## Recomendações (opcionais, fora do escopo atual)

- **Persistir `to_addr` (destinatário do teste)** se fizer sentido no fluxo —
  hoje não é persistido (apenas do `.env`).
- **Extrair `_app_settings()` para constante de módulo** para evitar recriar o
  objeto `QSettings` a cada chamada (clareza, ganho marginal).

## Atualizador Automático via Releases do GitHub — proposta

> **Objetivo**: o executável (`DracmaSort.exe`) poder se auto-atualizar baixando a
> release mais recente publicada no GitHub (o mesmo fluxo manual que fazemos hoje
> via `gh`/API REST, só que embutido no app).

### Contexto e restrições

- O repositório é **privado**, então a API do GitHub exige **autenticação** —
  ao contrário de projetos públicos onde apenas `GET /releases/latest` resolve.
- O app é distribuído como **um único `.exe` (onefile)** em `dist/`, gerado com
  PyInstaller via `main_exe.py`.
- As releases já são criadas com asset nomeado `DracmaSort.exe` (v0.2.0, v0.2.1).
- Dependências atuais (ver `pyproject.toml`): PyQt6, Markdown, openpyxl, tqdm —
  **sem** biblioteca de HTTP dedicada. Usar `urllib.request` da stdlib evita nova
  dependência.

### Fluxo proposto

1. **Na inicialização** (ou num botão "Verificar atualizações" na aba de config),
   o app consulta a versão corrente (`app.__version__`, gerada a partir do
   `pyproject.toml` ou embutida no build).
2. **Consulta à última release** — `GET /repos/{owner}/{repo}/releases/latest` com
   header `Authorization: Bearer <token>` (ver autenticação abaixo). A resposta
   expõe `tag_name` (ex.: `v0.2.2`) e `assets[].browser_download_url` para o `.exe`.
3. **Comparação semântica**: se `tag_name` > versão local, oferece atualizar via
   `QMessageBox` com o changelog do corpo da release.
4. **Download** do asset em `tempfile.gettempdir()` (ex.: `DracmaSort_v0.2.2.exe`)
   com barra de progresso (reusar `QProgressDialog`).
5. **Substituição do executável**: como o `.exe` em execução está bloqueado no
   Windows, baixar com nome temporário e, ao fechar o app (`closeEvent`), copiar
   por cima do atual e relançar (ex.: `subprocess.Popen([novo_exe])` + `sys.exit`).
6. **Rollback**: manter o `.exe` anterior como `DracmaSort.exe.bak` por uma versão.

### Autenticação (ponto crítico no repositório privado)

Opções possíveis, em ordem de complexidade:

| Opção | Como funciona | Prós | Contras |
|-------|---------------|------|---------|
| **A. Token armazenado pelo usuário** | Débito configurado na UI (`QSettings`, mesmo padrão de login/from já usado), campo "Token GitHub" | Simples, sem infra | Token com escopo `repo` vaza para `QSettings` (criptografia fraca no Windows); rotação manual |
| **B. Chave do usuário já presente** | Reusar o `git credential fill` em runtime não é viável (dependente do credential manager instalado) | — | Não reproduzível fora de máquinas com GCM |
| **C. Token de deploy (recomendado)** | Criar um **PAT apenas-leitura de releases** (escopo `repo:read`/`public_repo`) com permissão mínima, embutido no build via variável de ambiente do PyInstaller | Escopo mínimo, ideal para auto-update | Token pode vazar no `.exe` (extração simples com binwalk); deve ter expiração curta e ser revogável |
| **D. App público ou release pública** | Tornar só a aba de "Releases" pública, ou o repo inteiro | Elimina autenticação (anônimo) | Muda a política de visibilidade — decisão de negócio |

**Recomendação**: começar pela opção **C** para o *updater* consultar releases
(leitura), com token lido de variável de ambiente (`GITHUB_TOKEN`) injetada no
build via `build_main_ui.ps1`, e **fallback para a opção D** se o repo puder ser
público — aí o updater não precisa de token algum.

### Estrutura de código proposta (novo módulo)

```
src/updater/
├── __init__.py          # torna o pacote importável
├── version.py           # NÚCLEO: versão local (de __version__) + igual/maior/menor semântico
├── github.py            # NÚCLEO: GET /releases/latest (urllib, header Bearer, timeout)
├── download.py          # download com progresso (chunks, relatório de bytes)
└── patch.py             # substituição do .exe + relaunch (Windows)
```

- **Responsabilidades únicas, testáveis**: `version.py` e `github.py` são
  testáveis sem GUI (parse de JSON mockado); `download.py` e `patch.py` ficam
  finos.
- **Integração com a UI**: botão "Verificar atualizações" + diálogo de progresso
  numa `QThread` (mesmo padrão do `EmailWorker` existente) para não travar a janela.
- **Testes** (alinhados às regras do projeto):
  - comparação semântica (v0.2.1 vs v0.2.2, pré-release, `v` prefixo);
  - parsing da resposta da API (assets, tag_name);
  - download para arquivo temporário e fallback de URL.

### Passos de implementação sugeridos (quando aprovado)

1. Criar `src/updater/version.py` com comparação semântica + testes.
2. Criar `src/updater/github.py` com chamada anônima (opção D) e depois o header
   Bearer (opção C).
3. Criar `src/updater/download.py` + `patch.py`.
4. Adicionar botão/verificação na `MainWindow` e diálogo de progresso.
5. Injetar `GITHUB_TOKEN`/versão no build via `build_main_ui.ps1` e `main_exe.py`.
6. Release de teste: publicar `v0.2.2`, verificar o auto-update em máquina limpa.

> **Decisão pendente**: qual opção de autenticação (A/C/D) — decisão de negócio e
> segurança que cabe ao mantenedor.

## Status

| # | Item                           | Status                           |
|---|--------------------------------|----------------------------------|
| 1 | Remover `sync()` por keystroke  | 🔲 pendente de decisão/implementação |
| 2 | Salvar no `closeEvent`          | 🔲 pendente de decisão/implementação |
| 3 | Testes de persistência          | 🔲 pendente (comportamento já coberto indiretamente) |
| 4 | Documentar precedência          | 📄 coberto por este doc            |
| 5 | Atualizador automático (releases GitHub) | 🔲 proposta registrada; decisão de autenticação pendente (A/C/D) |

> **Nota de decisão**: os itens 1–3 foram levantados na revisão como melhorias
> opcionais. A release atual (v0.2.1) inclui APENAS a persistência funcional
> (modelo de e-mail + SMTP via `QSettings`). O item 5 (atualizador automático)
> está registrado como proposta de arquitetura para avaliação do mantenedor.
> A implementação dos itens acima ficou registrada aqui para verificação e
> decisão posteriores.