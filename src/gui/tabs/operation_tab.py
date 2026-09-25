"""Controlador modular da aba de Operação (Importação, Tabela, Códigos e Envio)."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QTableWidgetItem

from code_gen.core import (
    CodeRegistry,
    pool_size,
)
from code_gen.io import (
    KEY_CODIGOS_EMITIDOS,
    confirmed_sent_students,
    default_config_path,
    filter_new_students,
    read_spreadsheet,
)


class SpreadsheetWorker(QObject):
    """Executa a leitura da planilha fora da thread da interface."""

    finished = pyqtSignal(list, list)
    error = pyqtSignal(str)

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path

    @pyqtSlot()
    def run(self) -> None:
        try:
            records, warnings = read_spreadsheet(self.path)
            self.finished.emit(records, warnings)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class OperationTabHandler(QObject):
    """Gerencia a aba de Operação da janela principal."""

    status_changed = pyqtSignal(str)
    log_message = pyqtSignal(str)

    def __init__(self, window) -> None:
        parent = window if isinstance(window, QObject) else None
        super().__init__(parent)
        self.window = window
        self.worker_thread: QThread | None = None
        self.spreadsheet_worker: SpreadsheetWorker | None = None

    def import_spreadsheet(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self.window,
            "Selecione a planilha de participantes",
            str(self.window.input_path.parent if self.window.input_path else Path.cwd()),
            "Planilhas (*.xlsx *.csv)",
        )
        if not filename:
            return

        path = Path(filename)
        self.window.import_button.setEnabled(False)
        self.status_changed.emit("Lendo planilha em segundo plano...")

        self.worker_thread = QThread()
        self.spreadsheet_worker = SpreadsheetWorker(path)
        self.spreadsheet_worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.spreadsheet_worker.run)
        self.spreadsheet_worker.finished.connect(
            lambda records, warnings: self._on_import_success(path, records, warnings)
        )
        self.spreadsheet_worker.error.connect(self._on_import_error)
        self.spreadsheet_worker.finished.connect(self.worker_thread.quit)
        self.spreadsheet_worker.error.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(lambda: self.window.import_button.setEnabled(True))

        self.worker_thread.start()

    def _on_import_success(
        self, path: Path, records: list[dict[str, str | int]], warnings: list[str]
    ) -> None:
        self.window.input_path = path
        self.window.input_records = records
        self.window.output_rows = []
        self.window.output_path = None
        self.window.report_path = None
        self._populate_input_table(records)
        self.window._clear_output()
        self.window.activity_log.clear()

        for warning in warnings:
            self.log_message.emit(f"Aviso: {warning}")
        if not warnings:
            self.log_message.emit("Planilha validada sem avisos.")

        try:
            _, already_tracked = filter_new_students(records, confirmed_sent_students())
            if already_tracked:
                self.log_message.emit(
                    f"{len(already_tracked)} aluno(s) já enviado(s), ignorado(s) na geração."
                )
        except Exception as exc:  # noqa: BLE001
            self.log_message.emit(f"Não foi possível consultar o relatório de envios: {exc}")

        self.window.generate_button.setEnabled(bool(records))
        self.window.export_button.setEnabled(False)
        self.window.open_folder_button.setEnabled(False)
        self.window.send_button.setEnabled(False)
        self.window.participants_metric_value.setText(str(len(records)))
        self.window.codes_metric_value.setText("0")

        try:
            available = pool_size(
                CodeRegistry(default_config_path(), section=KEY_CODIGOS_EMITIDOS).load()
            )
            self.window.available_metric_value.setText(f"{available:,}".replace(",", "."))
        except Exception as exc:  # noqa: BLE001
            self.window.available_metric_value.setText("?")
            self.log_message.emit(f"Não foi possível consultar o registro de códigos: {exc}")

        self.status_changed.emit(f"{len(records)} participante(s) importado(s).")

    def _on_import_error(self, message: str) -> None:
        QMessageBox.critical(self.window, "Não foi possível importar", message)
        self.status_changed.emit("Falha ao importar a planilha.")

    def _populate_input_table(self, records: list[dict[str, str | int]]) -> None:
        self.window.input_table.setRowCount(len(records))
        for row_index, record in enumerate(records):
            values = [
                str(record.get("aluno", "")),
                str(record["nome"]),
                str(record["email"]),
                str(record["quantidade"]),
            ]
            for column, value in enumerate(values):
                self.window.input_table.setItem(row_index, column, QTableWidgetItem(str(value)))
