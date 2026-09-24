import json

import pytest
from openpyxl import Workbook

from code_gen import io as io_mod
from code_gen.io import (
    KEY_ALUNOS_RASTREADOS,
    KEY_ALUNOS_SORTEADOS,
    KEY_CODIGOS_EMITIDOS,
    KEY_CODIGOS_SORTEADOS,
    default_config_path,
    default_report_path,
    filter_new_students,
    migrate_legacy_config,
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


def test_read_csv_aliases_planilha_sistema(tmp_path):
    src = tmp_path / "entrada_sistema.csv"
    src.write_text(
        "Nome Completo;Responsável Financeiro;E-Mail do Responsável Financeiro;"
        "Quantidade;Materia;Periodo\n"
        "Maria Silva;Joao Pereira;responsavel1@ex.com;2;Mat;Manha\n"
        "Ana Melo;Carlos Melo;responsavel2@ex.com;1;Mat;Tarde\n",
        encoding="utf-8-sig",
    )
    records, warnings = read_spreadsheet(src)
    assert [record["aluno"] for record in records] == ["Maria Silva", "Ana Melo"]
    assert [record["nome"] for record in records] == ["Joao Pereira", "Carlos Melo"]
    assert [record["email"] for record in records] == [
        "responsavel1@ex.com",
        "responsavel2@ex.com",
    ]
    assert [record["quantidade"] for record in records] == [2, 1]
    assert warnings == []


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


def test_default_config_path_points_to_project_root():
    parts = default_config_path().parts
    assert "Giveaways_Tools" in parts
    assert default_config_path().name == "config.json"


def test_migrate_legacy_config_cria_config_e_remove_legados(tmp_path, monkeypatch):
    monkeypatch.setattr(io_mod, "app_root", lambda: tmp_path)
    (tmp_path / "codigos_emitidos.json").write_text("[2, 1, 2]", encoding="utf-8")
    (tmp_path / "alunos_rastreados.json").write_text('["ana melo"]', encoding="utf-8")
    (tmp_path / "codigos_sorteados.json").write_text("[7]", encoding="utf-8")
    (tmp_path / "alunos_sorteados.json").write_text('["Bia Lima"]', encoding="utf-8")

    config = tmp_path / "config.json"
    assert migrate_legacy_config(config) is True
    data = json.loads(config.read_text(encoding="utf-8"))
    assert data[KEY_CODIGOS_EMITIDOS] == [1, 2]
    assert data[KEY_ALUNOS_RASTREADOS] == ["ana melo"]
    assert data[KEY_CODIGOS_SORTEADOS] == [7]
    assert data[KEY_ALUNOS_SORTEADOS] == ["Bia Lima"]
    assert not (tmp_path / "codigos_emitidos.json").exists()
    assert not (tmp_path / "alunos_rastreados.json").exists()
    assert not (tmp_path / "codigos_sorteados.json").exists()
    assert not (tmp_path / "alunos_sorteados.json").exists()


def test_migrate_legacy_config_idempotente_e_nao_sobrescreve(tmp_path, monkeypatch):
    monkeypatch.setattr(io_mod, "app_root", lambda: tmp_path)
    (tmp_path / "codigos_emitidos.json").write_text("[3]", encoding="utf-8")
    config = tmp_path / "config.json"
    assert migrate_legacy_config(config) is True
    config.write_text(json.dumps({KEY_CODIGOS_EMITIDOS: [99]}), encoding="utf-8")
    assert migrate_legacy_config(config) is False
    data = json.loads(config.read_text(encoding="utf-8"))
    assert data[KEY_CODIGOS_EMITIDOS] == [99]


def test_migrate_legacy_config_sem_legados(tmp_path, monkeypatch):
    monkeypatch.setattr(io_mod, "app_root", lambda: tmp_path)
    config = tmp_path / "config.json"
    assert migrate_legacy_config(config) is True
    data = json.loads(config.read_text(encoding="utf-8"))
    assert data[KEY_CODIGOS_EMITIDOS] == []
    assert data[KEY_ALUNOS_RASTREADOS] == []
    assert data[KEY_CODIGOS_SORTEADOS] == []
    assert data[KEY_ALUNOS_SORTEADOS] == []


def test_migrate_legacy_config_preserva_acentos(tmp_path, monkeypatch):
    monkeypatch.setattr(io_mod, "app_root", lambda: tmp_path)
    (tmp_path / "alunos_sorteados.json").write_text('["Letícia"]', encoding="utf-8")
    config = tmp_path / "config.json"
    migrate_legacy_config(config)
    text = config.read_text(encoding="utf-8")
    assert "Letícia" in text
    assert "\\u00ed" not in text


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
