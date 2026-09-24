import json

from PyQt6.QtWidgets import QApplication

from code_gen.io import KEY_ALUNOS_SORTEADOS, KEY_CODIGOS_SORTEADOS
from gui.drawn_codes import (
    DrawnCodesDialog,
    parse_codes_input,
    parse_students_input,
    register_drawn_numbers,
    register_drawn_students,
)


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    assert isinstance(app, QApplication)
    return app


_APP: QApplication = _ensure_app()


def _dialog(tmp_path, known_students=None) -> DrawnCodesDialog:
    return DrawnCodesDialog(tmp_path / "config.json", known_students or set())


def _read_config(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_parse_codes_input_aceita_virgulas_espacos_e_novas_linhas():
    assert parse_codes_input("1, 15, 9999") == [1, 15, 9999]
    assert parse_codes_input("1;15\n42") == [1, 15, 42]
    assert parse_codes_input("  007 ") == [7]


def test_parse_codes_input_ignora_invalidos_e_fora_do_dominio():
    assert parse_codes_input("1, abc, -5, 10000, 0") == [1]


def test_register_drawn_numbers_persiste_e_acumula(tmp_path):
    path = tmp_path / "config.json"
    register_drawn_numbers(path, ["0001", "0042"], section=KEY_CODIGOS_SORTEADOS)
    assert _read_config(path)[KEY_CODIGOS_SORTEADOS] == [1, 42]
    register_drawn_numbers(path, ["0042", "100"], section=KEY_CODIGOS_SORTEADOS)
    assert set(_read_config(path)[KEY_CODIGOS_SORTEADOS]) == {1, 42, 100}


def test_dialog_carrega_codigos_existentes(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"codigos_sorteados": [2, 7]}', encoding="utf-8")
    dialog = _dialog(tmp_path)
    assert dialog.codes() == {2, 7}
    assert dialog._codes_section._list.count() == 2
    assert dialog._codes_section._list.item(0).text() == "0002"


def test_dialog_adiciona_codigos_manualmente(tmp_path):
    path = tmp_path / "config.json"
    dialog = _dialog(tmp_path)
    emitted: list[bool] = []
    dialog.sorteadosChanged.connect(lambda: emitted.append(True))
    dialog._codes_section._input.setText("3, 12")
    dialog._codes_section._add_manual()
    assert dialog.codes() == {3, 12}
    assert _read_config(path)[KEY_CODIGOS_SORTEADOS] == [3, 12]
    assert emitted == [True]


def test_dialog_remove_codigos_selecionados(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"codigos_sorteados": [1, 2, 3]}', encoding="utf-8")
    dialog = _dialog(tmp_path)
    dialog._codes_section._list.item(1).setSelected(True)
    dialog._codes_section._remove_selected()
    assert dialog.codes() == {1, 3}
    assert _read_config(path)[KEY_CODIGOS_SORTEADOS] == [1, 3]


def test_dialog_adicao_de_codigo_vazio_nao_altera(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"codigos_sorteados": [5]}', encoding="utf-8")
    dialog = _dialog(tmp_path)
    emitted: list[bool] = []
    dialog.sorteadosChanged.connect(lambda: emitted.append(True))
    dialog._codes_section._input.setText("abc")
    dialog._codes_section._add_manual()
    assert dialog.codes() == {5}
    assert emitted == []


def test_parse_students_input_devolve_apenas_nomes_da_base(tmp_path):
    conhecidos = {"Maria Silva", "João Costa"}
    assert parse_students_input("Maria Silva, joão costa", conhecidos) == [
        "Maria Silva",
        "joão costa",
    ]
    assert parse_students_input("Maria Silva, Nome Inexistente", conhecidos) == ["Maria Silva"]
    assert parse_students_input("", conhecidos) == []


def test_register_drawn_students_persiste_com_titulo(tmp_path):
    path = tmp_path / "config.json"
    register_drawn_students(path, ["maria silva"], section=KEY_ALUNOS_SORTEADOS)
    assert _read_config(path)[KEY_ALUNOS_SORTEADOS] == ["Maria Silva"]
    register_drawn_students(path, ["joão costa"], section=KEY_ALUNOS_SORTEADOS)
    assert set(_read_config(path)[KEY_ALUNOS_SORTEADOS]) == {"Maria Silva", "João Costa"}


def test_dialog_adiciona_aluno_valido(tmp_path):
    path = tmp_path / "config.json"
    dialog = _dialog(tmp_path, {"Maria Silva", "João Costa"})
    emitted: list[bool] = []
    dialog.sorteadosChanged.connect(lambda: emitted.append(True))
    dialog._students_section._input.setText("maria silva")
    dialog._students_section._add_manual()
    assert dialog.students() == {"Maria Silva"}
    assert _read_config(path)[KEY_ALUNOS_SORTEADOS] == ["Maria Silva"]
    assert emitted == [True]
    assert dialog._students_section._error_label.text() == ""


def test_dialog_rejeita_aluno_fora_da_base(tmp_path):
    path = tmp_path / "config.json"
    dialog = _dialog(tmp_path, {"Maria Silva"})
    emitted: list[bool] = []
    dialog.sorteadosChanged.connect(lambda: emitted.append(True))
    dialog._students_section._input.setText("Fulano Inexistente")
    dialog._students_section._add_manual()
    assert dialog.students() == set()
    assert "existe na base" in dialog._students_section._error_label.text()
    assert not path.exists()
    assert emitted == []


def test_dialog_remove_aluno_selecionado(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"alunos_sorteados": ["Maria Silva", "João Costa"]}', encoding="utf-8")
    dialog = _dialog(tmp_path, {"Maria Silva", "João Costa"})
    for index in range(dialog._students_section._list.count()):
        item = dialog._students_section._list.item(index)
        if item.text() == "Maria Silva":
            item.setSelected(True)
    dialog._students_section._remove_selected()
    assert dialog.students() == {"João Costa"}
    assert _read_config(path)[KEY_ALUNOS_SORTEADOS] == ["João Costa"]
