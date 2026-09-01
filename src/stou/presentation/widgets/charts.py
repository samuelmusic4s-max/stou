"""Gráficos dibujados a mano.

Son dos y hacen falta los dos, pero por razones distintas:

- ``ActivityChart`` responde «¿he sido constante?». Un número no puede responder eso:
  cinco horas repartidas en cinco días y cinco horas en un atracón dan el mismo total
  y significan cosas opuestas.
- ``SubjectBars`` responde «¿a qué le estoy dedicando el tiempo?». Comparar materias
  se hace con longitudes, no leyendo cifras una por una.

Se pintan con QPainter en lugar de traer una librería de gráficas: son dos formas
simples y una dependencia nueva costaría más de lo que ahorra.
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from stou.application.dto import DayTime
from stou.presentation.qt.theme import COLORS, SPACE, TYPE, format_duration_short
from stou.presentation.widgets.components import label

_WEEKDAY_INITIAL = ["L", "M", "M", "J", "V", "S", "D"]


class ActivityChart(QWidget):
    """Barras de tiempo por día. El día de hoy va marcado."""

    def __init__(self, *, height: int = 170, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data: list[DayTime] = []
        self._today: date | None = None
        self.setMinimumHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, data: list[DayTime], *, today: date | None = None) -> None:
        self._data = list(data)
        self._today = today
        self.setToolTip(
            "\n".join(
                f"{item.day.strftime('%d/%m')}: {format_duration_short(item.seconds)}"
                for item in self._data
                if item.seconds
            )
            or "Sin tiempo registrado en este período."
        )
        self.update()

    @property
    def has_data(self) -> bool:
        """¿Hay algo que mirar? Un período entero en cero no es un gráfico."""
        return any(item.seconds for item in self._data)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - API de Qt
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        axis_height = 22
        plot_height = max(10, height - axis_height - 6)

        # Línea de base: sin ella las barras cortas parecen flotar.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS["line"]))
        painter.drawRect(QRectF(0, plot_height + 1, width, 1))

        if not self._data:
            painter.setPen(QColor(COLORS["text_faint"]))
            painter.drawText(
                QRectF(0, 0, width, plot_height),
                Qt.AlignmentFlag.AlignCenter,
                "Sin tiempo registrado todavía",
            )
            return

        peak = max((item.seconds for item in self._data), default=0)
        count = len(self._data)
        slot = width / count
        bar_width = min(34.0, max(6.0, slot * 0.52))

        small = QFont(self.font())
        small.setPointSizeF(max(7.5, small.pointSizeF() - 1.5))

        for index, item in enumerate(self._data):
            center = slot * (index + 0.5)
            is_today = self._today is not None and item.day == self._today
            ratio = (item.seconds / peak) if peak else 0.0
            bar_height = max(3.0, ratio * (plot_height - 14)) if item.seconds else 3.0

            rect = QRectF(
                center - bar_width / 2, plot_height - bar_height, bar_width, bar_height
            )
            radius = min(6.0, bar_width / 2)

            painter.setPen(Qt.PenStyle.NoPen)
            if not item.seconds:
                # Un día en cero se dibuja: es información, no un hueco.
                painter.setBrush(QColor(COLORS["surface_3"]))
            elif is_today:
                painter.setBrush(QColor(COLORS["accent"]))
            else:
                painter.setBrush(QColor(COLORS["warm"]))
            painter.drawRoundedRect(rect, radius, radius)

            painter.setFont(small)
            painter.setPen(
                QColor(COLORS["text"] if is_today else COLORS["text_faint"])
            )
            painter.drawText(
                QRectF(center - slot / 2, plot_height + 4, slot, axis_height / 2),
                Qt.AlignmentFlag.AlignCenter,
                _WEEKDAY_INITIAL[item.day.weekday()],
            )
            # El número del día solo cada tres, o se convierte en ruido.
            if index % 3 == 0 or is_today:
                painter.setPen(QColor(COLORS["text_faint"]))
                painter.drawText(
                    QRectF(center - slot / 2, plot_height + 4 + axis_height / 2, slot, 12),
                    Qt.AlignmentFlag.AlignCenter,
                    str(item.day.day),
                )

            # La cifra solo sobre el máximo: etiquetar todo es no etiquetar nada.
            if item.seconds and item.seconds == peak:
                painter.setFont(small)
                painter.setPen(QColor(COLORS["text_dim"]))
                painter.drawText(
                    QRectF(center - slot / 2, rect.top() - 15, slot, 14),
                    Qt.AlignmentFlag.AlignCenter,
                    format_duration_short(item.seconds),
                )


class Track(QWidget):
    """Barra horizontal proporcional. Comparar sin leer cifras."""

    def __init__(self, ratio: float, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ratio = max(0.0, min(1.0, ratio))
        self._color = color
        self.setFixedHeight(8)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - API de Qt
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        radius = self.height() / 2
        painter.setBrush(QColor(COLORS["surface_3"]))
        painter.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), radius, radius)
        if self._ratio > 0:
            painter.setBrush(QColor(self._color))
            painter.drawRoundedRect(
                QRectF(0, 0, max(8.0, self.width() * self._ratio), self.height()),
                radius,
                radius,
            )


class SubjectRow(QWidget):
    """Una materia: punto de color, nombre, barra y cifra."""

    def __init__(
        self,
        *,
        title: str,
        value: str,
        ratio: float,
        color: str,
        note: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 3, 0, 3)
        column.setSpacing(2)

        top = QHBoxLayout()
        top.setSpacing(SPACE["sm"])
        top.addWidget(_Dot(color))
        top.addWidget(label(title, "H3"), 1)
        top.addWidget(label(value, "Dim"))
        column.addLayout(top)
        column.addWidget(Track(ratio, color))
        if note:
            column.addWidget(label(note, "Faint"))


class _Dot(QWidget):
    """Punto de color de la materia. Ata la fila con su color en el resto de la app."""

    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self.setFixedSize(10, 10)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - API de Qt
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._color))
        painter.drawEllipse(0, 1, 9, 9)


class SubjectBars(QWidget):
    """Lista de materias comparables entre sí."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(SPACE["xs"])

    def clear(self) -> None:
        while self._column.count():
            item = self._column.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def add(self, widget: QWidget) -> None:
        self._column.addWidget(widget)

    def set_rows(self, rows: list[SubjectRow]) -> None:
        self.clear()
        for row in rows:
            self._column.addWidget(row)

    @property
    def count(self) -> int:
        return self._column.count()


def type_scale(role: str) -> int:
    """Acceso a la escala tipográfica para quien pinta a mano."""
    return int(TYPE.get(role, TYPE["body"]))
