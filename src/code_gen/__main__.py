"""Interface de linha de comando do gerador de códigos."""

import argparse
import sys
from pathlib import Path

from .cli import resolve_input_path
from .core import CodeRegistry, NotEnoughCodesError, generate_codes
from .io import (
    default_output_path,
    default_registry_path,
    read_spreadsheet,
    write_output_csv,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gera códigos únicos de sorteio a partir de uma planilha."
    )
    parser.add_argument(
        "--arquivo",
        help="Caminho da planilha (.xlsx ou .csv). Se omitido, abre o seletor de arquivos.",
    )
    parser.add_argument(
        "--saida",
        help=(
            "Caminho do CSV de saída. Padrão: codigos_sorteados_<data>_<hora>.csv "
            "na pasta da planilha."
        ),
    )
    parser.add_argument(
        "--registro",
        help=(
            "Caminho do registro de códigos usados. Padrão: codigos_emitidos.json "
            "na raiz do projeto."
        ),
    )
    args = parser.parse_args(argv)

    input_path = resolve_input_path(args.arquivo)
    if input_path is None:
        print("Nenhum arquivo selecionado. Abortando.")
        return 1

    registry_path = Path(args.registro) if args.registro else default_registry_path()

    try:
        records, warnings = read_spreadsheet(input_path)
    except ValueError as exc:
        print(f"Erro ao ler a planilha: {exc}")
        return 1

    for warning in warnings:
        print(f"Aviso: {warning}")

    if not records:
        print("Nenhuma linha válida encontrada para processamento.")
        return 1

    registry = CodeRegistry(registry_path)
    used_codes = registry.load()
    quantities = [record["quantidade"] for record in records]

    try:
        batches = generate_codes(quantities, used_codes)
    except NotEnoughCodesError as exc:
        print(f"Erro: {exc}")
        return 1

    rows = [
        {"Nome": record["nome"], "E-mail": record["email"], "Códigos": ", ".join(codes)}
        for record, codes in zip(records, batches, strict=True)
    ]
    output_path = Path(args.saida) if args.saida else default_output_path(input_path)
    write_output_csv(output_path, rows)

    newly_used = {int(code) for codes in batches for code in codes}
    registry.save(used_codes | newly_used)

    print(f"{len(records)} pessoas atendidas, {sum(quantities)} códigos gerados.")
    print(f"Saída: {output_path}")
    print(f"Registro atualizado: {registry_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
