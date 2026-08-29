"""Interface interativa (TUI simples) que unifica o fluxo de sorteio e envio.

Orquestra: seleção da planilha -> leitura (io) -> geração dos códigos (core)
-> escrita do CSV de saída -> envio por e-mail (smtp).

Uso:
    uv run python -m code_gen.main [--arquivo caminho] [--teste]

Modos de envio:
    - padrão: envia um e-mail para cada participante com seus códigos;
    - --teste: envia um único e-mail (sem códigos) para o destinatário da
      configuração SMTP, útil para validar o pipeline sem disparar para todos.
    - sem GIVEAWAY_SMTP_PASS: executa em dry-run, apenas exibindo o conteúdo.
"""

import argparse
import getpass
import sys
import time
from email.mime.multipart import MIMEMultipart
from pathlib import Path

from tqdm import tqdm

from delivery.sender import send_all
from delivery.smtp import SmtpConfig, enviar_email, montar_mensagem_html

from .cli import resolve_input_path
from .core import CodeRegistry, NotEnoughCodesError, generate_codes
from .io import (
    default_output_path,
    default_registry_path,
    default_report_path,
    read_spreadsheet,
    write_output_csv,
    write_report_csv,
)


def _confirm(question: str, default_no: bool = True) -> bool:
    """Pergunta sim/não e devolve a resposta como bool."""
    prompt = f"{question} [{'s/N' if default_no else 'S/n'}]: "
    answer = input(prompt).strip().lower()
    if default_no:
        return answer in {"s", "sim", "y", "yes"}
    return answer not in {"n", "nao", "não", "no"}


def _prompt_credentials(config: SmtpConfig) -> SmtpConfig:
    """Solicita credenciais SMTP via CLI interativo."""
    print("\n--- Credenciais SMTP ---")
    login_prompt = f"Login SMTP [{config.login}]: " if config.login else "Login SMTP: "
    login_input = input(login_prompt).strip()
    login = login_input if login_input else config.login

    from_prompt = (
        f"De (Caixa Compartilhada) [{config.from_addr}]: "
        if config.from_addr
        else "De (Caixa Compartilhada): "
    )
    from_input = input(from_prompt).strip()
    from_addr = from_input if from_input else config.from_addr

    pass_prompt = (
        "Senha SMTP [pressione Enter para usar a senha do .env]: "
        if config.password
        else "Senha SMTP: "
    )
    password_input = getpass.getpass(pass_prompt).strip()
    password = password_input if password_input else config.password

    return SmtpConfig(
        host=config.host,
        port=config.port,
        login=login,
        password=password,
        from_addr=from_addr,
        to_addr=config.to_addr,
    )


def _print_rows(rows: list[dict]) -> None:
    for row in rows:
        print(f"  {row['Códigos']:<20} {row['Nome']:<24} {row['E-mail']}")


def _run_processamento(input_path: Path) -> list[dict] | None:
    """Lê a planilha, gera os códigos e grava o CSV. Devolve as linhas de saída."""
    try:
        records, warnings = read_spreadsheet(input_path)
    except ValueError as exc:
        print(f"Erro ao ler a planilha: {exc}")
        return None

    for warning in warnings:
        print(f"Aviso: {warning}")

    if not records:
        print("Nenhuma linha válida encontrada para processamento.")
        return None

    valid_records = [record for record in records if bool(record.get("email_valido", True))]
    if not valid_records:
        print("Nenhum e-mail válido encontrado para gerar códigos.")
        return None

    registry = CodeRegistry(default_registry_path())
    used_codes = registry.load()
    quantities = [record["quantidade"] for record in valid_records]

    try:
        batches = generate_codes(quantities, used_codes)
    except NotEnoughCodesError as exc:
        print(f"Erro: {exc}")
        return None

    rows = [
        {"Nome": record["nome"], "E-mail": record["email"], "Códigos": ", ".join(codes)}
        for record, codes in zip(valid_records, batches, strict=True)
    ]
    output_path = default_output_path(input_path)
    write_output_csv(output_path, rows)

    newly_used = {int(code) for codes in batches for code in codes}
    registry.save(used_codes | newly_used)

    print(f"\n{len(valid_records)} pessoas atendidas, {sum(quantities)} códigos gerados.")
    print(f"Saída: {output_path}")
    print(f"Registro atualizado: {registry.path}\n")
    print("Linhas geradas:")
    _print_rows(rows)
    print()
    return rows


def _run_envio(rows: list[dict], test_mode: bool, input_path: Path | None = None) -> int:
    """Envia os e-mails conforme o modo (teste / individual / dry-run)."""
    config = SmtpConfig.from_env()
    config = _prompt_credentials(config)

    if not config.password:
        print("Sem senha configurada — modo dry-run (nenhum envio real).")
        print("Conteúdo que seria enviado ao primeiro destinatário:\n")
        first = rows[0]
        msg = montar_mensagem_html(
            first["Nome"],
            config.from_addr,
            first["E-mail"],
            numeros=[first["Códigos"]],
        )
        print(msg.as_string())
        return 1

    if test_mode:
        msg = montar_mensagem_html("Teste", config.from_addr, config.to_addr)
        print(f"Modo teste: enviando e-mail de teste para {config.to_addr}...")
        rejeitados = enviar_email(config, msg)
        if rejeitados:
            print(f"Envios rejeitados: {rejeitados}")
            return 1
        print("E-mail de teste enviado com sucesso.")
        return 0

    total = len(rows)
    if not _confirm(f"Enviar {total} e-mail(s) para os participantes?"):
        print("Envio cancelado.")
        return 1

    print(f"\nIniciando envio de {total} e-mail(s)...")

    def _make_message(row: dict[str, str]) -> MIMEMultipart:
        return montar_mensagem_html(
            row["Nome"], config.from_addr, row["E-mail"], numeros=row["Códigos"]
        )

    def _log_row(index: int, report: dict[str, str]) -> None:
        if report["Status"] == "Sucesso":
            tqdm.write(f"  [{index + 1}/{total}] Enviado para {report['E-mail']}")
        else:
            tqdm.write(
                f"  [{index + 1}/{total}] {report['Status']} para "
                f"{report['E-mail']}: {report['Detalhes']}"
            )

    def _bump_progress(_current: int, _total: int) -> None:
        pbar.update(1)

    with tqdm(
        total=total,
        desc="Envio dos e-mails",
        unit="email",
        dynamic_ncols=True,
    ) as pbar:
        result = send_all(
            config,
            rows,
            simulate=False,
            make_message=_make_message,
            deliver=enviar_email,
            sleep_fn=time.sleep,
            on_row=_log_row,
            on_progress=_bump_progress,
            on_message=lambda text: tqdm.write(f"\n  {text}\n"),
        )

    if input_path and result.reports:
        report_path = default_report_path(input_path)
        write_report_csv(report_path, result.reports)
        print(f"\nRelatório de envio salvo em: {report_path}")

    if result.failures:
        print(f"\nConcluído com {result.failures} falha(s).")
        return 1
    print(f"\n{total} e-mail(s) enviados com sucesso.")
    return 0


def run(*, test_mode: bool = False, arquivo: str | None = None) -> int:
    """Executa o fluxo completo de sorteio + envio de forma interativa."""
    input_path = resolve_input_path(arquivo)
    if input_path is None:
        print("Nenhum arquivo selecionado. Abortando.")
        return 1

    rows = _run_processamento(input_path)
    if rows is None:
        return 1

    if not _confirm("Deseja prosseguir para o envio dos e-mails?", default_no=False):
        print("Encerrado. Nenhum e-mail enviado.")
        return 0

    return _run_envio(rows, test_mode=test_mode, input_path=input_path)


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada do CLI interativo, aceitando --arquivo e --teste."""
    parser = argparse.ArgumentParser(
        description="Fluxo interativo de sorteio com envio de e-mails."
    )
    parser.add_argument(
        "--arquivo",
        help="Caminho da planilha (.xlsx ou .csv). Se omitido, abre o seletor.",
    )
    parser.add_argument(
        "--teste",
        action="store_true",
        help="Envia apenas um e-mail de validação para o destinatário configurado.",
    )
    args = parser.parse_args(argv)
    return run(test_mode=args.teste, arquivo=args.arquivo)


if __name__ == "__main__":
    sys.exit(main())
