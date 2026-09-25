"""Controlador modular da aba de Modelo de E-mail."""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from delivery.smtp import markdown_to_html

DEFAULT_SUBJECT = "Confira seus números para o sorteio"
DEFAULT_MESSAGE = """Olá, **{nome}**!

O Colégio Adventista de Blumenau agradece pela realização da rematrícula.

Você recebeu os seguintes números para participar do nosso sorteio:

## {codigos}

Guarde estes números.

Atenciosamente,
**Colégio Adventista de Blumenau**"""


class EmailTemplateTabHandler(QObject):
    """Gerencia a aba de Modelo de E-mail da janela principal."""

    status_changed = pyqtSignal(str)

    def __init__(self, window) -> None:
        parent = window if isinstance(window, QObject) else None
        super().__init__(parent)
        self.window = window

    def reset_template(self) -> None:
        self.window.subject_input.setText(DEFAULT_SUBJECT)
        self.window.message_input.setPlainText(DEFAULT_MESSAGE)
        self.save_template()
        self.status_changed.emit("Modelo original da mensagem restaurado.")

    def save_template(self) -> None:
        if not hasattr(self.window, "subject_input") or not hasattr(self.window, "message_input"):
            return
        settings = self.window._app_settings()
        settings.setValue("email/subject", self.window.subject_input.text())
        settings.setValue("email/body", self.window.message_input.toPlainText())
        settings.sync()

    def load_template(self) -> None:
        settings = self.window._app_settings()
        subject = settings.value("email/subject", DEFAULT_SUBJECT)
        body = settings.value("email/body", DEFAULT_MESSAGE)
        self.window.subject_input.setText(str(subject))
        self.window.message_input.setPlainText(str(body))
        self.update_preview()

    def update_preview(self) -> None:
        if not hasattr(self.window, "message_preview"):
            return
        preview_body = self.window.message_input.toPlainText()
        preview_body = preview_body.replace("{nome}", "Maria Souza")
        preview_body = preview_body.replace("{codigos}", "1234, 5678")
        preview_body = preview_body.replace("{remetente}", "escola@example.com")
        preview_body = preview_body.replace("{destinatario}", "maria@example.com")
        html = markdown_to_html(preview_body)
        self.window.message_preview.setHtml(
            f'<div style="font-family: Segoe UI; color: #27312b; padding: 14px;">{html}</div>'
        )
