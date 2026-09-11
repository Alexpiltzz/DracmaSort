"""Janela dedicada ao streaming/gravacao do sorteio.

Exibe apenas o resultado do sorteio e o historico, sem controles,
para ser capturada em ferramentas de streaming (OBS, etc). Atualizada
automaticamente pela janela principal a cada sorteio.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QKeyEvent
from PyQt6.QtWidgets import (
    QFrame,
    QGroupBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from .animations import ConfettiWidget


class StreamingWindow(QWidget):
    """Janela flutuante minimalista focada no resultado do sorteio."""

    closed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sorteio - Tela")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.resize(720, 520)
        self.setMinimumSize(480, 360)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._result_frame = QFrame()
        self._result_frame.setObjectName("streaming_result_frame")
        self._result_frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame_layout = QVBoxLayout(self._result_frame)
        frame_layout.setContentsMargins(24, 24, 24, 24)
        frame_layout.setSpacing(0)

        self._title_label = QLabel("VENCEDOR")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setProperty("class", "stream-title")

        self._result_label = QLabel("Aguardando sorteio...")
        self._result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_label.setWordWrap(True)
        self._result_label.setProperty("class", "stream-result")
        font = self._result_label.font()
        font.setPointSize(36)
        font.setBold(True)
        self._result_label.setFont(font)

        center = QVBoxLayout()
        center.setSpacing(8)
        center.addWidget(self._title_label)
        center.addWidget(self._result_label)
        frame_layout.addStretch(1)
        frame_layout.addLayout(center)
        frame_layout.addStretch(1)

        root.addWidget(self._result_frame, 1)

        self._history_group = QGroupBox("Histórico")
        history_layout = QVBoxLayout(self._history_group)
        self._history_edit = QPlainTextEdit()
        self._history_edit.setObjectName("streaming_history")
        self._history_edit.setReadOnly(True)
        self._history_edit.setPlaceholderText("Itens sorteados aqui.")
        history_layout.addWidget(self._history_edit)
        root.addWidget(self._history_group, 0)

    def update_winner(self, text: str) -> None:
        """Atualiza o texto do vencedor exibido."""
        self._result_label.setText(text)

    def update_title(self, text: str) -> None:
        """Atualiza o titulo acima do resultado."""
        self._title_label.setText(text)

    def update_history(self, text: str) -> None:
        """Substitui o conteudo do historico."""
        self._history_edit.setPlainText(text)

    def reset(self) -> None:
        """Limpa resultado e historico."""
        self._title_label.setText("VENCEDOR")
        self._result_label.setText("Aguardando sorteio...")
        self._history_edit.clear()

    def apply_stream_style(self, qss: str) -> None:
        """Aplica uma folha de estilo com escopo reduzido a esta janela."""
        self.setStyleSheet(qss)

    def toggle_fullscreen(self) -> None:
        """Alterna entre tela cheia e modo janela."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def celebrate(self) -> None:
        """Dispara o confete reforçado sobre o resultado quando visível."""
        if self.isVisible():
            ConfettiWidget(self._result_frame).start(
                count=60,
                frames=100,
                particle_scale=1.4,
                speed_scale=0.7,
            )

    def set_codes_mode(self, is_codes: bool) -> None:
        """Ativa fonte dobrada quando o sorteio exibe códigos em vez de nomes."""
        self._result_label.setProperty("codes", is_codes)
        self._result_label.style().unpolish(self._result_label)
        self._result_label.style().polish(self._result_label)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Fecha ocultando a janela, mantendo o estado para reexibir."""
        self.closed.emit()
        self.hide()
        event.accept()
