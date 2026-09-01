"""Rejilla de mes propia.

Sustituye a ``QCalendarWidget``, que traía tres problemas que no se arreglan con
hoja de estilos:

1. **Las celdas crecían con la ventana** hasta ser cajones enormes con un número
   diminuto en el medio. Aquí la altura de fila está acotada: el calendario ocupa lo
   que necesita y devuelve el resto del espacio a la pantalla.
2. **No se podía mostrar qué hay cada día.** Pintar el fondo del día no dice si es
   una tarea o un examen. Aquí cada celda lleva sus actividades escritas.
3. Empezaba la semana en domingo y pintaba el fin de semana en rojo, que en esta
   aplicación es el color de «examen» y de «atrasado».
"""

from __future__ import annotations

import calendar
from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from stou.application.dto import CalendarEntry
from stou.presentation.qt.theme import SPACE
from stou.presentation.widgets.components import label

WEEKDAYS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
MONTHS = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]

ROW_HEIGHT = 86
MAX_CHIPS = 2


class _DayCell(QFrame):
    """Un día. Clicable, con el número legible y lo que hay ese día."""

    clicked = Signal(object)  # date

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._day: date | None = None
        self._in_month = True
        self.setObjectName("DayCell")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(ROW_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(SPACE["sm"], SPACE["xs"], SPACE["sm"], SPACE["xs"])
        self._column.setSpacing(2)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        self._number = label("", "DayNumber")
        head.addWidget(self._number)
        head.addStretch(1)
        self._badge = label("", "Faint")
        head.addWidget(self._badge)
        self._column.addLayout(head)

        self._chips = QVBoxLayout()
        self._chips.setContentsMargins(0, 0, 0, 0)
        self._chips.setSpacing(2)
        self._column.addLayout(self._chips)
        self._column.addStretch(1)

    def set_day(
        self,
        day: date,
        entries: list[CalendarEntry],
        *,
        in_month: bool,
        today: date,
        selected: bool,
    ) -> None:
        self._day = day
        self._in_month = in_month

        while self._chips.count():
            item = self._chips.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        role = "DayNumber"
        if not in_month:
            role = "DayNumberMuted"
        elif day == today:
            role = "DayNumberToday"
        self._number.setObjectName(role)
        self._number.setText(str(day.day))
        self._repolish(self._number)

        exams = [entry for entry in entries if entry.exam is not None]
        tasks = [entry for entry in entries if entry.task is not None]
        # El examen manda: es la fecha que no se mueve.
        ordered = exams + tasks

        self._badge.setText(str(len(ordered)) if len(ordered) > MAX_CHIPS else "")

        for entry in ordered[:MAX_CHIPS]:
            if entry.exam is not None:
                chip = label(entry.exam.title, "ChipExam")
            else:
                assert entry.task is not None
                tone = "ChipLate" if entry.task.overdue else "Chip"
                chip = label(entry.task.title, tone)
            chip.setToolTip(chip.text())
            self._chips.addWidget(chip)

        if len(ordered) > MAX_CHIPS:
            self._chips.addWidget(label(f"+{len(ordered) - MAX_CHIPS} más", "Faint"))

        name = "DayCell"
        if selected:
            name = "DayCellSelected"
        elif not in_month:
            name = "DayCellOutside"
        elif ordered:
            name = "DayCellBusy"
        self.setObjectName(name)
        self._repolish(self)

        self.setToolTip(
            "\n".join(
                entry.exam.title if entry.exam else (entry.task.title if entry.task else "")
                for entry in ordered
            )
        )

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001, N802 - API de Qt
        if event.button() == Qt.MouseButton.LeftButton and self._day is not None:
            self.clicked.emit(self._day)
        super().mouseReleaseEvent(event)


class MonthGrid(QWidget):
    """Mes completo en seis filas. Emite el día que el usuario elige."""

    daySelected = Signal(object)  # date

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        today = date.today()
        self._year = today.year
        self._month = today.month
        self._selected = today
        self._entries: dict[date, list[CalendarEntry]] = {}

        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(SPACE["xs"])
        self._grid.setVerticalSpacing(SPACE["xs"])

        for column, name in enumerate(WEEKDAYS):
            head = label(name.upper(), "Eyebrow", align=Qt.AlignmentFlag.AlignCenter)
            self._grid.addWidget(head, 0, column)
            self._grid.setColumnStretch(column, 1)

        self._cells: list[_DayCell] = []
        for index in range(42):
            cell = _DayCell()
            # Envuelta en lambda aunque `clicked` aquí sea una señal propia con un
            # argumento: la regla del proyecto es que ninguna señal `clicked` se
            # conecte directamente a un método con parámetros.
            cell.clicked.connect(lambda day: self._on_cell(day))
            self._grid.addWidget(cell, 1 + index // 7, index % 7)
            self._cells.append(cell)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    # --- estado ---------------------------------------------------------------

    @property
    def year(self) -> int:
        return self._year

    @property
    def month(self) -> int:
        return self._month

    @property
    def selected(self) -> date:
        return self._selected

    def month_label(self) -> str:
        return f"{MONTHS[self._month - 1]} de {self._year}"

    def show_month(self, year: int, month: int) -> None:
        self._year = year
        self._month = month
        self._paint()

    def shift_month(self, delta: int) -> None:
        month = self._month + delta
        year = self._year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        self.show_month(year, month)

    def go_to_today(self) -> None:
        today = date.today()
        self._selected = today
        self.show_month(today.year, today.month)
        self.daySelected.emit(today)

    def select(self, day: date) -> None:
        self._selected = day
        if (day.year, day.month) != (self._year, self._month):
            self.show_month(day.year, day.month)
        else:
            self._paint()

    def set_entries(self, entries: dict[date, list[CalendarEntry]]) -> None:
        self._entries = entries
        self._paint()

    # --- pintado --------------------------------------------------------------

    def _paint(self) -> None:
        today = date.today()
        first = date(self._year, self._month, 1)
        # La semana empieza en lunes: weekday() ya devuelve 0 para lunes.
        offset = first.weekday()
        days_in_month = calendar.monthrange(self._year, self._month)[1]

        for index, cell in enumerate(self._cells):
            ordinal = index - offset + 1
            if 1 <= ordinal <= days_in_month:
                day = date(self._year, self._month, ordinal)
                in_month = True
            else:
                day = first.toordinal() + ordinal - 1
                day = date.fromordinal(max(1, day))
                in_month = False
            cell.set_day(
                day,
                self._entries.get(day, []) if in_month else [],
                in_month=in_month,
                today=today,
                selected=in_month and day == self._selected,
            )

    def _on_cell(self, day: date) -> None:
        self._selected = day
        if (day.year, day.month) != (self._year, self._month):
            self.show_month(day.year, day.month)
        else:
            self._paint()
        self.daySelected.emit(day)
