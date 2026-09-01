"""Calendario: cuándo.

El mes a la izquierda, el día elegido a la derecha. Los días con carga se marcan por
color, y el panel del día explica qué se puede crear ahí en lugar de quedarse en
blanco.
"""

from __future__ import annotations

from datetime import date, datetime, time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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
from stou.presentation.qt.theme import SPACE, relative_day
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
from stou.presentation.widgets.month_grid import MonthGrid
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

        self._grid = MonthGrid()
        self._grid.daySelected.connect(lambda _day: self._refresh_day())

        self._month_label = label(self._grid.month_label().capitalize(), "H2")
        previous = QPushButton("‹")
        previous.setObjectName("Step")
        previous.setCursor(Qt.CursorShape.PointingHandCursor)
        previous.clicked.connect(lambda: self._shift(-1))
        following = QPushButton("›")
        following.setObjectName("Step")
        following.setCursor(Qt.CursorShape.PointingHandCursor)
        following.clicked.connect(lambda: self._shift(1))
        today_button = QPushButton("Hoy")
        today_button.setObjectName("Ghost")
        today_button.setCursor(Qt.CursorShape.PointingHandCursor)
        today_button.clicked.connect(lambda: self._go_today())

        month_bar = QHBoxLayout()
        month_bar.setSpacing(SPACE["sm"])
        month_bar.addWidget(self._month_label)
        month_bar.addStretch(1)
        month_bar.addWidget(today_button)
        month_bar.addWidget(previous)
        month_bar.addWidget(following)
        month_bar_holder = QWidget()
        month_bar_holder.setLayout(month_bar)

        month_card = Card(padding=SPACE["lg"])
        month_card.add(month_bar_holder)
        month_card.add(self._grid)
        month_card.add(
            label(
                "Azul: tareas con fecha.  ·  Ámbar: exámenes.  ·  Rojo: atrasado.",
                "Faint",
            )
        )
        # La tarjeta del mes ocupa lo que necesita: el calendario ya no se estira hasta
        # dejar celdas enormes con un número diminuto dentro.
        month_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

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
        self._day_card.setMinimumWidth(340)
        self._day_card.setMaximumWidth(460)

        # Rail derecho: el día elegido y, debajo, lo que no se puede mover de sitio.
        self._exams_card = Card(padding=SPACE["lg"])
        self._exams_card.add(
            SectionHeader("Próximos exámenes", subtitle="Las fechas que no se mueven.")
        )
        self._exams_column = QVBoxLayout()
        self._exams_column.setContentsMargins(0, 0, 0, 0)
        self._exams_column.setSpacing(SPACE["xs"])
        exams_holder = QWidget()
        exams_holder.setLayout(self._exams_column)
        self._exams_card.add(exams_holder)
        self._exams_card.setMinimumWidth(340)
        self._exams_card.setMaximumWidth(460)

        right = QVBoxLayout()
        right.setSpacing(SPACE["lg"])
        right.addWidget(self._day_card, 3)
        right.addWidget(self._exams_card, 2)

        body = QHBoxLayout()
        body.setSpacing(SPACE["lg"])
        left = QVBoxLayout()
        left.setSpacing(SPACE["lg"])
        left.addWidget(month_card)
        left.addStretch(1)
        body.addLayout(left, 3)
        body.addLayout(right, 2)

        column = QVBoxLayout(self)
        column.setContentsMargins(SPACE["xl"], SPACE["xl"], SPACE["xl"], SPACE["xl"])
        column.setSpacing(SPACE["lg"])
        column.addLayout(header)
        column.addLayout(body, 1)

    def _shift(self, delta: int) -> None:
        self._grid.shift_month(delta)
        self._month_label.setText(self._grid.month_label().capitalize())
        self.refresh()

    def _go_today(self) -> None:
        self._grid.go_to_today()
        self._month_label.setText(self._grid.month_label().capitalize())
        self.refresh()

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
            year=self._grid.year, month=self._grid.month
        )
        self._grid.set_entries(self._entries)
        self._month_label.setText(self._grid.month_label().capitalize())
        self._refresh_day()
        self._refresh_exams()

    def _refresh_exams(self) -> None:
        while self._exams_column.count():
            item = self._exams_column.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        now = datetime.now().astimezone()
        exams = self._s.list_exams.execute(scheduled_from=now, pending_only=True)
        if not exams:
            self._exams_column.addWidget(
                EmptyState(
                    glyph=GLYPH["exam"],
                    title="Sin exámenes por delante",
                    body="Registra uno y elige qué capítulos cubre: al aprobarlo, ese "
                    "material se archiva solo.",
                )
            )
            return
        for exam in exams[:5]:
            row = QWidget()
            line = QHBoxLayout(row)
            line.setContentsMargins(0, SPACE["xs"], 0, SPACE["xs"])
            line.setSpacing(SPACE["sm"])
            texts = QVBoxLayout()
            texts.setSpacing(1)
            texts.addWidget(label(exam.title, "H3"))
            texts.addWidget(
                label(f"{exam.category_path} · {exam.section_count} secciones", "Faint")
            )
            line.addLayout(texts, 1)
            if exam.scheduled_at is not None:
                line.addWidget(pill(relative_day(exam.scheduled_at, now), "Warn"))
            self._exams_column.addWidget(row)
        self._exams_column.addStretch(1)

    def _selected_date(self) -> date:
        return self._grid.selected

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
