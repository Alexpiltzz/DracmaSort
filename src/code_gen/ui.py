"""Interface grafica PyQt para o fluxo de sorteio e envio de e-mails.

Este modulo usa a mesma camada de leitura, geracao, persistencia e SMTP da
interface de terminal. Assim, os dois modos compartilham o registro de codigos
ja emitidos e os mesmos formatos de arquivo.
"""

# ruff: noqa: E501

from __future__ import annotations

import random
import sys
import time
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, QThread, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .core import CodeRegistry, NotEnoughCodesError, generate_codes, pool_size
from .io import (
    default_output_path,
    default_registry_path,
    default_report_path,
    read_spreadsheet,
    is_valid_email,
    write_output_csv,
    write_report_csv,
)
from .main import (
    BATCH_PAUSE_MAX,
    BATCH_PAUSE_MIN,
    BATCH_SIZE,
    DELAY_PER_EMAIL_MAX,
    DELAY_PER_EMAIL_MIN,
)
from .smtp import SmtpConfig, build_custom_message, enviar_email, markdown_to_html

DEFAULT_SUBJECT = "Seus números para o sorteio"
DEFAULT_MESSAGE = """Olá, **{nome}**!

Agradecemos pela realização da matrícula.

Você recebeu os seguintes números para participar do nosso sorteio:

## {codigos}

Guarde estes números.

Atenciosamente,
**Colégio**"""


def _status_for_email(email: str) -> tuple[str, str]:
    """Devolve o status inicial e o detalhe exibidos na tabela de saída."""
    if is_valid_email(email):
        return "Aguardando envio", "Aguardando envio"
    return "Aguardando envio | E-mail inválido", "E-mail inválido"


LIGHT_STYLE = """
QWidget { background: #f5f5f2; color: #272727; font-family: 'Segoe UI'; font-size: 13px; }
QMainWindow, QTabWidget::pane { background: #f5f5f2; }
QLabel { background: transparent; }
QLabel#title { color: #242424; font-size: 29px; font-weight: 700; }
QLabel#subtitle, QLabel#messageIntro { color: #77736d; font-size: 14px; }
QLabel#panelLabel { color: #e16c25; font-size: 11px; font-weight: 700; }
QLabel#placeholderHelp { color: #8a857d; }
QLabel#modeBadge { background: #f7c59f; color: #8a3f15; border-radius: 12px; padding: 7px 12px; font-weight: 700; font-size: 11px; }
QLabel#modeBadge[real="true"] { background: #f08a54; color: #4e1c0c; }
QGroupBox { background: rgba(255,255,255,220); border: 1px solid #dedbd5; border-radius: 10px; margin-top: 12px; padding: 12px; font-weight: 700; color: #3c3935; }
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 5px; }
QFrame#metricCard { background: rgba(255,255,255,190); border: 1px solid #e1ded8; border-radius: 9px; }
QLabel#metricLabel { color: #918a81; font-size: 10px; font-weight: 700; }
QLabel#metricValue { color: #242424; font-size: 23px; font-weight: 700; }
QPushButton { background: rgba(255,255,255,210); border: 1px solid #d8d4ce; border-radius: 7px; padding: 8px 13px; font-weight: 600; }
QPushButton:hover { background: #fff0e5; border-color: #e98a4e; }
QPushButton:disabled { background: #ecebe8; color: #aaa7a1; border-color: #e2dfda; }
QPushButton#primaryButton, QPushButton#sendButton { background: #e8752b; color: white; border: none; }
QPushButton#primaryButton:hover, QPushButton#sendButton:hover { background: #c95b19; }
QTableWidget, QPlainTextEdit { background: rgba(255,255,255,235); border: 1px solid #dedbd5; gridline-color: #efede9; alternate-background-color: #faf9f7; }
QTextBrowser { background: #ffffff; border: 1px solid #dedbd5; }
QHeaderView::section { background: #f0eee9; color: #5b5751; border: none; border-bottom: 1px solid #dedbd5; padding: 7px; font-weight: 700; }
QLineEdit, QSpinBox, QComboBox { background: rgba(255,255,255,235); border: 1px solid #d8d4ce; border-radius: 5px; padding: 6px; }
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus { border: 2px solid #e8752b; }
QTabBar::tab { background: transparent; color: #817b73; padding: 9px 18px; border-bottom: 2px solid transparent; font-weight: 600; }
QTabBar::tab:selected { color: #c95b19; border-bottom: 2px solid #e8752b; }
QProgressBar { border: 1px solid #d8d4ce; border-radius: 6px; text-align: center; background: #ffffff; }
QProgressBar::chunk { background: #e8752b; border-radius: 5px; }
QToolButton#themeButton { background: transparent; color: #e8752b; border: 1px solid #e3b28d; border-radius: 17px; padding: 5px; font-size: 20px; }
QToolButton#themeButton:hover { background: #fff0e5; border-color: #e8752b; }
"""

DARK_STYLE = """
QWidget { background: #171717; color: #eeeeeb; font-family: 'Segoe UI'; font-size: 13px; }
QMainWindow, QTabWidget::pane { background: #171717; }
QLabel { background: transparent; }
QLabel#title { color: #f4f0e9; font-size: 29px; font-weight: 700; }
QLabel#subtitle, QLabel#messageIntro { color: #a7a29a; font-size: 14px; }
QLabel#panelLabel { color: #f0904d; font-size: 11px; font-weight: 700; }
QLabel#placeholderHelp { color: #99948c; }
QLabel#modeBadge { background: #634128; color: #ffc08f; border-radius: 12px; padding: 7px 12px; font-weight: 700; font-size: 11px; }
QLabel#modeBadge[real="true"] { background: #9b4c2b; color: #ffe2d0; }
QGroupBox { background: rgba(39,39,39,235); border: 1px solid #414141; border-radius: 10px; margin-top: 12px; padding: 12px; font-weight: 700; color: #f0ede7; }
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 5px; }
QFrame#metricCard { background: rgba(43,43,43,220); border: 1px solid #464646; border-radius: 9px; }
QLabel#metricLabel { color: #a29c93; font-size: 10px; font-weight: 700; }
QLabel#metricValue { color: #f5f2ed; font-size: 23px; font-weight: 700; }
QPushButton { background: rgba(54,54,54,235); color: #eeeae4; border: 1px solid #505050; border-radius: 7px; padding: 8px 13px; font-weight: 600; }
QPushButton:hover { background: #53311e; border-color: #e8752b; }
QPushButton:disabled { background: #272727; color: #77736d; border-color: #343434; }
QPushButton#primaryButton, QPushButton#sendButton { background: #e8752b; color: white; border: none; }
QPushButton#primaryButton:hover, QPushButton#sendButton:hover { background: #f08b45; }
QTableWidget, QPlainTextEdit { background: rgba(29,29,29,245); color: #eeeae4; border: 1px solid #414141; gridline-color: #303030; alternate-background-color: #242424; }
QTextBrowser { background: #ffffff; border: 1px solid #5a5a5a; }
QHeaderView::section { background: #303030; color: #ded9d1; border: none; border-bottom: 1px solid #4a4a4a; padding: 7px; font-weight: 700; }
QLineEdit, QSpinBox, QComboBox { background: rgba(31,31,31,245); color: #eeeae4; border: 1px solid #505050; border-radius: 5px; padding: 6px; }
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus { border: 2px solid #e8752b; }
QComboBox QAbstractItemView { background: #292929; color: #eeeae4; selection-background-color: #e8752b; }
QTabBar::tab { background: transparent; color: #918b83; padding: 9px 18px; border-bottom: 2px solid transparent; font-weight: 600; }
QTabBar::tab:selected { color: #f0904d; border-bottom: 2px solid #e8752b; }
QProgressBar { border: 1px solid #505050; border-radius: 6px; text-align: center; background: #242424; color: #eeeae4; }
QProgressBar::chunk { background: #e8752b; border-radius: 5px; }
QToolButton#themeButton { background: transparent; color: #f0904d; border: 1px solid #805034; border-radius: 17px; padding: 5px; font-size: 20px; }
QToolButton#themeButton:hover { background: #53311e; border-color: #e8752b; }
"""


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

    def _wait(self, seconds: float) -> bool:
        """Aguarda permitindo que o usuario interrompa o lote durante a pausa."""
        remaining = seconds
        while remaining > 0:
            if self._stop_requested:
                return False
            interval = min(0.25, remaining)
            time.sleep(interval)
            remaining -= interval
        return True

    @pyqtSlot()
    def run(self) -> None:
        if self.test_only:
            self._run_test()
            return

        report_rows: list[dict[str, str]] = []
        total = len(self.rows)
        interrupted = False

        for index, row in enumerate(self.rows, start=1):
            if self._stop_requested:
                interrupted = True
                break

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            email_valid = bool(row.get("email_valido", True))
            status = "Simulado" if self.simulate else "Sucesso"
            details = "Nenhum e-mail enviado (modo de simulação)." if self.simulate else "Enviado com sucesso"

            if not email_valid:
                status = "Simulado" if self.simulate else "Falha"
                details = "E-mail inválido."
            elif not self.simulate:
                message = build_custom_message(
                    self.subject,
                    self.body,
                    nome=row["Nome"],
                    remetente=self.config.from_addr,
                    destinatario=row["E-mail"],
                    codigos=row["Códigos"],
                )
                try:
                    rejected = enviar_email(self.config, message)
                    if rejected:
                        status = "Rejeitado"
                        details = f"Rejeitados: {rejected}"
                except Exception as exc:  # noqa: BLE001 - uma falha nao interrompe o lote
                    status = "Falha"
                    details = str(exc)

            report = {
                "Nome": row["Nome"],
                "E-mail": row["E-mail"],
                "Códigos": row["Códigos"],
                "Status": status,
                "Data_Hora": now,
                "Detalhes": details,
            }
            report_rows.append(report)
            self.row_finished.emit(index - 1, report)
            self.progress.emit(index, total)

            if not self.simulate and index < total:
                if index % BATCH_SIZE == 0:
                    seconds = random.uniform(BATCH_PAUSE_MIN, BATCH_PAUSE_MAX)
                    self.message.emit(
                        f"Pausa de segurança apos {index} e-mails: {seconds / 60:.1f} minutos."
                    )
                else:
                    seconds = random.uniform(DELAY_PER_EMAIL_MIN, DELAY_PER_EMAIL_MAX)
                if not self._wait(seconds):
                    interrupted = True
                    break

        failures = sum(row["Status"] in {"Falha", "Rejeitado"} for row in report_rows)
        if interrupted:
            summary = f"Envio interrompido: {len(report_rows)} de {total} e-mails processados."
        elif failures:
            summary = f"Envio concluído com {failures} falha(s) em {total} e-mails."
        elif self.simulate:
            summary = f"Simulação concluída para {total} e-mail(s). Nenhuma mensagem foi enviada."
        else:
            summary = f"{total} e-mail(s) enviados com sucesso."
        self.finished.emit(report_rows, not interrupted, summary)

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

        self.setWindowTitle("Central de Sorteios")
        self.setMinimumSize(1100, 720)
        self.resize(1320, 820)
        self._build_ui()
        self._load_smtp_config()
        self._set_status("Importe uma planilha para começar.")

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        layout.addLayout(self._build_header())

        tabs = QTabWidget()
        operation_tab = QWidget()
        operation_layout = QVBoxLayout(operation_tab)
        operation_layout.setContentsMargins(0, 16, 0, 0)
        operation_layout.addLayout(self._build_actions())
        operation_layout.addLayout(self._build_metrics())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_input_group())
        splitter.addWidget(self._build_output_group())
        splitter.setSizes([540, 760])
        operation_layout.addWidget(splitter, stretch=1)

        lower = QSplitter(Qt.Orientation.Horizontal)
        lower.addWidget(self._build_warnings_group())
        lower.addWidget(self._build_smtp_group())
        lower.setSizes([520, 780])
        operation_layout.addWidget(lower)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        operation_layout.addWidget(self.progress)

        tabs.addTab(operation_tab, "Operação")
        tabs.addTab(self._build_message_tab(), "Mensagem")
        layout.addWidget(tabs, stretch=1)

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        self.status_label = QLabel()
        status_bar.addWidget(self.status_label)

        self._apply_style()

    def _build_message_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 16, 0, 0)

        intro = QLabel(
            "Escreva em Markdown à esquerda e confira a prévia visual do HTML à direita. "
            "As alterações serão usadas na simulação, no teste e no envio real."
        )
        intro.setObjectName("messageIntro")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        subject_row = QHBoxLayout()
        subject_row.addWidget(QLabel("Assunto"))
        self.subject_input = QLineEdit(DEFAULT_SUBJECT)
        subject_row.addWidget(self.subject_input, stretch=1)
        reset_button = QPushButton("Restaurar modelo original")
        reset_button.clicked.connect(self._reset_message_template)
        subject_row.addWidget(reset_button)
        layout.addLayout(subject_row)

        editor_splitter = QSplitter(Qt.Orientation.Horizontal)
        editor_panel = QWidget()
        editor_layout = QVBoxLayout(editor_panel)
        editor_layout.setContentsMargins(0, 0, 8, 0)
        editor_label = QLabel("Markdown")
        editor_label.setObjectName("panelLabel")
        editor_layout.addWidget(editor_label)

        self.message_input = QPlainTextEdit()
        self.message_input.setPlainText(DEFAULT_MESSAGE)
        self.message_input.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.message_input.textChanged.connect(self._update_message_preview)
        editor_layout.addWidget(self.message_input, stretch=1)

        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(8, 0, 0, 0)
        preview_label = QLabel("Prévia do e-mail")
        preview_label.setObjectName("panelLabel")
        preview_layout.addWidget(preview_label)
        self.message_preview = QTextBrowser()
        self.message_preview.setOpenExternalLinks(False)
        self.message_preview.setReadOnly(True)
        preview_layout.addWidget(self.message_preview, stretch=1)

        editor_splitter.addWidget(editor_panel)
        editor_splitter.addWidget(preview_panel)
        editor_splitter.setSizes([560, 560])
        layout.addWidget(editor_splitter, stretch=1)

        placeholders = QLabel(
            "Campos disponíveis: {nome}  {codigos}  {remetente}  {destinatario}. "
            "Use negrito, itálico, títulos, listas e links em Markdown."
        )
        placeholders.setObjectName("placeholderHelp")
        placeholders.setWordWrap(True)
        layout.addWidget(placeholders)
        self._update_message_preview()
        return tab

    def _reset_message_template(self) -> None:
        self.subject_input.setText(DEFAULT_SUBJECT)
        self.message_input.setPlainText(DEFAULT_MESSAGE)
        self._set_status("Modelo original da mensagem restaurado.")

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
            "<div style=\"font-family: Segoe UI; color: #27312b; padding: 14px;\">"
            f"{html}</div>"
        )

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Central de Sorteios")
        title.setObjectName("title")
        subtitle = QLabel("Importe, confira os códigos e acompanhe cada envio em um único lugar.")
        subtitle.setObjectName("subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()
        self.theme_button = QToolButton()
        self.theme_button.setObjectName("themeButton")
        self.theme_button.setText("☀")
        self.theme_button.setToolTip("Alternar para o tema escuro")
        self.theme_button.setAccessibleName("Alternar tema claro e escuro")
        self.theme_button.clicked.connect(self._toggle_theme)
        header.addWidget(self.theme_button, alignment=Qt.AlignmentFlag.AlignTop)
        self.mode_badge = QLabel("SIMULAÇÃO ATIVA")
        self.mode_badge.setObjectName("modeBadge")
        self.mode_badge.setProperty("real", False)
        header.addWidget(self.mode_badge, alignment=Qt.AlignmentFlag.AlignTop)
        return header

    def _build_actions(self) -> QHBoxLayout:
        actions = QHBoxLayout()
        self.import_button = QPushButton("Importar planilha")
        self.import_button.setObjectName("primaryButton")
        self.import_button.clicked.connect(self._import_spreadsheet)
        self.generate_button = QPushButton("Gerar códigos")
        self.generate_button.clicked.connect(self._generate_codes)
        self.generate_button.setEnabled(False)
        self.export_button = QPushButton("Exportar CSV")
        self.export_button.clicked.connect(self._export_output)
        self.export_button.setEnabled(False)
        self.open_folder_button = QPushButton("Abrir pasta")
        self.open_folder_button.clicked.connect(self._open_output_folder)
        self.open_folder_button.setEnabled(False)
        actions.addWidget(self.import_button)
        actions.addWidget(self.generate_button)
        actions.addWidget(self.export_button)
        actions.addWidget(self.open_folder_button)
        actions.addStretch()
        return actions

    def _build_metrics(self) -> QGridLayout:
        metrics = QGridLayout()
        metrics.setHorizontalSpacing(12)
        self.participants_metric = self._metric("Participantes", "0")
        self.codes_metric = self._metric("Códigos gerados", "0")
        self.available_metric = self._metric("Códigos disponíveis", "—")
        metrics.addWidget(self.participants_metric, 0, 0)
        metrics.addWidget(self.codes_metric, 0, 1)
        metrics.addWidget(self.available_metric, 0, 2)
        return metrics

    @staticmethod
    def _metric(label: str, value: str) -> QFrame:
        card = QFrame()
        card.setObjectName("metricCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        label_widget = QLabel(label.upper())
        label_widget.setObjectName("metricLabel")
        value_widget = QLabel(value)
        value_widget.setObjectName("metricValue")
        card_layout.addWidget(label_widget)
        card_layout.addWidget(value_widget)
        card.value_widget = value_widget  # type: ignore[attr-defined]
        return card

    def _build_input_group(self) -> QGroupBox:
        group = QGroupBox("1. Participantes importados")
        layout = QVBoxLayout(group)
        self.input_table = self._create_table(["Nome", "E-mail", "Quantidade"])
        layout.addWidget(self.input_table)
        return group

    def _build_output_group(self) -> QGroupBox:
        group = QGroupBox("2. Códigos e status de envio")
        layout = QVBoxLayout(group)
        self.output_table = self._create_table(["Nome", "E-mail", "Códigos", "Status", "Detalhes"])
        layout.addWidget(self.output_table)
        return group

    def _build_warnings_group(self) -> QGroupBox:
        group = QGroupBox("Validação e atividade")
        layout = QVBoxLayout(group)
        self.activity_log = QPlainTextEdit()
        self.activity_log.setReadOnly(True)
        self.activity_log.setPlaceholderText("Avisos da planilha e andamento do envio aparecerão aqui.")
        layout.addWidget(self.activity_log)
        return group

    def _build_smtp_group(self) -> QGroupBox:
        group = QGroupBox("3. Configuração e envio")
        layout = QVBoxLayout(group)
        form = QFormLayout()
        self.host_input = QLineEdit()
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.login_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.from_input = QLineEdit()
        self.test_to_input = QLineEdit()
        form.addRow("Servidor SMTP", self.host_input)
        form.addRow("Porta", self.port_input)
        form.addRow("Login", self.login_input)
        form.addRow("Senha", self.password_input)
        form.addRow("E-mail remetente", self.from_input)
        form.addRow("Destino do teste", self.test_to_input)
        layout.addLayout(form)

        self.simulate_checkbox = QCheckBox("Simular envios (não envia mensagens reais)")
        self.simulate_checkbox.setChecked(True)
        self.simulate_checkbox.toggled.connect(self._update_mode_badge)
        layout.addWidget(self.simulate_checkbox)

        send_actions = QHBoxLayout()
        self.test_button = QPushButton("Enviar teste")
        self.test_button.clicked.connect(self._send_test)
        self.send_button = QPushButton("Enviar para participantes")
        self.send_button.setObjectName("sendButton")
        self.send_button.setEnabled(False)
        self.send_button.clicked.connect(self._send_participants)
        self.cancel_button = QPushButton("Interromper")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._request_stop)
        send_actions.addWidget(self.test_button)
        send_actions.addWidget(self.send_button)
        send_actions.addWidget(self.cancel_button)
        layout.addLayout(send_actions)
        return group

    @staticmethod
    def _create_table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        return table

    def _apply_style(self) -> None:
        self.setStyleSheet(DARK_STYLE if self.dark_mode else LIGHT_STYLE)

    def _toggle_theme(self) -> None:
        self.dark_mode = not self.dark_mode
        self.theme_button.setText("☾" if self.dark_mode else "☀")
        self.theme_button.setToolTip(
            "Alternar para o tema claro" if self.dark_mode else "Alternar para o tema escuro"
        )
        self._apply_style()
        self._update_message_preview()

    def _load_smtp_config(self) -> None:
        config = SmtpConfig.from_env()
        self.host_input.setText(config.host)
        self.port_input.setValue(config.port)
        self.login_input.setText(config.login)
        self.password_input.setText(config.password)
        self.from_input.setText(config.from_addr)
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
        self.generate_button.setEnabled(bool(records))
        self.export_button.setEnabled(False)
        self.open_folder_button.setEnabled(False)
        self.send_button.setEnabled(False)
        self.participants_metric.value_widget.setText(str(len(records)))  # type: ignore[attr-defined]
        self.codes_metric.value_widget.setText("0")  # type: ignore[attr-defined]
        try:
            available = pool_size(CodeRegistry(default_registry_path()).load())
            self.available_metric.value_widget.setText(f"{available:,}".replace(",", "."))  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001 - o usuario ainda pode corrigir o registro depois
            self.available_metric.value_widget.setText("?")  # type: ignore[attr-defined]
            self._log(f"Não foi possível consultar o registro de códigos: {exc}")
        self._set_status(f"{len(records)} participante(s) importado(s).")

    def _populate_input_table(self, records: list[dict[str, str | int]]) -> None:
        self.input_table.setRowCount(len(records))
        for row_index, record in enumerate(records):
            values = [record["nome"], record["email"], str(record["quantidade"])]
            for column, value in enumerate(values):
                self.input_table.setItem(row_index, column, QTableWidgetItem(str(value)))

    def _generate_codes(self) -> None:
        if not self.input_path or not self.input_records:
            return
        registry = CodeRegistry(default_registry_path())
        try:
            used_codes = registry.load()
            valid_records = [record for record in self.input_records if bool(record.get("email_valido", True))]
            quantities = [int(record["quantidade"]) for record in valid_records]
            batches = generate_codes(quantities, used_codes) if valid_records else []
        except (NotEnoughCodesError, ValueError, OSError) as exc:
            QMessageBox.critical(self, "Não foi possível gerar os códigos", str(exc))
            return

        batch_iter = iter(batches)
        self.output_rows = []
        for record in self.input_records:
            email_valid = bool(record.get("email_valido", True))
            codes = ", ".join(next(batch_iter)) if email_valid and batches else ""
            self.output_rows.append(
                {
                    "Nome": str(record["nome"]),
                    "E-mail": str(record["email"]),
                    "Códigos": codes,
                    "email_valido": email_valid,
                }
            )
        self.output_path = default_output_path(self.input_path)
        try:
            write_output_csv(self.output_path, self.output_rows)
            registry.save(used_codes | {int(code) for batch in batches for code in batch})
        except OSError as exc:
            QMessageBox.critical(self, "Não foi possível salvar a saída", str(exc))
            return

        self._populate_output_table()
        self.codes_metric.value_widget.setText(str(sum(quantities)))  # type: ignore[attr-defined]
        self.available_metric.value_widget.setText(f"{pool_size(used_codes | {int(code) for batch in batches for code in batch}):,}".replace(",", "."))  # type: ignore[attr-defined]
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
            values = [row["Nome"], row["E-mail"], row["Códigos"], status, details]
            for column, value in enumerate(values):
                self.output_table.setItem(row_index, column, QTableWidgetItem(value))

    def _clear_output(self) -> None:
        self.output_table.setRowCount(0)

    def _export_output(self) -> None:
        if not self.output_rows:
            return
        default_name = self.output_path.name if self.output_path else "codigos_sorteados.csv"
        filename, _ = QFileDialog.getSaveFileName(self, "Exportar códigos", default_name, "CSV (*.csv)")
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
            QMessageBox.warning(self, "Configuração incompleta", "Preencha servidor, login e e-mail remetente.")
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
            QMessageBox.warning(self, "Destino ausente", "Informe o destinatário do e-mail de teste.")
            return
        if not self.simulate_checkbox.isChecked() and not config.password:
            QMessageBox.warning(self, "Senha ausente", "Informe a senha SMTP para enviar um e-mail real.")
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
            QMessageBox.warning(self, "Senha ausente", "Informe a senha SMTP para enviar e-mails reais.")
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

    def _start_worker(self, rows: list[dict[str, str]], config: SmtpConfig, *, test_only: bool = False) -> None:
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
        self.output_table.setItem(row_index, 3, QTableWidgetItem(report["Status"]))
        self.output_table.setItem(row_index, 4, QTableWidgetItem(report["Detalhes"]))
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
                    "Ainda não foi possível finalizar o envio atual. Tente fechar novamente em instantes.",
                )
                event.ignore()
                return
        event.accept()


def main() -> int:
    """Abre a aplicacao grafica."""
    app = QApplication(sys.argv)
    app.setApplicationName("Central de Sorteios")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
