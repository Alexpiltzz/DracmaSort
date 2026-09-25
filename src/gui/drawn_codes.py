"""Dialog para consultar e registrar sorteados (códigos e alunos).

Códigos e alunos sorteados vivem em ``config.json`` nas seções
``codigos_sorteados`` e ``alunos_sorteados``. Edições feitas aqui valem também
para os sorteios futuros.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from code_gen.core import (
    MAX_CODE,
    MIN_CODE,
    CodeRegistry,
    StudentRegistry,
    format_code,
    smart_title_case,
)
from code_gen.docx_export import generate_draw_report_docx
from code_gen.io import (
    KEY_ALUNOS_SORTEADOS,
    KEY_CODIGOS_SORTEADOS,
    latest_unified_report_path,
    normalize_name,
    read_unified_pairs,
)


def parse_codes_input(text: str) -> list[int]:
    """Extrai números válidos (1..9999) de uma entrada livre de códigos."""
    codes: list[int] = []
    for token in text.replace(";", ",").replace("\n", ",").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            number = int(token)
        except ValueError:
            continue
        if MIN_CODE <= number <= MAX_CODE:
            codes.append(number)
    return codes


def parse_students_input(text: str, known: set[str]) -> list[str]:
    """Valida nomes livremente digitados contra a base e devolve os existentes."""
    valid: list[str] = []
    known_normalized = {normalize_name(name) for name in known}
    for token in text.replace(",", "\n").split("\n"):
        token = token.strip()
        if not token:
            continue
        if normalize_name(token) in known_normalized:
            valid.append(token)
    return valid


def register_drawn_numbers(
    path: Path,
    winners: list[str] | list[int],
    section: str | None = None,
) -> set[int]:
    """Persiste códigos sorteados no registro e devolve o conjunto atualizado."""
    registry = CodeRegistry(path, section=section)
    drawn = registry.load()
    drawn |= {int(code) for code in winners}
    registry.save(drawn)
    return drawn


def register_drawn_students(
    path: Path,
    names: list[str] | set[str],
    section: str | None = None,
) -> set[str]:
    """Persiste alunos sorteados no registro e devolve o conjunto atualizado."""
    registry = StudentRegistry(path, section=section)
    drawn = registry.load()
    drawn |= {smart_title_case(name) for name in names}
    registry.save(drawn)
    return drawn


class _SorteadosSection(QWidget):
    """Aba base do dialog: lista, adição manual e remoção."""

    def __init__(self, title: str, hint: str) -> None:
        super().__init__()
        self._title = title
        root = QVBoxLayout(self)

        hint_label = QLabel(hint)
        hint_label.setWordWrap(True)
        root.addWidget(hint_label)

        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        root.addWidget(self._list)

        add_row = QHBoxLayout()
        self._input = QLineEdit()
        add_row.addWidget(self._input, 1)
        self._add_button = QPushButton("Adicionar")
        self._add_button.clicked.connect(self._add_manual)
        self._input.returnPressed.connect(self._add_manual)
        add_row.addWidget(self._add_button)
        root.addLayout(add_row)

        self._error_label = QLabel("")
        self._error_label.setWordWrap(True)
        root.addWidget(self._error_label)

        self._remove_button = QPushButton("Remover selecionados")
        self._remove_button.clicked.connect(self._remove_selected)
        root.addWidget(self._remove_button)

        self._title_label = QLabel()
        root.addWidget(self._title_label)

    def _refresh(self) -> None:
        self._list.clear()
        for item in self._items():
            self._list.addItem(item)
        self._title_label.setText(f"{len(self._items())} registrado(s)")

    def _set_error(self, message: str) -> None:
        self._error_label.setText(message)

    def _items(self) -> list[str]:
        raise NotImplementedError

    def _add_manual(self) -> None:
        raise NotImplementedError

    def _remove_selected(self) -> None:
        raise NotImplementedError


class _CodesSection(_SorteadosSection):
    def __init__(self, parent: DrawnCodesDialog, config_path: Path) -> None:
        super().__init__(
            "Códigos",
            "Códigos já sorteados. Use vírgulas ou espaços para separar números.",
        )
        self._parent = parent
        self._registry = CodeRegistry(config_path, section=KEY_CODIGOS_SORTEADOS)
        self._codes = self._registry.load()
        self._input.setPlaceholderText("Digite códigos: 0001, 42, 9999")
        self._refresh()

    def _items(self) -> list[str]:
        return [format_code(code) for code in sorted(self._codes)]

    def _add_manual(self) -> None:
        numbers = parse_codes_input(self._input.text())
        if not numbers:
            return
        self._input.clear()
        self._set_error("")
        self._codes.update(numbers)
        self._parent._save(self)

    def _remove_selected(self) -> None:
        rows = [index.row() for index in self._list.selectedIndexes()]
        if not rows:
            return
        ordered = sorted(self._codes)
        for row in reversed(rows):
            ordered.pop(row)
        self._codes = set(ordered)
        self._parent._save(self)


class _StudentsSection(_SorteadosSection):
    def __init__(
        self,
        parent: DrawnCodesDialog,
        config_path: Path,
        known_students: set[str],
    ) -> None:
        super().__init__(
            "Alunos",
            "Alunos já sorteados. Digite um nome existente na base "
            "e confirme na lista para selecionar.",
        )
        self._parent = parent
        self._registry = StudentRegistry(config_path, section=KEY_ALUNOS_SORTEADOS)
        self._students = self._registry.load()
        self._known = known_students

        completer = QCompleter(sorted(known_students), self._input)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._input.setCompleter(completer)
        self._input.setPlaceholderText("Digite o nome do aluno...")

        self._refresh()

    def _items(self) -> list[str]:
        return [smart_title_case(name) for name in sorted(self._students)]

    def _add_manual(self) -> None:
        text = self._input.text()
        valid = parse_students_input(text, self._known)
        if not valid:
            self._set_error("Nenhum nome digitado existe na base de dados.")
            return
        self._input.clear()
        self._set_error("")
        self._students |= {smart_title_case(name) for name in valid}
        self._parent._save(self)

    def _remove_selected(self) -> None:
        rows = [index.row() for index in self._list.selectedIndexes()]
        if not rows:
            return
        ordered = sorted(self._students)
        for row in reversed(rows):
            ordered.pop(row)
        self._students = set(ordered)
        self._parent._save(self)


class DrawnCodesDialog(QDialog):
    """Janela para ver e editar os sorteados (códigos e alunos)."""

    sorteadosChanged = pyqtSignal()

    def __init__(
        self,
        config_path: Path,
        known_students: set[str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sorteados")
        self.setModal(True)
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)
        tabs = QTabWidget(self)

        self._codes_section = _CodesSection(self, config_path)
        tabs.addTab(self._codes_section, "Códigos")

        self._students_section = _StudentsSection(self, config_path, known_students or set())
        tabs.addTab(self._students_section, "Alunos")

        root.addWidget(tabs)

        export_row = QHBoxLayout()
        self.export_docx_button = QPushButton("📄 Exportar Ata (.docx)")
        self.export_docx_button.clicked.connect(self._export_docx_ata)
        export_row.addWidget(self.export_docx_button)
        export_row.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        export_row.addWidget(buttons)
        root.addLayout(export_row)

    def _export_docx_ata(self) -> None:
        students = self.students()
        codes = self.codes()
        if not students and not codes:
            QMessageBox.information(
                self, "Nenhum sorteado", "Não há alunos ou códigos registrados para exportar a ata."
            )
            return

        unificado = latest_unified_report_path()
        pares: dict[int, str] = {}
        if unificado is not None:
            try:
                pares = read_unified_pairs(unificado)
            except Exception:  # noqa: BLE001
                pares = {}

        records: list[dict[str, str]] = []
        if students:
            for name in sorted(students):
                # encontrar código vinculado se existir
                matched_codes = [
                    format_code(c)
                    for c, aluno in pares.items()
                    if normalize_name(aluno) == normalize_name(name)
                ]
                records.append(
                    {
                        "aluno": name,
                        "email": "-",
                        "codigo": ", ".join(matched_codes) if matched_codes else "-",
                    }
                )
        else:
            for code in sorted(codes):
                aluno = pares.get(code, "-")
                records.append(
                    {
                        "aluno": aluno,
                        "email": "-",
                        "codigo": format_code(code),
                    }
                )

        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"Ata_Sorteio_{timestamp}.docx"
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Ata Oficial do Sorteio (.docx)",
            default_name,
            "Documentos Word (*.docx)",
        )
        if not filename:
            return

        path = Path(filename)
        try:
            generate_draw_report_docx(path, records)
            QMessageBox.information(
                self,
                "Ata gerada com sucesso",
                (
                    f"A Ata Oficial do Sorteio foi salva em:\n{path}\n\n"
                    "Você pode abrir este arquivo no Word para preencher a coluna "
                    "'Prêmio Recebido'."
                ),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self, "Falha ao gerar Ata", f"Ocorreu um erro ao gerar o arquivo .docx:\n{exc}"
            )

    def _save(self, section: _SorteadosSection) -> None:
        if section is self._codes_section:
            self._save_codes()
        else:
            self._save_students()

    def _save_codes(self) -> None:
        section = self._codes_section
        try:
            section._registry.save(section._codes)
        except OSError as exc:
            QMessageBox.critical(self, "Não foi possível salvar", str(exc))
            return
        section._refresh()
        self.sorteadosChanged.emit()

    def _save_students(self) -> None:
        section = self._students_section
        try:
            section._registry.save(section._students)
        except OSError as exc:
            QMessageBox.critical(self, "Não foi possível salvar", str(exc))
            return
        section._refresh()
        self.sorteadosChanged.emit()

    def codes(self) -> set[int]:
        """Conjunto atual de códigos sorteados."""
        return set(self._codes_section._codes)

    def students(self) -> set[str]:
        """Conjunto atual de alunos sorteados (formato exibição)."""
        return set(self._students_section._students)
