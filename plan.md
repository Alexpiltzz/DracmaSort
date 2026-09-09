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

## Atualizador Automático via Releases do GitHub — implementado

> **Objetivo**: o executável (`DracmaSort.exe`) se auto-atualizar baixando a
> release mais recente publicada no GitHub (o mesmo fluxo manual de antes, agora
> embutido no app). **Implementado** em conjunto com o fluxo de publicação
> `python main_exe.py --release`.

### Contexto e restrições

- O repositório é **privado**, então a API do GitHub exige **autenticação**.
- O app é distribuído como **um único `.exe` (onefile)** em `dist/`, gerado com
  PyInstaller via `main_exe.py`.
- Releases com asset nomeado `DracmaSort.exe`.
- Sem biblioteca de HTTP dedicada — `urllib.request` da stdlib.

### Decisões de segurança (definidas na revisão)

- **Nenhum token é embutido no executável.** Empacotar o token via build
  (`_build_config.py`) colocaria a credencial em texto puro no bytecode — descartado.
- **Updater sem autenticação**: o repositório tornou-se **público**, então o
  updater consulta `GET /releases/latest` e baixa o asset anonimamente — **sem
  `GITHUB_TOKEN`, sem `.env.updater`, sem header `Authorization`**. A distribuição
  é apenas o `DracmaSort.exe`; o usuário final não fornece credencial alguma.
- **Token de publicação (escrita)**: `GITHUB_RELEASE_TOKEN` — variável de ambiente
  **somente no dev**, usada por `python main_exe.py --release` e `make_release.ps1`.
  Não chega ao pacote distribuído e não possui fallback para `git credential`
  nem `GITHUB_TOKEN`.
- **Isolamento SMTP**: `load_env_file(prefix=_PREFIX)` em `smtp.py` carrega apenas
  `GIVEAWAY_SMTP_*`, impedindo que credenciais de outras áreas entrem no
  `os.environ` via import do SMTP.

### Arquitetura final

```
src/updater/
├── __init__.py          # pacote importável
├── version.py           # versão local + comparação semântica (is_newer)
├── github.py            # GET /releases/latest em repo público (urllib, sem auth, timeout)
├── download.py          # download com progresso (sem auth)
├── updater.py           # UpdateWorker (QThread): check → download → apply_update
└── _build_config.py     # config estática SEM credenciais (repo + nome do asset)
```

- **Integração com a UI** (`src/gui/ui.py`): verificação automática no startup em
  background (`QThread`), diálogo de confirmação, barra de progresso no download e
  `apply_update()` no `closeEvent` (substitui o `.exe` e relança, com `.bak` de rollback).
- **Publicação**: `main_exe.py --release` cria a release + upload do asset; o mesmo
  fluxo existe em `make_release.ps1`.
- **Testes**: `tests/test_updater.py` (12 testes) — parsing de release, comparação
  semântica, caminho de download, 404, sem asset. Usam mock de `urlopen` (sem rede).

### Opções de autenticação — decisão registrada

| Opção | Situação |
|-------|----------|
| A. Token armazenado pelo usuário (QSettings) | ❌ descartado — criptografia fraca no Windows |
| B. Reusar `git credential fill` | ❌ descartado — dependente do credential manager |
| C. PAT read-only distribuído (`.env.updater`) | ✅ adotado em 2026 para repo privado; **substituído** depois que o repositório tornou-se público |
| D. Repo/release público (sem token) | ✅ adotado: `GET /releases/latest` e download do asset anônimos, sem `.env.updater`, distribuição só do `.exe` |
| Servidor intermediário / GitHub App | 🔲 fora do escopo atual; só se o repo voltar a ser privado |

## Status

| # | Item                           | Status                           |
|---|--------------------------------|----------------------------------|
| 1 | Remover `sync()` por keystroke  | 🔲 pendente de decisão/implementação |
| 2 | Salvar no `closeEvent`          | 🔲 pendente de decisão/implementação |
| 3 | Testes de persistência          | 🔲 pendente (comportamento já coberto indiretamente) |
| 4 | Documentar precedência          | 📄 coberto por este doc            |
| 5 | Atualizador automático (releases GitHub) | ✅ implementado (repo público, sem token) |
| 6 | `python main_exe.py --release`  | ✅ implementado (publica release + asset com `GITHUB_RELEASE_TOKEN` no dev) |
| 7 | Separação de credenciais (`.env` SMTP / publish env dev) | ✅ implementado — `.env.updater` removido |

> **Nota de decisão**: os itens 1–3 seguem pendentes (melhorias opcionais da
> revisão). O item 5 (atualizador automático) foi **implementado** — ver seção
> acima — e as decisões de segurança/autenticação estão registradas na tabela
> "Opções de autenticação". Com o repositório público, o updater é anônimo (opção
> D) e nenhum PAT circula no ambiente do usuário. Se o repo voltar a ser privado,
> revisitar a opção de servidor intermediário/GitHub App.