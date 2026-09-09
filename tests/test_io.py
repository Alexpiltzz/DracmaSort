import pytest
from openpyxl import Workbook

from code_gen.io import (
    default_registry_path,
    default_report_path,
    default_student_registry_path,
    filter_new_students,
    normalize_name,
    read_spreadsheet,
    write_output_csv,
    write_report_csv,
)


def test_read_csv_semicolon(tmp_path):
    src = tmp_path / "entrada.csv"
    src.write_text(
        "Aluno;Nome;E-mail;Quantidade\nMaria Silva;Maria;maria@ex.com;2\n",
        encoding="utf-8-sig",
    )
    records, warnings = read_spreadsheet(src)
    assert records == [
        {
            "aluno": "Maria Silva",
            "nome": "Maria",
            "email": "maria@ex.com",
            "quantidade": 2,
            "email_valido": True,
        }
    ]
    assert warnings == []


def test_read_csv_skips_invalid_rows(tmp_path):
    src = tmp_path / "entrada.csv"
    src.write_text(
        "Aluno,Nome,Email,Quantidade\n"
        "Ana Melo,Ana,ana@ex.com,2\n"
        ",SemNome,sem-email@ex.com,1\n"
        "Carlos Rocha,Carlos,nao-e-email,1\n"
        "Bruno Reis,Bruno,bruno@ex.com,abc\n",
        encoding="utf-8",
    )
    records, warnings = read_spreadsheet(src)
    assert [record["aluno"] for record in records] == ["Ana Melo", "Carlos Rocha"]
    assert [record["email_valido"] for record in records] == [True, False]
    assert len(warnings) == 3


def test_read_csv_missing_columns(tmp_path):
    src = tmp_path / "entrada.csv"
    src.write_text("Nome;E-mail;Quantidade\nMaria;maria@ex.com;1\n", encoding="utf-8-sig")
    with pytest.raises(ValueError, match="aluno"):
        read_spreadsheet(src)


def test_filter_new_students_filters_tracked():
    records = [
        {"aluno": "Ana Melo", "nome": "Ana"},
        {"aluno": "Carlos Rocha", "nome": "Carlos"},
    ]
    fresh, skipped = filter_new_students(records, {"ana melo"})
    assert [record["aluno"] for record in fresh] == ["Carlos Rocha"]
    assert skipped == ["Ana Melo"]


def test_normalize_name_sem_acentos_e_caixa():
    assert normalize_name("  José da Silva  ") == "jose da silva"


def test_read_xlsx(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Aluno", "Nome", "E-mail", "Quantidade"])
    sheet.append(["João Souza", "João", "joao@ex.com", 3])
    src = tmp_path / "entrada.xlsx"
    workbook.save(src)
    records, warnings = read_spreadsheet(src)
    assert records == [
        {
            "aluno": "João Souza",
            "nome": "João",
            "email": "joao@ex.com",
            "quantidade": 3,
            "email_valido": True,
        }
    ]
    assert warnings == []


def test_write_output_csv(tmp_path):
    out = tmp_path / "saida.csv"
    rows = [{"Aluno": "Maria", "Nome": "Maria", "E-mail": "m@ex.com", "Códigos": "0001, 0002"}]
    write_output_csv(out, rows)
    text = out.read_text(encoding="utf-8-sig")
    assert "0001, 0002" in text
    assert text.splitlines()[0] == "Aluno;Nome;E-mail;Códigos"


def test_default_registry_path_points_to_project_root():
    parts = default_registry_path().parts
    assert "Giveaways_Tools" in parts
    assert default_registry_path().name == "codigos_emitidos.json"


def test_default_student_registry_path_points_to_project_root():
    parts = default_student_registry_path().parts
    assert "Giveaways_Tools" in parts
    assert default_student_registry_path().name == "alunos_rastreados.json"


def test_write_report_csv_e_path(tmp_path):
    input_file = tmp_path / "participantes.csv"
    rep_path = default_report_path(input_file)
    assert rep_path.name.startswith("relatorio_envio_")
    assert rep_path.suffix == ".csv"

    rows = [
        {
            "Aluno": "Maria Silva",
            "Nome": "Maria",
            "E-mail": "m@ex.com",
            "Códigos": "0001",
            "Status": "Sucesso",
            "Data_Hora": "2026-08-28 10:00:00",
            "Detalhes": "Enviado com sucesso",
        }
    ]
    write_report_csv(rep_path, rows)
    text = rep_path.read_text(encoding="utf-8-sig")
    assert "Aluno;Nome;E-mail;Códigos;Status;Data_Hora;Detalhes" in text
    assert "Maria Silva" in text
