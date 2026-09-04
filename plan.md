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

## Status

| # | Item                           | Status                           |
|---|--------------------------------|----------------------------------|
| 1 | Remover `sync()` por keystroke  | 🔲 pendente de decisão/implementação |
| 2 | Salvar no `closeEvent`          | 🔲 pendente de decisão/implementação |
| 3 | Testes de persistência          | 🔲 pendente (comportamento já coberto indiretamente) |
| 4 | Documentar precedência          | 📄 coberto por este doc            |

> **Nota de decisão**: estes itens foram levantados na revisão como melhorias
> opcionais. A release atual (v0.2.1) inclui APENAS a persistência funcional
> (modelo de e-mail + SMTP via `QSettings`). A implementação dos itens acima
> ficou registrada aqui para verificação e decisão posteriores.