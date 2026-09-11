"""Configuracao do sorteador: fonte de dados, quantidade, ordem, repeticao e tipografia.

Os valores escolhidos sao persistidos via ``QSettings`` e reaplicados pela
janela principal atraves do sinal ``settingsApplied``.
"""

from __future__ import annotations

from PyQt6.QtCore import QSettings, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

DEFAULT_FONT_SIZE = 34


def _stored_bool(settings: QSettings, key: str, default: bool) -> bool:
    value = settings.value(key, default)
    return value in (True, "true", "1", 1)


class SorteioConfigDialog(QDialog):
    """Dialog para ajustar o comportamento do sorteador."""

    settingsApplied = pyqtSignal()

    def __init__(self, settings: QSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configuração do sorteio")
        self.setModal(True)
        self._settings = settings
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        source_box = QGroupBox("Fonte de dados")
        source_layout = QFormLayout(source_box)
        self.source_combo = QComboBox()
        self.source_combo.addItems(["Alunos (nomes)", "Códigos"])
        source_layout.addRow("Fonte", self.source_combo)
        root.addWidget(source_box)

        draw_box = QGroupBox("Sorteio")
        draw_layout = QFormLayout(draw_box)
        self.quantity_spin = QSpinBox()
        self.quantity_spin.setRange(1, 50)
        draw_layout.addRow("Quantidade por sorteio", self.quantity_spin)
        self.sequential_check = QCheckBox("Sortear em ordem")
        draw_layout.addRow("Ordem", self.sequential_check)
        self.repetition_combo = QComboBox()
        self.repetition_combo.addItems(["Sem repetição", "Com repetição"])
        draw_layout.addRow("Repetição", self.repetition_combo)
        root.addWidget(draw_box)

        font_box = QGroupBox("Fonte do resultado")
        font_layout = QFormLayout(font_box)
        self.font_combo = QFontComboBox()
        self.size_spin = QSpinBox()
        self.size_spin.setRange(16, 120)
        self.size_spin.setSuffix(" px")
        self.size_spin.setValue(DEFAULT_FONT_SIZE)
        font_layout.addRow("Família", self.font_combo)
        font_layout.addRow("Tamanho", self.size_spin)
        hint = QLabel("O tamanho dos códigos é o dobro do informado.")
        hint.setWordWrap(True)
        font_layout.addRow("", hint)
        root.addWidget(font_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _load_values(self) -> None:
        self.source_combo.setCurrentIndex(int(self._settings.value("sorteio/source_index", 0)))
        self.quantity_spin.setValue(int(self._settings.value("sorteio/quantity", 1)))
        self.sequential_check.setChecked(_stored_bool(self._settings, "sorteio/sequential", False))
        self.repetition_combo.setCurrentIndex(int(self._settings.value("sorteio/repetition", 0)))
        family = str(self._settings.value("sorteio/font_family", "Segoe UI"))
        self.font_combo.setCurrentFont(QFont(family))
        self.size_spin.setValue(int(self._settings.value("sorteio/font_size", DEFAULT_FONT_SIZE)))

    def accept(self) -> None:
        self._persist()
        super().accept()
        self.settingsApplied.emit()

    def _persist(self) -> None:
        self._settings.setValue("sorteio/source_index", self.source_combo.currentIndex())
        self._settings.setValue("sorteio/quantity", self.quantity_spin.value())
        self._settings.setValue("sorteio/sequential", self.sequential_check.isChecked())
        self._settings.setValue("sorteio/repetition", self.repetition_combo.currentIndex())
        self._settings.setValue("sorteio/font_family", self.font_combo.currentFont().family())
        self._settings.setValue("sorteio/font_size", self.size_spin.value())
        self._settings.sync()
