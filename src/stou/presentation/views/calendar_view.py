"""Calendario de actividades: tareas con fecha y exámenes."""

from __future__ import annotations

from datetime import date, datetime, time

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QCalendarWidget,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from stou.application.dto import CalendarEntry
from stou.domain.events import (
    ExamCreated,
    ExamRecorded,
    TaskCreated,
    TaskDeleted,
    TaskScheduled,
    TaskStatusChanged,
    TaskUpdated,
)
from stou.presentation.services import AppServices
from stou.presentation.widgets.dialogs import ExamDialog, RecordExamDialog, TaskDialog
from stou.shared.ids import EntityId

ROLE_ENTRY = Qt.ItemDataRole.UserRole


class CalendarView(QWidget):
    studyRequested = Signal(str)

    def __init__(self, services: AppServices, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._s = services
        self._entries: dict[date, list[CalendarEntry]] = {}
        self._build_ui()
        self._connect_events()
        self.refresh()

    def _build_ui(self) -> None:
        title = QLabel("Calendario")
        title.setObjectName("Title")

        self._calendar = QCalendarWidget()
        self._calendar.setGridVisible(True)
        self._calendar.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
        )
        self._calendar.currentPageChanged.connect(lambda *_: self.refresh())
        self._calendar.selectionChanged.connect(self._refresh_day)

        self._day_label = QLabel()
        self._day_label.setObjectName("Subtitle")
        self._day_list = QListWidget()
        self._day_list.itemDoubleClicked.connect(self._open_entry)

        new_task = QPushButton("Nueva tarea en este día")
        new_task.setObjectName("Primary")
        new_task.clicked.connect(self._create_task)
        new_exam = QPushButton("Nuevo examen…")
        new_exam.clicked.connect(self._create_exam)
        record = QPushButton("Registrar resultado…")
        record.clicked.connect(self._record_exam)

        buttons = QHBoxLayout()
        buttons.addWidget(new_task)
        buttons.addWidget(new_exam)
        buttons.addWidget(record)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.addWidget(self._day_label)
        side_layout.addWidget(self._day_list, 1)
        side_layout.addLayout(buttons)
        side.setMaximumWidth(420)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._calendar)
        splitter.addWidget(side)
        splitter.setStretchFactor(0, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(splitter, 1)

    def _connect_events(self) -> None:
        self._s.events.on(
            (
                TaskCreated,
                TaskUpdated,
                TaskDeleted,
                TaskScheduled,
                TaskStatusChanged,
                ExamCreated,
                ExamRecorded,
            ),
            lambda _e: self.refresh(),
        )

    # --- datos ----------------------------------------------------------------

    def refresh(self) -> None:
        year = self._calendar.yearShown()
        month = self._calendar.monthShown()
        self._entries = self._s.calendar_month.execute(year=year, month=month)
        self._paint_days()
        self._refresh_day()

    def _paint_days(self) -> None:
        self._calendar.setDateTextFormat(QDate(), QTextCharFormat())
        for day, entries in self._entries.items():
            fmt = QTextCharFormat()
            has_exam = any(e.exam for e in entries)
            fmt.setBackground(QBrush(QColor("#4A2F35" if has_exam else "#243044")))
            fmt.setForeground(QBrush(QColor("#E6E8EC")))
            fmt.setToolTip(
                "\n".join(
                    (e.exam.title if e.exam else e.task.title if e.task else "") for e in entries
                )
            )
            self._calendar.setDateTextFormat(QDate(day.year, day.month, day.day), fmt)

    def _selected_date(self) -> date:
        qdate = self._calendar.selectedDate()
        return date(qdate.year(), qdate.month(), qdate.day())

    def _refresh_day(self) -> None:
        day = self._selected_date()
        entries = self._entries.get(day, [])
        self._day_label.setText(f"{day.strftime('%A %d/%m/%Y')} · {len(entries)} actividad(es)")
        self._day_list.clear()
        for entry in entries:
            if entry.exam is not None:
                label = f"📝  Examen: {entry.exam.title}  ·  {entry.exam.section_count} secciones"
            elif entry.task is not None:
                label = f"•  {entry.task.title}  ·  {entry.task.category_path}"
            else:
                continue
            item = QListWidgetItem(label)
            item.setData(ROLE_ENTRY, entry)
            self._day_list.addItem(item)

    # --- acciones -------------------------------------------------------------

    def _open_entry(self, item: QListWidgetItem) -> None:
        entry: CalendarEntry = item.data(ROLE_ENTRY)
        if entry.task is not None:
            self.studyRequested.emit(entry.task.id)

    def _create_task(self) -> None:
        day = self._selected_date()
        default_due = datetime.combine(day, time(hour=20)).astimezone()
        dialog = TaskDialog(
            self._s.category_tree.execute(), parent=self, default_due=default_due
        )
        if dialog.exec() != TaskDialog.DialogCode.Accepted:
            return
        data = dialog.data()
        if not data.title:
            return
        self._s.create_task.execute(
            title=data.title,
            description=data.description,
            category_id=data.category_id,
            priority=data.priority,
            due_at=data.due_at,
            estimated_minutes=data.estimated_minutes,
        )

    def _create_exam(self) -> None:
        day = self._selected_date()
        sections = self._s.suggest_sections.execute(category_id=None)
        dialog = ExamDialog(
            self._s.category_tree.execute(),
            sections,
            parent=self,
            default_date=datetime.combine(day, time(hour=8)).astimezone(),
        )
        if dialog.exec() != ExamDialog.DialogCode.Accepted:
            return
        if not dialog.title():
            return
        self._s.create_exam.execute(
            title=dialog.title(),
            category_id=dialog.category_id(),
            scheduled_at=dialog.scheduled_at(),
            section_ids=dialog.section_ids(),
        )

    def _record_exam(self) -> None:
        item = self._day_list.currentItem()
        entry: CalendarEntry | None = item.data(ROLE_ENTRY) if item else None
        if entry is None or entry.exam is None:
            QMessageBox.information(
                self, "Registrar resultado", "Selecciona un examen del día."
            )
            return
        dialog = RecordExamDialog(entry.exam.title, parent=self)
        if dialog.exec() != RecordExamDialog.DialogCode.Accepted:
            return
        try:
            archived = self._s.record_exam.execute(
                exam_id=entry.exam.id, passed=dialog.passed(), score=dialog.score()
            )
        except Exception as exc:
            QMessageBox.warning(self, "No se pudo registrar", str(exc))
            return
        if dialog.passed():
            QMessageBox.information(
                self,
                "Temario archivado",
                f"Se archivaron {len(archived)} secciones. Siguen consultables desde "
                "«Ver archivado» en la biblioteca.",
            )
        else:
            QMessageBox.information(
                self,
                "Material sigue activo",
                "El temario permanece activo para el reintento.",
            )

    def selected_exam_id(self) -> EntityId | None:
        item = self._day_list.currentItem()
        entry: CalendarEntry | None = item.data(ROLE_ENTRY) if item else None
        return entry.exam.id if entry and entry.exam else None
