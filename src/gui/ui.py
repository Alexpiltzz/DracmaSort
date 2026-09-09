"""Interface grafica PyQt para o fluxo de sorteio e envio de e-mails.

Este modulo usa a mesma camada de leitura, geracao, persistencia e SMTP da
interface de terminal. Assim, os dois modos compartilham o registro de codigos
ja emitidos e os mesmos formatos de arquivo.
"""

from __future__ import annotations

import sys
from email.mime.multipart import MIMEMultipart
from pathlib import Path

from PyQt6 import uic
from PyQt6.QtCore import QObject, QSettings, QThread, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHeaderView,
    QMainWindow,
    QMessageBox,
    QTableWidgetItem,
)

from code_gen.core import (
    CodeRegistry,
    NotEnoughCodesError,
    StudentRegistry,
    generate_codes,
    pool_size,
)
from code_gen.io import (
    default_output_path,
    default_registry_path,
    default_report_path,
    default_student_registry_path,
    filter_new_students,
    is_valid_email,
    normalize_name,
    read_spreadsheet,
    write_output_csv,
    write_report_csv,
)
from delivery.sender import send_all
from delivery.smtp import SmtpConfig, build_custom_message, enviar_email, markdown_to_html
from updater.updater import UpdateWorker

from .resources import asset_path, load_qss

DEFAULT_SUBJECT = "Confira seus números para o sorteio"
DEFAULT_MESSAGE = """Olá, **{nome}**!

O Colégio Adventista de Blumenau agradece pela realização da rematrícula.

Você recebeu os seguintes números para participar do nosso sorteio:

## {codigos}

Guarde estes números.

Atenciosamente,
**Colégio Adventista de Blumenau**"""


def _status_for_email(email: str) -> tuple[str, str]:
    """Devolve o status inicial e o detalhe exibidos na tabela de saída."""
    if is_valid_email(email):
        return "Aguardando envio", "Aguardando envio"
    return "Aguardando envio | E-mail inválido", "E-mail inválido"


class EmailWorker(QObject):
    """Executa os envios fora da thread da interface para nao travar a janela."""

    row_finished = pyqtSignal(int, object)
    progress = pyqtSignal(int, int)
    message = pyqtSignal(str)
    finished = pyqtSignal(object, bool, str)

    def __init__(
        self,
        rows: list[dict[str, str]],
        config: SmtpConfig,
        *,
        simulate: bool,
        test_only: bool = False,
        subject: str = DEFAULT_SUBJECT,
        body: str = DEFAULT_MESSAGE,
    ) -> None:
        super().__init__()
        self.rows = rows
        self.config = config
        self.simulate = simulate
        self.test_only = test_only
        self.subject = subject
        self.body = body
        self._stop_requested = False

    def request_stop(self) -> None:
        self._stop_requested = True

    def _make_message(self, row: dict[str, str]) -> MIMEMultipart:
        return build_custom_message(
            self.subject,
            self.body,
            nome=row["Nome"],
            remetente=self.config.from_addr,
            destinatario=row["E-mail"],
            codigos=row["Códigos"],
        )

    @pyqtSlot()
    def run(self) -> None:
        if self.test_only:
            self._run_test()
            return

        result = send_all(
            self.config,
            self.rows,
            simulate=self.simulate,
            make_message=self._make_message,
            deliver=enviar_email,
            should_stop=lambda: self._stop_requested,
            on_row=lambda index, report: self.row_finished.emit(index, report),
            on_progress=lambda current, total: self.progress.emit(current, total),
            on_message=lambda text: self.message.emit(text),
        )
        self.finished.emit(result.reports, not result.interrupted, result.summary)

    def _run_test(self) -> None:
        if self.simulate:
            self.finished.emit([], True, "Teste simulado. Nenhum e-mail foi enviado.")
            return
        try:
            message = build_custom_message(
                self.subject,
                self.body,
                nome="Teste",
                remetente=self.config.from_addr,
                destinatario=self.config.to_addr,
                codigos="(mensagem de teste)",
            )
            rejected = enviar_email(self.config, message)
            if rejected:
                self.finished.emit([], True, f"E-mail de teste rejeitado: {rejected}")
            else:
                self.finished.emit([], True, f"E-mail de teste enviado para {self.config.to_addr}.")
        except Exception as exc:  # noqa: BLE001 - exibe a falha no dialogo da UI
            self.finished.emit([], True, f"Falha ao enviar e-mail de teste: {exc}")


class MainWindow(QMainWindow):
    """Janela principal para importar, gerar, revisar e enviar os codigos."""

    def __init__(self) -> None:
        super().__init__()
        self.input_path: Path | None = None
        self.input_records: list[dict[str, str | int]] = []
        self.output_rows: list[dict[str, str]] = []
        self.output_path: Path | None = None
        self.report_path: Path | None = None
        self.worker: EmailWorker | None = None
        self.thread: QThread | None = None
        self.dark_mode = False
        self._pending_update_path: str | None = None
        self._update_worker: UpdateWorker | None = None
        self._update_thread: QThread | None = None
        self._download_thread: QThread | None = None

        self._build_ui()
        self._load_smtp_config()
        self._load_message_template()
        self._set_status("Importe uma planilha para começar.")
        self._start_update_check()

    def _build_ui(self) -> None:
        uic.loadUi(asset_path("main_window.ui"), self)
        self._apply_runtime_geometry()
        self._bind_signals()
        self._update_message_preview()
        self._apply_style()

    def _apply_runtime_geometry(self) -> None:
        self.statusbar.addWidget(self.status_label)
        self.splitter.setSizes([540, 760])
        self.lower_splitter.setSizes([520, 780])
        self.editor_splitter.setSizes([560, 560])
        for table in (self.input_table, self.output_table):
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        root = self.centralWidget().layout()
        root.setStretch(root.indexOf(self.tabs), 1)
        operation = self.tabs.widget(0).layout()
        operation.setStretch(operation.indexOf(self.splitter), 1)
        message = self.tabs.widget(1).layout()
        message.setStretch(message.indexOf(self.editor_splitter), 1)

    def _bind_signals(self) -> None:
        self.theme_button.clicked.connect(self._toggle_theme)
        self.import_button.clicked.connect(self._import_spreadsheet)
        self.generate_button.clicked.connect(self._generate_codes)
        self.export_button.clicked.connect(self._export_output)
        self.open_folder_button.clicked.connect(self._open_output_folder)
        self.simulate_checkbox.toggled.connect(self._update_mode_badge)
        self.test_button.clicked.connect(self._send_test)
        self.send_button.clicked.connect(self._send_participants)
        self.cancel_button.clicked.connect(self._request_stop)
        self.reset_button.clicked.connect(self._reset_message_template)
        self.subject_input.textChanged.connect(self._save_message_template)
        self.message_input.textChanged.connect(self._save_message_template)
        self.message_input.textChanged.connect(self._update_message_preview)
        self.host_input.textChanged.connect(self._save_smtp_config)
        self.port_input.valueChanged.connect(self._save_smtp_config)
        self.login_input.textChanged.connect(self._save_smtp_config)
        self.from_input.textChanged.connect(self._save_smtp_config)

    def _reset_message_template(self) -> None:
        self.subject_input.setText(DEFAULT_SUBJECT)
        self.message_input.setPlainText(DEFAULT_MESSAGE)
        self._save_message_template()
        self._set_status("Modelo original da mensagem restaurado.")

    def _app_settings(self) -> QSettings:
        return QSettings("Colégio Adventista de Blumenau", "Central de Sorteios")

    def _save_message_template(self) -> None:
        if not hasattr(self, "subject_input") or not hasattr(self, "message_input"):
            return
        settings = self._app_settings()
        settings.setValue("email/subject", self.subject_input.text())
        settings.setValue("email/body", self.message_input.toPlainText())
        settings.sync()

    def _load_message_template(self) -> None:
        settings = self._app_settings()
        subject = settings.value("email/subject", DEFAULT_SUBJECT)
        body = settings.value("email/body", DEFAULT_MESSAGE)
        self.subject_input.setText(str(subject))
        self.message_input.setPlainText(str(body))
        self._update_message_preview()

    def _update_message_preview(self) -> None:
        if not hasattr(self, "message_preview"):
            return
        preview_body = self.message_input.toPlainText()
        preview_body = preview_body.replace("{nome}", "Maria Souza")
        preview_body = preview_body.replace("{codigos}", "1234, 5678")
        preview_body = preview_body.replace("{remetente}", "escola@example.com")
        preview_body = preview_body.replace("{destinatario}", "maria@example.com")
        html = markdown_to_html(preview_body)
        self.message_preview.setHtml(
            f'<div style="font-family: Segoe UI; color: #27312b; padding: 14px;">{html}</div>'
        )

    def _apply_style(self) -> None:
        self.setStyleSheet(load_qss(self.dark_mode))

    def _toggle_theme(self) -> None:
        self.dark_mode = not self.dark_mode
        self.theme_button.setText("☾" if self.dark_mode else "☀")
        self.theme_button.setToolTip(
            "Alternar para o tema claro" if self.dark_mode else "Alternar para o tema escuro"
        )
        self._apply_style()
        self._update_message_preview()

    def _save_smtp_config(self) -> None:
        if not hasattr(self, "login_input") or not hasattr(self, "from_input"):
            return
        settings = self._app_settings()
        settings.setValue("smtp/host", self.host_input.text())
        settings.setValue("smtp/port", self.port_input.value())
        settings.setValue("smtp/login", self.login_input.text())
        settings.setValue("smtp/from", self.from_input.text())
        settings.sync()

    def _load_smtp_config(self) -> None:
        config = SmtpConfig.from_env()
        settings = self._app_settings()
        host = settings.value("smtp/host", config.host)
        port = settings.value("smtp/port", config.port)
        login = settings.value("smtp/login", config.login)
        from_addr = settings.value("smtp/from", config.from_addr)
        self.host_input.setText(str(host))
        self.port_input.setValue(int(port))
        self.login_input.setText(str(login))
        self.password_input.setText(config.password)
        self.from_input.setText(str(from_addr))
        self.test_to_input.setText(config.to_addr)

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _log(self, text: str) -> None:
        self.activity_log.appendPlainText(text)

    def _update_mode_badge(self, simulate: bool) -> None:
        self.mode_badge.setText("SIMULAÇÃO ATIVA" if simulate else "ENVIO REAL")
        self.mode_badge.setProperty("real", not simulate)
        self.mode_badge.style().unpolish(self.mode_badge)
        self.mode_badge.style().polish(self.mode_badge)

    def _import_spreadsheet(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Selecione a planilha de participantes",
            str(self.input_path.parent if self.input_path else Path.cwd()),
            "Planilhas (*.xlsx *.csv)",
        )
        if not filename:
            return
        path = Path(filename)
        try:
            records, warnings = read_spreadsheet(path)
        except ValueError as exc:
            QMessageBox.critical(self, "Não foi possível importar", str(exc))
            return

        self.input_path = path
        self.input_records = records
        self.output_rows = []
        self.output_path = None
        self.report_path = None
        self._populate_input_table(records)
        self._clear_output()
        self.activity_log.clear()
        for warning in warnings:
            self._log(f"Aviso: {warning}")
        if not warnings:
            self._log("Planilha validada sem avisos.")
        try:
            tracked = StudentRegistry(default_student_registry_path()).load()
            _, already_tracked = filter_new_students(records, tracked)
            if already_tracked:
                self._log(
                    f"{len(already_tracked)} aluno(s) já rastreado(s), ignorado(s) na geração."
                )
        except (ValueError, OSError) as exc:
            self._log(f"Não foi possível consultar o registro de alunos: {exc}")
        self.generate_button.setEnabled(bool(records))
        self.export_button.setEnabled(False)
        self.open_folder_button.setEnabled(False)
        self.send_button.setEnabled(False)
        self.participants_metric_value.setText(str(len(records)))
        self.codes_metric_value.setText("0")
        try:
            available = pool_size(CodeRegistry(default_registry_path()).load())
            self.available_metric_value.setText(f"{available:,}".replace(",", "."))
        except Exception as exc:  # noqa: BLE001 - o usuario ainda pode corrigir o registro depois
            self.available_metric_value.setText("?")
            self._log(f"Não foi possível consultar o registro de códigos: {exc}")
        self._set_status(f"{len(records)} participante(s) importado(s).")

    def _populate_input_table(self, records: list[dict[str, str | int]]) -> None:
        self.input_table.setRowCount(len(records))
        for row_index, record in enumerate(records):
            values = [
                str(record.get("aluno", "")),
                record["nome"],
                record["email"],
                str(record["quantidade"]),
            ]
            for column, value in enumerate(values):
                self.input_table.setItem(row_index, column, QTableWidgetItem(str(value)))

    def _generate_codes(self) -> None:
        if not self.input_path or not self.input_records:
            return
        registry = CodeRegistry(default_registry_path())
        student_registry = StudentRegistry(default_student_registry_path())
        try:
            used_codes = registry.load()
            tracked_students = student_registry.load()
        except (ValueError, OSError) as exc:
            QMessageBox.critical(self, "Não foi possível carregar os registros", str(exc))
            return

        fresh_records, skipped = filter_new_students(self.input_records, tracked_students)
        for aluno in skipped:
            self._log(f"Aluno '{aluno}' já rastreado, ignorado na geração.")
        if skipped:
            self._set_status(f"{len(skipped)} aluno(s) já rastreado(s) ignorado(s).")
        if not fresh_records:
            QMessageBox.information(
                self, "Nenhum aluno novo", "Todos os alunos da planilha já foram rastreados."
            )
            return

        try:
            valid_records = [
                record for record in fresh_records if bool(record.get("email_valido", True))
            ]
            quantities = [int(record["quantidade"]) for record in valid_records]
            batches = generate_codes(quantities, used_codes) if valid_records else []
        except (NotEnoughCodesError, ValueError, OSError) as exc:
            QMessageBox.critical(self, "Não foi possível gerar os códigos", str(exc))
            return

        batch_iter = iter(batches)
        self.output_rows = []
        for record in fresh_records:
            email_valid = bool(record.get("email_valido", True))
            codes = ", ".join(next(batch_iter)) if email_valid and batches else ""
            self.output_rows.append(
                {
                    "Aluno": str(record.get("aluno", "")),
                    "Nome": str(record["nome"]),
                    "E-mail": str(record["email"]),
                    "Códigos": codes,
                    "email_valido": email_valid,
                }
            )
        self.output_path = default_output_path(self.input_path)
        try:
            if self.output_rows:
                write_output_csv(self.output_path, self.output_rows)
                registry.save(used_codes | {int(code) for batch in batches for code in batch})
                new_students = {normalize_name(str(record["aluno"])) for record in fresh_records}
                student_registry.save(tracked_students | new_students)
        except OSError as exc:
            QMessageBox.critical(self, "Não foi possível salvar a saída", str(exc))
            return

        self._populate_output_table()
        self.codes_metric_value.setText(str(sum(quantities)))
        available_now = used_codes | {int(code) for batch in batches for code in batch}
        self.available_metric_value.setText(f"{pool_size(available_now):,}".replace(",", "."))
        self.export_button.setEnabled(True)
        self.open_folder_button.setEnabled(True)
        self.send_button.setEnabled(any(row.get("email_valido", True) for row in self.output_rows))
        invalid_count = sum(1 for row in self.output_rows if not row.get("email_valido", True))
        if invalid_count:
            self._log(f"{invalid_count} e-mail(s) inválido(s) mantido(s) para revisão na tabela.")
        self._log(f"{sum(quantities)} código(s) gerado(s). CSV salvo em: {self.output_path}")
        self._set_status("Códigos gerados e registrados. Revise a tabela antes do envio.")

    def _populate_output_table(self) -> None:
        self.output_table.setRowCount(len(self.output_rows))
        for row_index, row in enumerate(self.output_rows):
            status, details = _status_for_email(row["E-mail"])
            values = [
                row["Aluno"],
                row["Nome"],
                row["E-mail"],
                row["Códigos"],
                status,
                details,
            ]
            for column, value in enumerate(values):
                self.output_table.setItem(row_index, column, QTableWidgetItem(value))

    def _clear_output(self) -> None:
        self.output_table.setRowCount(0)

    def _export_output(self) -> None:
        if not self.output_rows:
            return
        default_name = self.output_path.name if self.output_path else "codigos_sorteados.csv"
        filename, _ = QFileDialog.getSaveFileName(
            self, "Exportar códigos", default_name, "CSV (*.csv)"
        )
        if not filename:
            return
        path = Path(filename)
        if path.suffix.lower() != ".csv":
            path = path.with_suffix(".csv")
        try:
            write_output_csv(path, self.output_rows)
        except OSError as exc:
            QMessageBox.critical(self, "Não foi possível exportar", str(exc))
            return
        self._set_status(f"CSV exportado para {path}.")

    def _open_output_folder(self) -> None:
        if self.output_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_path.parent)))

    def _smtp_config(self) -> SmtpConfig | None:
        host = self.host_input.text().strip()
        login = self.login_input.text().strip()
        from_addr = self.from_input.text().strip()
        to_addr = self.test_to_input.text().strip()
        if not host or not login or not from_addr:
            QMessageBox.warning(
                self, "Configuração incompleta", "Preencha servidor, login e e-mail remetente."
            )
            return None
        return SmtpConfig(
            host=host,
            port=self.port_input.value(),
            login=login,
            password=self.password_input.text(),
            from_addr=from_addr,
            to_addr=to_addr,
        )

    def _send_test(self) -> None:
        config = self._smtp_config()
        if not config:
            return
        if not config.to_addr:
            QMessageBox.warning(
                self, "Destino ausente", "Informe o destinatário do e-mail de teste."
            )
            return
        if not self.simulate_checkbox.isChecked() and not config.password:
            QMessageBox.warning(
                self, "Senha ausente", "Informe a senha SMTP para enviar um e-mail real."
            )
            return
        self._start_worker([], config, test_only=True)

    def _send_participants(self) -> None:
        if not self.output_rows:
            return
        config = self._smtp_config()
        if not config:
            return
        simulate = self.simulate_checkbox.isChecked()
        if not simulate and not config.password:
            QMessageBox.warning(
                self, "Senha ausente", "Informe a senha SMTP para enviar e-mails reais."
            )
            return
        valid_rows = [row for row in self.output_rows if bool(row.get("email_valido", True))]
        if not valid_rows:
            QMessageBox.information(
                self,
                "Nenhum e-mail válido",
                "Não há e-mails válidos para envio. Revise a planilha antes de continuar.",
            )
            return
        if not simulate:
            answer = QMessageBox.question(
                self,
                "Confirmar envio real",
                f"Enviar e-mails reais para {len(valid_rows)} participante(s)?\n\n"
                "O envio respeitará os intervalos e pausas anti-spam configurados.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._start_worker(self.output_rows, config)

    def _start_worker(
        self, rows: list[dict[str, str]], config: SmtpConfig, *, test_only: bool = False
    ) -> None:
        self.thread = QThread(self)
        self.worker = EmailWorker(
            rows,
            config,
            simulate=self.simulate_checkbox.isChecked(),
            test_only=test_only,
            subject=self.subject_input.text().strip() or DEFAULT_SUBJECT,
            body=self.message_input.toPlainText(),
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.row_finished.connect(self._update_sent_row)
        self.worker.progress.connect(self._update_progress)
        self.worker.message.connect(self._log)
        self.worker.finished.connect(self._finish_worker)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

        self._set_busy(True)
        if test_only:
            self._set_status("Executando teste de e-mail...")
        else:
            self.progress.setRange(0, len(rows))
            self.progress.setValue(0)
            self.progress.setVisible(True)
            self._set_status("Processando envios...")

    def _set_busy(self, busy: bool) -> None:
        self.import_button.setEnabled(not busy)
        self.generate_button.setEnabled(not busy and bool(self.input_records))
        self.export_button.setEnabled(not busy and bool(self.output_rows))
        self.open_folder_button.setEnabled(not busy and self.output_path is not None)
        self.test_button.setEnabled(not busy)
        self.send_button.setEnabled(not busy and bool(self.output_rows))
        self.cancel_button.setEnabled(busy)

    def _update_sent_row(self, row_index: int, report: dict[str, str]) -> None:
        self.output_table.setItem(row_index, 4, QTableWidgetItem(report["Status"]))
        self.output_table.setItem(row_index, 5, QTableWidgetItem(report["Detalhes"]))
        self._log(f"{report['Status']}: {report['E-mail']} — {report['Detalhes']}")

    def _update_progress(self, current: int, total: int) -> None:
        self.progress.setMaximum(total)
        self.progress.setValue(current)
        self.progress.setFormat(f"{current} de {total} e-mails processados")

    def _request_stop(self) -> None:
        if self.worker:
            self.worker.request_stop()
            self.cancel_button.setEnabled(False)
            self._set_status("Interrupção solicitada. Aguardando o término do envio atual...")

    def _finish_worker(self, reports: list[dict[str, str]], completed: bool, summary: str) -> None:
        self._set_busy(False)
        self.progress.setVisible(False)
        self.worker = None
        self.thread = None
        if reports and self.input_path:
            self.report_path = default_report_path(self.input_path)
            try:
                write_report_csv(self.report_path, reports)
                self._log(f"Relatório salvo em: {self.report_path}")
            except OSError as exc:
                self._log(f"Não foi possível salvar o relatório: {exc}")
        self._set_status(summary)
        icon = QMessageBox.Icon.Information if completed else QMessageBox.Icon.Warning
        dialog = QMessageBox(self)
        dialog.setIcon(icon)
        dialog.setWindowTitle("Resultado do envio")
        dialog.setText(summary)
        dialog.exec()

    def _start_update_check(self) -> None:
        """Verifica atualizações em background no startup (silencioso)."""
        self._update_thread = QThread(self)
        self._update_worker = UpdateWorker()
        self._update_worker.moveToThread(self._update_thread)
        self._update_thread.started.connect(self._update_worker.check)
        self._update_worker.update_available.connect(self._on_update_available)
        self._update_worker.progress.connect(self._on_update_progress)
        self._update_worker.download_finished.connect(self._on_update_finished)
        self._update_worker.error.connect(self._on_update_error)
        self._update_worker.up_to_date.connect(self._on_update_up_to_date)
        self._update_worker.error.connect(self._update_thread.quit)
        self._update_worker.up_to_date.connect(self._update_thread.quit)
        self._update_worker.download_finished.connect(self._update_thread.quit)
        self._update_thread.finished.connect(self._update_worker.deleteLater)
        self._update_thread.finished.connect(self._update_thread.deleteLater)
        self._update_thread.start()

    def _on_update_available(self, tag: str, body: str, asset_url: str) -> None:
        """Mostra diálogo perguntando se o usuário quer atualizar."""
        from code_gen import __version__

        answer = QMessageBox.question(
            self,
            "Atualização disponível",
            f"Uma nova versão ({tag}) está disponível.\n\n"
            f"Versão atual: v{__version__}\n\n"
            f"Deseja baixar a atualização agora?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._set_status(f"Baixando atualização {tag}...")
            self._download_thread = QThread(self)
            self._update_worker.moveToThread(self._download_thread)
            self._download_thread.started.connect(self._update_worker.download)
            self._update_worker.download_finished.connect(self._on_update_downloaded)
            self._update_worker.progress.connect(self._on_update_progress)
            self._update_worker.error.connect(self._on_download_error)
            self._update_worker.download_finished.connect(self._download_thread.quit)
            self._update_worker.error.connect(self._download_thread.quit)
            self._download_thread.finished.connect(self._download_thread.deleteLater)
            self._download_thread.start()
        else:
            self._pending_update_path = None
            self._update_thread.quit()

    def _on_update_downloaded(self, path: str) -> None:
        """Download concluído — avisa o usuário que o update será aplicado ao fechar."""
        self._pending_update_path = path
        self._set_status("Atualização baixada. Será aplicada ao fechar o programa.")
        QMessageBox.information(
            self,
            "Atualização pronta",
            "A atualização foi baixada com sucesso.\n\n"
            "Ela será aplicada automaticamente quando você fechar o programa.",
        )

    def _on_update_downloaded(self, path: str) -> None:
        """Download concluído — avisa o usuário que o update será aplicado ao fechar."""
        self._pending_update_path = path
        self._set_status("Atualização baixada. Será aplicada ao fechar o programa.")
        QMessageBox.information(
            self,
            "Atualização pronta",
            "A atualização foi baixada com sucesso.\n\n"
            "Ela será aplicada automaticamente quando você fechar o programa.",
        )

    def _on_update_progress(self, current: int, total: int) -> None:
        """Atualiza a barra de progresso durante o download."""
        if total > 0:
            mb_done = current / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            self._set_status(f"Baixando atualização... {mb_done:.1f}/{mb_total:.1f} MB")

    def _on_update_finished(self, path: str) -> None:
        """Download concluído (fluxo direto sem confirmação)."""
        self._pending_update_path = path
        self._set_status("Atualização baixada. Será aplicada ao fechar o programa.")

    def _on_update_error(self, msg: str) -> None:
        """Erro na verificação — log silencioso."""
        self._log(f"[Updater] {msg}")

    def _on_download_error(self, msg: str) -> None:
        """Erro no download — log silencioso."""
        self._log(f"[Updater] {msg}")

    def _on_update_up_to_date(self) -> None:
        """Versão atual já é a mais recente — nada a fazer."""
        pass

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.thread and self.thread.isRunning():
            answer = QMessageBox.question(
                self,
                "Envio em andamento",
                "Há um envio em andamento. Interromper e fechar a janela?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._request_stop()
            self.thread.wait(3000)
            if self.thread.isRunning():
                QMessageBox.warning(
                    self,
                    "Aguardando envio",
                    "O envio atual ainda não finalizou. Feche novamente em instantes.",
                )
                event.ignore()
                return
        event.accept()
        if self._pending_update_path and self._update_worker:
            self._update_worker.apply_update()


def main() -> int:
    """Abre a aplicacao grafica."""
    app = QApplication(sys.argv)
    app.setApplicationName("Central de Sorteios")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
