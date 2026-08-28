import pytest
from openpyxl import Workbook

from code_gen.io import (
    default_registry_path,
    default_report_path,
    read_spreadsheet,
    write_output_csv,
    write_report_csv,
)


def test_read_csv_semicolon(tmp_path):
    src = tmp_path / "entrada.csv"
    src.write_text("Nome;E-mail;Quantidade\nMaria;maria@ex.com;2\n", encoding="utf-8-sig")
    records, warnings = read_spreadsheet(src)
    assert records == [{"nome": "Maria", "email": "maria@ex.com", "quantidade": 2, "email_valido": True}]
    assert warnings == []


def test_read_csv_skips_invalid_rows(tmp_path):
    src = tmp_path / "entrada.csv"
    src.write_text(
        "nome,email,quantidade\n"
        "Ana,ana@ex.com,2\n"
        ",sem-email@ex.com,1\n"
        "Carlos,nao-e-email,1\n"
        "Bruno,bruno@ex.com,abc\n",
        encoding="utf-8",
    )
    records, warnings = read_spreadsheet(src)
    assert [record["nome"] for record in records] == ["Ana", "Carlos"]
    assert [record["email_valido"] for record in records] == [True, False]
    assert len(warnings) == 3


def test_read_csv_missing_columns(tmp_path):
    src = tmp_path / "entrada.csv"
    src.write_text("Nome;E-mail\nMaria;maria@ex.com\n", encoding="utf-8-sig")
    with pytest.raises(ValueError, match="quantidade"):
        read_spreadsheet(src)


def test_read_xlsx(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Nome", "E-mail", "Quantidade"])
    sheet.append(["João", "joao@ex.com", 3])
    src = tmp_path / "entrada.xlsx"
    workbook.save(src)
    records, warnings = read_spreadsheet(src)
    assert records == [{"nome": "João", "email": "joao@ex.com", "quantidade": 3, "email_valido": True}]
    assert warnings == []


def test_write_output_csv(tmp_path):
    out = tmp_path / "saida.csv"
    rows = [{"Nome": "Maria", "E-mail": "m@ex.com", "Códigos": "0001, 0002"}]
    write_output_csv(out, rows)
    text = out.read_text(encoding="utf-8-sig")
    assert "0001, 0002" in text
    assert text.splitlines()[0] == "Nome;E-mail;Códigos"


def test_default_registry_path_points_to_project_root():
    parts = default_registry_path().parts
    assert "Giveaways_Tools" in parts
    assert default_registry_path().name == "codigos_emitidos.json"


def test_write_report_csv_e_path(tmp_path):
    input_file = tmp_path / "participantes.csv"
    rep_path = default_report_path(input_file)
    assert rep_path.name.startswith("relatorio_envio_")
    assert rep_path.suffix == ".csv"

    rows = [{
        "Nome": "Maria",
        "E-mail": "m@ex.com",
        "Códigos": "0001",
        "Status": "Sucesso",
        "Data_Hora": "2026-08-28 10:00:00",
        "Detalhes": "Enviado com sucesso",
    }]
    write_report_csv(rep_path, rows)
    text = rep_path.read_text(encoding="utf-8-sig")
    assert "Nome;E-mail;Códigos;Status;Data_Hora;Detalhes" in text
    assert "Sucesso" in text
