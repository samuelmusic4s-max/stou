"""Calendario: cuándo.

El mes a la izquierda, el día elegido a la derecha. Los días con carga se marcan por
color, y el panel del día explica qué se puede crear ahí en lugar de quedarse en
blanco.
"""

from __future__ import annotations

from datetime import date, datetime, time

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QCalendarWidget,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from stou.application.dto import CalendarEntry
from stou.domain.events import (
    ExamCreated,
    ExamRecorded,
    TaskCompleted,
    TaskCreated,
    TaskDeleted,
    TaskScheduled,
    TaskStatusChanged,
    TaskUpdated,
)
from stou.presentation.qt import motion
from stou.presentation.qt.theme import COLORS, SPACE, relative_day
from stou.presentation.services import AppServices
from stou.presentation.widgets.components import (
    GLYPH,
    Card,
    EmptyState,
    SectionHeader,
    label,
    pill,
)
from stou.presentation.widgets.dialogs import ExamDialog, RecordExamDialog, TaskDialog
from stou.shared.ids import EntityId

_DAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MONTHS = [
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


class CalendarView(QWidget):
    studyRequested = Signal(str)

    def __init__(self, services: AppServices, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._s = services
        self._entries: dict[date, list[CalendarEntry]] = {}
        self._selected_exam: EntityId | None = None
        self._build_ui()
        self._connect_events()
        self.refresh()

    # --- construcción ---------------------------------------------------------

    def _build_ui(self) -> None:
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(label("TU AGENDA", "Eyebrow"))
        titles.addWidget(label("Calendario", "H1"))

        header = QHBoxLayout()
        header.addLayout(titles, 1)

        self._calendar = QCalendarWidget()
        self._calendar.setGridVisible(False)
        self._calendar.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
        )
        self._calendar.setNavigationBarVisible(True)
        self._calendar.currentPageChanged.connect(lambda *_: self.refresh())
        self._calendar.selectionChanged.connect(self._refresh_day)

        month_card = Card(padding=SPACE["lg"])
        month_card.add(
            SectionHeader(
                "Mes",
                subtitle="Azul: tareas con fecha. Rojo: exámenes. Haz clic en un día.",
            )
        )
        month_card.add(self._calendar, 1)

        self._day_column = QVBoxLayout()
        self._day_column.setContentsMargins(0, 0, 0, 0)
        self._day_column.setSpacing(SPACE["sm"])
        day_holder = QWidget()
        day_holder.setLayout(self._day_column)

        day_scroll = QScrollArea()
        day_scroll.setWidgetResizable(True)
        day_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        day_scroll.setWidget(day_holder)

        new_task = QPushButton("Nueva tarea este día")
        new_task.setObjectName("Primary")
        new_task.setCursor(Qt.CursorShape.PointingHandCursor)
        new_task.clicked.connect(lambda: self.create_task())

        new_exam = QPushButton("Nuevo examen…")
        new_exam.setCursor(Qt.CursorShape.PointingHandCursor)
        new_exam.clicked.connect(lambda: self.create_exam())

        actions = QHBoxLayout()
        actions.setSpacing(SPACE["sm"])
        actions.addWidget(new_task, 1)
        actions.addWidget(new_exam)
        actions_holder = QWidget()
        actions_holder.setLayout(actions)

        self._day_card = Card(padding=SPACE["lg"])
        self._day_header = SectionHeader("Día")
        self._day_card.add(self._day_header)
        self._day_card.add(day_scroll, 1)
        self._day_card.add(actions_holder)
        self._day_card.setMinimumWidth(360)

        body = QSplitter(Qt.Orientation.Horizontal)
        body.addWidget(month_card)
        body.addWidget(self._day_card)
        body.setStretchFactor(0, 3)
        body.setStretchFactor(1, 2)
        body.setSizes([700, 420])

        column = QVBoxLayout(self)
        column.setContentsMargins(SPACE["xl"], SPACE["xl"], SPACE["xl"], SPACE["xl"])
        column.setSpacing(SPACE["lg"])
        column.addLayout(header)
        column.addWidget(body, 1)

    def _connect_events(self) -> None:
        self._s.events.on(
            (
                TaskCreated,
                TaskUpdated,
                TaskDeleted,
                TaskScheduled,
                TaskStatusChanged,
                TaskCompleted,
                ExamCreated,
                ExamRecorded,
            ),
            lambda _e: self.refresh(),
        )

    # --- datos ----------------------------------------------------------------

    def refresh(self) -> None:
        self._entries = self._s.calendar_month.execute(
            year=self._calendar.yearShown(), month=self._calendar.monthShown()
        )
        self._paint_month()
        self._refresh_day()

    def _paint_month(self) -> None:
        self._calendar.setDateTextFormat(QDate(), QTextCharFormat())
        for day, entries in self._entries.items():
            fmt = QTextCharFormat()
            has_exam = any(entry.exam for entry in entries)
            fmt.setBackground(
                QBrush(QColor(COLORS["danger_soft"] if has_exam else COLORS["accent_soft"]))
            )
            fmt.setForeground(QBrush(QColor(COLORS["text"])))
            names = [
                entry.exam.title if entry.exam else (entry.task.title if entry.task else "")
                for entry in entries
            ]
            fmt.setToolTip("\n".join(name for name in names if name))
            self._calendar.setDateTextFormat(QDate(day.year, day.month, day.day), fmt)

    def _selected_date(self) -> date:
        raw = self._calendar.selectedDate()
        return date(raw.year(), raw.month(), raw.day())

    def _refresh_day(self) -> None:
        while self._day_column.count():
            item = self._day_column.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        day = self._selected_date()
        entries = self._entries.get(day, [])
        self._selected_exam = None

        pretty = f"{_DAYS[day.weekday()]} {day.day} de {_MONTHS[day.month - 1]}"
        self._day_header.set_subtitle(
            f"{pretty} · {len(entries)} actividad(es)" if entries else pretty
        )

        if not entries:
            self._day_column.addWidget(
                EmptyState(
                    glyph=GLYPH["calendar"],
                    title="Nada este día",
                    body="Pon aquí una tarea para repartir el estudio, o registra un examen "
                    "con los capítulos que cubre: al aprobarlo, ese material se archiva.",
                )
            )
            return

        widgets: list[QWidget] = []
        for entry in entries:
            if entry.exam is not None:
                widget = _ExamRow(entry, on_record=self.record_exam)
                if self._selected_exam is None:
                    self._selected_exam = entry.exam.id
            elif entry.task is not None:
                widget = _TaskRow(entry, on_study=self.studyRequested.emit)
            else:
                continue
            self._day_column.addWidget(widget)
            widgets.append(widget)
        self._day_column.addStretch(1)
        motion.stagger(widgets, step=35, distance=8)

    # --- acciones -------------------------------------------------------------

    def create_task(self) -> EntityId | None:
        day = self._selected_date()
        default_due = datetime.combine(day, time(hour=20)).astimezone()
        dialog = TaskDialog(
            self._s.category_tree.execute(), parent=self, default_due=default_due
        )
        if dialog.exec() != TaskDialog.DialogCode.Accepted:
            return None
        data = dialog.data()
        if not data.title:
            QMessageBox.information(
                self, "Falta el título", "Una tarea necesita al menos un título."
            )
            return None
        try:
            return self._s.create_task.execute(
                title=data.title,
                description=data.description,
                category_id=data.category_id,
                priority=data.priority,
                due_at=data.due_at,
                estimated_minutes=data.estimated_minutes,
            )
        except Exception as exc:
            QMessageBox.warning(self, "No se pudo crear la tarea", str(exc))
            return None

    def create_exam(self) -> EntityId | None:
        day = self._selected_date()
        sections = self._s.suggest_sections.execute(category_id=None)
        if not sections:
            QMessageBox.information(
                self,
                "Todavía no hay temario posible",
                "Un examen cubre secciones de tu material. Sube material y divídelo en "
                "capítulos; después podrás elegir qué entra en el examen.",
            )
            return None

        dialog = ExamDialog(
            self._s.category_tree.execute(),
            sections,
            parent=self,
            default_date=datetime.combine(day, time(hour=8)).astimezone(),
        )
        if dialog.exec() != ExamDialog.DialogCode.Accepted:
            return None
        if not dialog.title():
            QMessageBox.information(
                self, "Falta el título", "El examen necesita al menos un título."
            )
            return None
        return self._s.create_exam.execute(
            title=dialog.title(),
            category_id=dialog.category_id(),
            scheduled_at=dialog.scheduled_at(),
            section_ids=dialog.section_ids(),
        )

    def record_exam(self, exam_id: EntityId, title: str) -> None:
        dialog = RecordExamDialog(title, parent=self)
        if dialog.exec() != RecordExamDialog.DialogCode.Accepted:
            return
        try:
            archived = self._s.record_exam.execute(
                exam_id=exam_id, passed=dialog.passed(), score=dialog.score()
            )
        except Exception as exc:
            QMessageBox.warning(self, "No se pudo registrar", str(exc))
            return

        if dialog.passed():
            QMessageBox.information(
                self,
                "Temario archivado",
                f"Se archivaron {len(archived)} secciones.\n\nSalen del circuito activo, "
                "pero siguen consultables con «Ver archivado» en la biblioteca.",
            )
        else:
            QMessageBox.information(
                self,
                "El material sigue activo",
                "El temario queda disponible para el reintento. Puedes crear el reintento "
                "desde este mismo examen.",
            )

    def selected_exam_id(self) -> EntityId | None:
        return self._selected_exam

    def entries_for_selected_day(self) -> list[CalendarEntry]:
        return self._entries.get(self._selected_date(), [])


class _TaskRow(QWidget):
    def __init__(
        self, entry: CalendarEntry, *, on_study, parent: QWidget | None = None  # noqa: ANN001
    ) -> None:
        super().__init__(parent)
        task = entry.task
        assert task is not None
        row = QHBoxLayout(self)
        row.setContentsMargins(SPACE["md"], SPACE["sm"], SPACE["md"], SPACE["sm"])
        row.setSpacing(SPACE["md"])

        glyph = label(GLYPH["study"], "Dim")
        glyph.setFixedWidth(18)
        row.addWidget(glyph)

        texts = QVBoxLayout()
        texts.setSpacing(1)
        texts.addWidget(label(task.title, "H3"))
        texts.addWidget(label(task.category_path, "Faint"))
        row.addLayout(texts, 1)

        if task.overdue:
            row.addWidget(pill("atrasada", "Danger"))

        button = QPushButton("Estudiar")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda: on_study(task.id))
        row.addWidget(button)


class _ExamRow(QWidget):
    def __init__(
        self, entry: CalendarEntry, *, on_record, parent: QWidget | None = None  # noqa: ANN001
    ) -> None:
        super().__init__(parent)
        exam = entry.exam
        assert exam is not None
        row = QHBoxLayout(self)
        row.setContentsMargins(SPACE["md"], SPACE["sm"], SPACE["md"], SPACE["sm"])
        row.setSpacing(SPACE["md"])

        glyph = label(GLYPH["exam"], "Dim")
        glyph.setFixedWidth(18)
        row.addWidget(glyph)

        texts = QVBoxLayout()
        texts.setSpacing(1)
        texts.addWidget(label(exam.title, "H3"))
        texts.addWidget(
            label(f"{exam.category_path} · {exam.section_count} secciones", "Faint")
        )
        row.addLayout(texts, 1)

        recorded = exam.result.value != "pending"
        if recorded:
            row.addWidget(
                pill(
                    "aprobado" if exam.result.value == "passed" else "reprobado",
                    "Ok" if exam.result.value == "passed" else "Danger",
                )
            )
        else:
            if exam.scheduled_at is not None:
                row.addWidget(
                    pill(relative_day(exam.scheduled_at, datetime.now().astimezone()), "Warn")
                )
            button = QPushButton("Registrar resultado")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda: on_record(exam.id, exam.title))
            row.addWidget(button)
