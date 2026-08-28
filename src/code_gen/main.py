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

import getpass
import random
import sys
import time
from datetime import datetime
from pathlib import Path

from tqdm import tqdm

from .__main__ import _resolve_input, default_registry_path
from .core import CodeRegistry, NotEnoughCodesError, generate_codes
from .io import (
    default_output_path,
    default_report_path,
    read_spreadsheet,
    write_output_csv,
    write_report_csv,
)
from .smtp import SmtpConfig, enviar_email, montar_mensagem_html

DELAY_PER_EMAIL_MIN = 7.0
DELAY_PER_EMAIL_MAX = 10.0
BATCH_SIZE = 50
BATCH_PAUSE_MIN = 300.0
BATCH_PAUSE_MAX = 600.0



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

    registry = CodeRegistry(default_registry_path())
    used_codes = registry.load()
    quantities = [record["quantidade"] for record in records]

    try:
        batches = generate_codes(quantities, used_codes)
    except NotEnoughCodesError as exc:
        print(f"Erro: {exc}")
        return None

    rows = [
        {"Nome": record["nome"], "E-mail": record["email"], "Códigos": ", ".join(codes)}
        for record, codes in zip(records, batches, strict=True)
    ]
    output_path = default_output_path(input_path)
    write_output_csv(output_path, rows)

    newly_used = {int(code) for codes in batches for code in codes}
    registry.save(used_codes | newly_used)

    print(f"\n{len(records)} pessoas atendidas, {sum(quantities)} códigos gerados.")
    print(f"Saída: {output_path}")
    print(f"Registro atualizado: {registry.path}\n")
    print("Linhas geradas:")
    _print_rows(rows)
    print()
    return rows


def _run_envio(
    rows: list[dict], test_mode: bool, input_path: Path | None = None
) -> int:
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

    falhas = 0
    report_rows = []

    print(f"\nIniciando envio de {total} e-mail(s)...")
    with tqdm(
        total=total,
        desc="Envio dos e-mails",
        unit="email",
        dynamic_ncols=True,
    ) as pbar:
        for index, row in enumerate(rows, start=1):
            to_addr = row["E-mail"]
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            msg = montar_mensagem_html(
                row["Nome"], config.from_addr, to_addr, numeros=row["Códigos"]
            )
            try:
                rejeitados = enviar_email(config, msg)
                if rejeitados:
                    tqdm.write(f"  [{index}/{total}] Rejeitado para {to_addr}: {rejeitados}")
                    falhas += 1
                    report_rows.append({
                        "Nome": row["Nome"],
                        "E-mail": to_addr,
                        "Códigos": row["Códigos"],
                        "Status": "Rejeitado",
                        "Data_Hora": now_str,
                        "Detalhes": f"Rejeitados: {rejeitados}",
                    })
                else:
                    tqdm.write(f"  [{index}/{total}] Enviado para {to_addr}")
                    report_rows.append({
                        "Nome": row["Nome"],
                        "E-mail": to_addr,
                        "Códigos": row["Códigos"],
                        "Status": "Sucesso",
                        "Data_Hora": now_str,
                        "Detalhes": "Enviado com sucesso",
                    })
            except Exception as exc:  # noqa: BLE001 - qualquer falha não interrompe o lote
                tqdm.write(f"  [{index}/{total}] Falha para {to_addr}: {exc}")
                falhas += 1
                report_rows.append({
                    "Nome": row["Nome"],
                    "E-mail": to_addr,
                    "Códigos": row["Códigos"],
                    "Status": "Falha",
                    "Data_Hora": now_str,
                    "Detalhes": str(exc),
                })

            pbar.update(1)

            if index < total:
                if index % BATCH_SIZE == 0:
                    pause_sec = random.uniform(BATCH_PAUSE_MIN, BATCH_PAUSE_MAX)
                    pause_min = pause_sec / 60.0
                    tqdm.write(
                        f"\n  [Pausa de Segurança] {index} e-mails enviados. "
                        f"Aguardando {pause_min:.1f} minutos ({int(pause_sec)}s) "
                        f"para prevenir bloqueios SMTP/anti-spam...\n"
                    )
                    time.sleep(pause_sec)
                else:
                    delay = random.uniform(DELAY_PER_EMAIL_MIN, DELAY_PER_EMAIL_MAX)
                    time.sleep(delay)



    if input_path and report_rows:
        report_path = default_report_path(input_path)
        write_report_csv(report_path, report_rows)
        print(f"\nRelatório de envio salvo em: {report_path}")

    if falhas:
        print(f"\nConcluído com {falhas} falha(s).")
        return 1
    print(f"\n{total} e-mail(s) enviados com sucesso.")
    return 0


def run(*, test_mode: bool = False, arquivo: str | None = None) -> int:
    """Executa o fluxo completo de sorteio + envio de forma interativa."""
    input_path = _resolve_input(arquivo)
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
    arquivo = None
    test_mode = False
    for arg in argv or sys.argv[1:]:
        if arg == "--teste":
            test_mode = True
        elif arg.startswith("--arquivo="):
            arquivo = arg.split("=", 1)[1]
        elif arg == "--arquivo":
            print("Uso: --arquivo=<caminho> (use '=' antes do caminho).")
            return 2
    return run(test_mode=test_mode, arquivo=arquivo)


if __name__ == "__main__":
    sys.exit(main())
