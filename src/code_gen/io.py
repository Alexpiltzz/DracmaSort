"""Leitura de planilhas (xlsx/csv) e escrita do CSV de saída."""

import csv
import unicodedata
from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook

from .runtime import app_root

OUTPUT_FIELDS = ["Nome", "E-mail", "Códigos"]
REPORT_FIELDS = ["Nome", "E-mail", "Códigos", "Status", "Data_Hora", "Detalhes"]


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFD", str(value).strip().lower())
    return "".join(char for char in text if unicodedata.category(char) != "Mn")


def _map_columns(headers: list) -> dict[str, int | None]:
    columns: dict[str, int | None] = {"nome": None, "email": None, "quantidade": None}
    for index, header in enumerate(headers):
        key = _normalize(header)
        if key in {"nome", "name", "participante"}:
            columns["nome"] = index
        elif key in {"email", "e-mail", "correio"}:
            columns["email"] = index
        elif key in {"quantidade", "qtd", "qty", "numero", "n"}:
            columns["quantidade"] = index
    return columns


def _detect_delimiter(sample: str) -> str:
    return ";" if sample.count(";") > sample.count(",") else ","


def _read_csv_rows(path: Path) -> list[list[str]]:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            with path.open("r", encoding=encoding, newline="") as fh:
                sample = fh.read(4096)
                fh.seek(0)
                delimiter = _detect_delimiter(sample)
                return list(csv.reader(fh, delimiter=delimiter))
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Não foi possível ler o CSV {path.name}: encoding não reconhecido.")


def _read_xlsx_rows(path: Path) -> list[list]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook.active
        if sheet is None:
            raise ValueError(f"A planilha {path.name} não possui planilhas ativas.")
        return [list(row) for row in sheet.iter_rows(values_only=True)]
    finally:
        workbook.close()


def _parse_quantity(value) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        qty = int(value)
        if float(qty) == value and qty >= 1:
            return qty
        return None
    try:
        qty = int(str(value).strip())
    except ValueError:
        return None
    return qty if qty >= 1 else None


def is_valid_email(email: str) -> bool:
    return "@" in email and "." in email.split("@")[-1]


def read_spreadsheet(path: Path) -> tuple[list[dict], list[str]]:
    """Lê a planilha e devolve registros válidos e avisos das linhas ignoradas."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        rows = _read_xlsx_rows(path)
    elif suffix == ".csv":
        rows = _read_csv_rows(path)
    else:
        raise ValueError(f"Formato não suportado: {path.name}")

    if not rows:
        raise ValueError("A planilha está vazia.")

    indexes = _map_columns(rows[0])
    missing = [label for label, index in indexes.items() if index is None]
    if missing:
        raise ValueError(f"Colunas obrigatórias não encontradas: {', '.join(missing)}.")
    columns = {label: index for label, index in indexes.items() if index is not None}

    records = []
    warnings = []
    for line_no, row in enumerate(rows[1:], start=2):
        if not any(str(cell).strip() for cell in row):
            continue
        name = str(row[columns["nome"]]).strip()
        email = str(row[columns["email"]]).strip()
        quantity_text = row[columns["quantidade"]]
        quantity = _parse_quantity(quantity_text)
        if not name:
            warnings.append(f"Linha {line_no}: nome vazio, ignorada.")
            continue
        if quantity is None:
            warnings.append(f"Linha {line_no}: quantidade inválida ({quantity_text}), ignorada.")
            continue
        email_valid = is_valid_email(email)
        if not email_valid:
            warnings.append(
                f"Linha {line_no}: e-mail inválido ({email or 'vazio'}), mantido para revisão."
            )
        records.append(
            {
                "nome": name,
                "email": email,
                "quantidade": quantity,
                "email_valido": email_valid,
            }
        )
    return records, warnings


def write_output_csv(path: Path, rows: list[dict]) -> None:
    """Grava o CSV de saída com BOM e delimitador ';' para o Excel pt-BR."""
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_FIELDS, delimiter=";")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in OUTPUT_FIELDS})


def default_output_path(input_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(input_path).parent / f"codigos_sorteados_{timestamp}.csv"


def write_report_csv(path: Path, rows: list[dict]) -> None:
    """Grava o CSV de relatório de envio com BOM e delimitador ';'."""
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=REPORT_FIELDS, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def default_report_path(input_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(input_path).parent / f"relatorio_envio_{timestamp}.csv"


def default_registry_path() -> Path:
    return app_root() / "codigos_emitidos.json"
