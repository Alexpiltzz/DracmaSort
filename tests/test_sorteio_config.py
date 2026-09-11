from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from gui.sorteio_config import SorteioConfigDialog


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    assert isinstance(app, QApplication)
    return app


_APP: QApplication = _ensure_app()


def test_dialog_persiste_valores(tmp_path):
    settings = QSettings(str(tmp_path / "config.ini"), QSettings.Format.IniFormat)
    dialog = SorteioConfigDialog(settings)
    dialog.source_combo.setCurrentIndex(1)
    dialog.quantity_spin.setValue(3)
    dialog.sequential_check.setChecked(True)
    dialog.repetition_combo.setCurrentIndex(1)
    dialog.font_combo.setCurrentFont(QFont("Arial"))
    dialog.size_spin.setValue(48)
    dialog.accept()
    assert settings.value("sorteio/source_index") == 1
    assert settings.value("sorteio/quantity") == 3
    assert settings.value("sorteio/sequential") is True
    assert settings.value("sorteio/repetition") == 1
    assert settings.value("sorteio/font_family") == "Arial"
    assert settings.value("sorteio/font_size") == 48


def test_dialog_carrega_valores_existentes(tmp_path):
    settings = QSettings(str(tmp_path / "config.ini"), QSettings.Format.IniFormat)
    settings.setValue("sorteio/source_index", 1)
    settings.setValue("sorteio/quantity", 5)
    settings.setValue("sorteio/sequential", True)
    settings.setValue("sorteio/repetition", 1)
    settings.setValue("sorteio/font_family", "Courier New")
    settings.setValue("sorteio/font_size", 60)
    dialog = SorteioConfigDialog(settings)
    assert dialog.source_combo.currentIndex() == 1
    assert dialog.quantity_spin.value() == 5
    assert dialog.sequential_check.isChecked()
    assert dialog.repetition_combo.currentIndex() == 1
    assert dialog.font_combo.currentFont().family() == "Courier New"
    assert dialog.size_spin.value() == 60


def test_dialog_valores_padrao(tmp_path):
    settings = QSettings(str(tmp_path / "config.ini"), QSettings.Format.IniFormat)
    dialog = SorteioConfigDialog(settings)
    assert dialog.source_combo.currentIndex() == 0
    assert dialog.quantity_spin.value() == 1
    assert not dialog.sequential_check.isChecked()
    assert dialog.repetition_combo.currentIndex() == 0
    assert dialog.size_spin.value() == 34


def test_dialog_emite_settings_applied(tmp_path):
    settings = QSettings(str(tmp_path / "config.ini"), QSettings.Format.IniFormat)
    dialog = SorteioConfigDialog(settings)
    emitted: list[bool] = []
    dialog.settingsApplied.connect(lambda: emitted.append(True))
    dialog.accept()
    assert emitted == [True]


def test_reject_nao_persiste(tmp_path):
    settings = QSettings(str(tmp_path / "config.ini"), QSettings.Format.IniFormat)
    dialog = SorteioConfigDialog(settings)
    dialog.quantity_spin.setValue(9)
    dialog.reject()
    assert settings.value("sorteio/quantity") is None
