"""Animacoes da aba de sorteio.

A escolha do vencedor permanece em ``code_gen.core.draw_item``; este modulo
adiciona apenas o efeito "caca-niqueis" (itens passando e desacelerando) e o
confete de celebracao ao final, sem tocar nos dados ou no estado real.
"""

from __future__ import annotations

import math
import random

from PyQt6.QtCore import QEvent, QObject, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QWidget


class SorteioRevealAnimator(QObject):
    """Anima a revelacao de um vencedor com efeito de roleta desacelerando.

    Decide a lista de itens intermediarios (dica: passe o pool sem o vencedor
    para manter a surpresa) e emite ``tick`` a cada passo crescente. No ultimo
    passo, emite ``finished`` com o vencedor real.
    """

    tick = pyqtSignal(str)
    finished = pyqtSignal(str)

    START_INTERVAL_MS = 60
    END_INTERVAL_MS = 300
    STEPS = 20

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._pool: list[str] = []
        self._winner = ""
        self._rng: random.Random | None = None
        self._step = 0
        self._running = False

    def start(self, pool: list[str], winner: str, rng: random.Random | None = None) -> None:
        """Inicia a animacao, sorteando itens intermediarios de *pool*."""
        self._pool = list(pool)
        self._winner = winner
        self._rng = rng or random.Random()
        self._step = 0
        self._running = True
        self._schedule_next()

    def stop(self) -> None:
        """Cancela a animacao antes de terminar."""
        self._running = False
        self._timer.stop()
        self._pool = []
        self._winner = ""

    def _interval_for(self, step: int) -> int:
        """Intervalo crescente com easing quadratico para desacelerar a roleta."""
        progress = step / max(1, self.STEPS - 1)
        return self.START_INTERVAL_MS + round(
            (self.END_INTERVAL_MS - self.START_INTERVAL_MS) * progress * progress
        )

    def _schedule_next(self) -> None:
        self._timer.start(self._interval_for(self._step))

    def _on_tick(self) -> None:
        if not self._running or not self._winner:
            return
        rng = self._rng or random.Random()
        item = rng.choice(self._pool) if self._pool else self._winner
        self._step += 1
        if self._step >= self.STEPS:
            self._timer.stop()
            self._running = False
            self.finished.emit(self._winner)
            return
        self.tick.emit(item)
        self._schedule_next()


class ConfettiWidget(QWidget):
    """Camada transparente que desenha confete caindo sobre o frame de resultado."""

    COLORS = ["#e8752b", "#f7c59f", "#8fbf6b", "#5b8def", "#f2c94c", "#d94f8f"]

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._particles: list[dict] = []
        self._frame = 0
        self._max_frames = 60
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        parent.installEventFilter(self)
        self.setGeometry(parent.rect())

    def start(
        self,
        count: int = 30,
        frames: int = 60,
        particle_scale: float = 1.0,
        speed_scale: float = 1.0,
    ) -> None:
        """Dispara a queda de confete com duracao e escala ajustaveis."""
        if self._timer.isActive():
            self._timer.stop()
        rng = random.Random()
        self._max_frames = max(1, frames)
        self._particles = [
            {
                "x": rng.random(),
                "y": -0.15 - rng.random() * 0.35,
                "speed": (0.5 + rng.random() * 1.2) * speed_scale,
                "wobble": rng.random() * math.tau,
                "size": (5 + rng.random() * 6) * particle_scale,
                "color": rng.choice(self.COLORS),
                "spin": rng.choice([-1.0, 1.0]),
            }
            for _ in range(count)
        ]
        self._frame = 0
        self.show()
        self.raise_()
        self._timer.start(30)

    def _advance(self) -> None:
        self._frame += 1
        for particle in self._particles:
            particle["y"] += particle["speed"] * 0.04
            particle["wobble"] += particle["spin"] * 0.3
        self.update()
        if self._frame >= self._max_frames:
            self._timer.stop()
            self.close()

    def eventFilter(self, watched: QWidget, event: QEvent) -> bool:  # type: ignore[override]
        if event.type() == QEvent.Type.Resize:
            self.setGeometry(watched.rect())
        return super().eventFilter(watched, event)

    def paintEvent(self, a0) -> None:  # noqa: N802 - API do Qt
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = self.width(), self.height()
        for particle in self._particles:
            x = (particle["x"] + 0.05 * math.sin(particle["wobble"])) * width
            y = particle["y"] * height
            size = particle["size"]
            painter.save()
            painter.translate(x, y)
            painter.rotate(particle["wobble"] * 30)
            painter.setBrush(QColor(particle["color"]))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(-size / 2, -size / 2, size, size * 0.6), 1, 1)
            painter.restore()
        painter.end()
