import json

import pytest
from openpyxl import Workbook

from code_gen import io as io_mod
from code_gen.io import (
    KEY_ALUNOS_RASTREADOS,
    KEY_ALUNOS_SORTEADOS,
    KEY_CODIGOS_EMITIDOS,
    KEY_CODIGOS_SORTEADOS,
    KEY_REPORTS_DIR,
    configured_reports_dir,
    confirmed_sent_codes,
    confirmed_sent_students,
    default_config_path,
    default_report_path,
    default_reports_dir,
    filter_new_students,
    migrate_legacy_config,
    normalize_name,
    read_spreadsheet,
    set_reports_dir,
    unify_reports,
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


def test_write_report_csv_e_path(tmp_path, monkeypatch):
    monkeypatch.setattr(io_mod, "default_reports_dir", lambda: tmp_path)
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


def _linha_report(aluno: str, codigo: str, status: str = "Sucesso") -> dict:
    return {
        "Aluno": aluno,
        "Nome": aluno.split()[0],
        "E-mail": f"{aluno.split()[0].lower()}@ex.com",
        "Códigos": codigo,
        "Status": status,
        "Data_Hora": "2026-08-28 10:00:00",
        "Detalhes": "ok",
    }


def test_unify_reports_junta_todos_os_relatorios(tmp_path):
    (tmp_path / "relatorio_envio_20260831_100000.csv").write_text("", encoding="utf-8")
    for idx in (1, 2):
        rep = tmp_path / f"relatorio_envio_2026090{idx}_100000.csv"
        write_report_csv(rep, [_linha_report(f"Aluno {idx}", f"000{idx}")])

    saida = unify_reports(tmp_path)
    assert saida is not None
    assert saida.name.startswith("relatorio_envio_unificado_")
    text = saida.read_text(encoding="utf-8-sig")
    assert "Aluno 1" in text
    assert "Aluno 2" in text


def test_unify_reports_sem_relatorios_devolve_none(tmp_path):
    assert unify_reports(tmp_path) is None


def test_unify_reports_ignora_unificado_anterior(tmp_path):
    anterior = tmp_path / "relatorio_envio_unificado_20260924_110218.csv"
    write_report_csv(anterior, [_linha_report("Repetido", "0999")])
    write_report_csv(
        tmp_path / "relatorio_envio_20260901_100000.csv",
        [_linha_report("Novo", "1001")],
    )

    saida = unify_reports(tmp_path)
    assert saida is not None
    text = saida.read_text(encoding="utf-8-sig")
    assert "Novo" in text
    assert "Repetido" not in text


def test_unify_reports_padrao_usa_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(io_mod, "app_root", lambda: tmp_path)
    cache = tmp_path / "cache"
    cache.mkdir()
    write_report_csv(
        cache / "relatorio_envio_20260901_100000.csv", [_linha_report("Maria", "0007")]
    )

    saida = unify_reports()
    assert saida is not None
    assert saida.parent == cache
    assert "Maria;Maria" in saida.read_text(encoding="utf-8-sig")


def _config_reports_dir(tmp_path, monkeypatch, valor):
    monkeypatch.setattr(io_mod, "app_root", lambda: tmp_path)
    config = default_config_path()
    config.write_text(
        json.dumps({"codigos_emitidos": [], KEY_REPORTS_DIR: valor}),
        encoding="utf-8",
    )


def test_default_reports_dir_usa_configurada(tmp_path, monkeypatch):
    pasta = tmp_path / "pasta_relatorios"
    pasta.mkdir()
    _config_reports_dir(tmp_path, monkeypatch, str(pasta))

    assert default_reports_dir() == pasta
    assert configured_reports_dir() == pasta


def test_default_reports_dir_ignora_configurada_invalida(tmp_path, monkeypatch):
    _config_reports_dir(tmp_path, monkeypatch, str(tmp_path / "inexistente"))

    assert configured_reports_dir() is None
    assert default_reports_dir() == tmp_path


def test_default_reports_dir_fallback_ordem(tmp_path, monkeypatch):
    monkeypatch.setattr(io_mod, "app_root", lambda: tmp_path)
    enviados = tmp_path / "enviados"
    enviados.mkdir()

    assert default_reports_dir() == enviados


def test_default_reports_dir_fallback_raiz(tmp_path, monkeypatch):
    monkeypatch.setattr(io_mod, "app_root", lambda: tmp_path)

    assert default_reports_dir() == tmp_path


def test_set_reports_dir_persiste_e_cria(tmp_path, monkeypatch):
    monkeypatch.setattr(io_mod, "app_root", lambda: tmp_path)
    pasta = tmp_path / "relatorios" / "novos"
    set_reports_dir(pasta)

    assert pasta.exists()
    assert configured_reports_dir() == pasta
    data = json.loads(default_config_path().read_text(encoding="utf-8"))
    assert data[KEY_REPORTS_DIR] == str(pasta)


def test_set_reports_dir_preserva_secoes(tmp_path, monkeypatch):
    monkeypatch.setattr(io_mod, "app_root", lambda: tmp_path)
    default_config_path().write_text(
        json.dumps({"alunos_sorteados": ["Ana"]}),
        encoding="utf-8",
    )

    set_reports_dir(tmp_path / "novos")

    data = json.loads(default_config_path().read_text(encoding="utf-8"))
    assert data["alunos_sorteados"] == ["Ana"]
    assert data[KEY_REPORTS_DIR] == str(tmp_path / "novos")


def test_confirmed_sent_students_sem_relatorio(tmp_path, monkeypatch):
    monkeypatch.setattr(io_mod, "latest_unified_report_path", lambda: None)

    assert confirmed_sent_students() == set()


def test_confirmed_sent_students_filtra_status(tmp_path, monkeypatch):
    unificado = tmp_path / "relatorio_envio_unificado_20260925_120000.csv"
    write_report_csv(
        unificado,
        [
            _linha_report("Ana Melo", "1001"),
            _linha_report("Bia Reis", "1002", status="Falha ao enviar"),
        ],
    )
    monkeypatch.setattr(io_mod, "latest_unified_report_path", lambda: unificado)

    assert confirmed_sent_students() == {"ana melo"}


def test_confirmed_sent_students_path_explicito(tmp_path):
    unificado = tmp_path / "relatorio_envio_unificado_20260925_120000.csv"
    write_report_csv(unificado, [_linha_report("Carlos Souza", "1003")])

    assert confirmed_sent_students(unificado) == {"carlos souza"}


def test_confirmed_sent_codes_sem_relatorio(tmp_path, monkeypatch):
    monkeypatch.setattr(io_mod, "latest_unified_report_path", lambda: None)

    assert confirmed_sent_codes() == set()


def test_confirmed_sent_codes_filtra_status(tmp_path, monkeypatch):
    unificado = tmp_path / "relatorio_envio_unificado_20260925_120000.csv"
    write_report_csv(
        unificado,
        [
            _linha_report("Ana Melo", "1001"),
            _linha_report("Bia Reis", "1002", status="Falha ao enviar"),
        ],
    )
    monkeypatch.setattr(io_mod, "latest_unified_report_path", lambda: unificado)

    assert confirmed_sent_codes() == {1001}


def test_confirmed_sent_codes_path_explicito(tmp_path):
    unificado = tmp_path / "relatorio_envio_unificado_20260925_120000.csv"
    write_report_csv(unificado, [_linha_report("Carlos Souza", "1003")])

    assert confirmed_sent_codes(unificado) == {1003}
