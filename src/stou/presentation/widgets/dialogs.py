"""Diálogos reutilizables: crear o editar tarea, asignar material, registrar examen."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from stou.application.dto import CategoryNode, SectionRow, TaskDetail
from stou.domain.values import Priority
from stou.shared.ids import EntityId

PRIORITY_LABEL = {
    Priority.LOW: "Baja",
    Priority.NORMAL: "Normal",
    Priority.HIGH: "Alta",
}


def category_combo(
    nodes: tuple[CategoryNode, ...], *, allow_none: bool = True
) -> QComboBox:
    combo = QComboBox()
    if allow_none:
        combo.addItem("Sin categoría", None)

    def add(node: CategoryNode, depth: int) -> None:
        combo.addItem("    " * depth + node.name, node.id)
        for child in node.children:
            add(child, depth + 1)

    for node in nodes:
        add(node, 0)
    return combo


@dataclass(frozen=True, slots=True)
class TaskFormData:
    title: str
    description: str
    category_id: EntityId | None
    priority: Priority
    due_at: datetime | None
    estimated_minutes: int | None


class TaskDialog(QDialog):
    def __init__(
        self,
        categories: tuple[CategoryNode, ...],
        *,
        parent: QWidget | None = None,
        detail: TaskDetail | None = None,
        default_category: EntityId | None = None,
        default_due: datetime | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar tarea" if detail else "Nueva tarea")
        self.setMinimumWidth(460)

        self._title = QLineEdit(detail.task.title if detail else "")
        self._title.setPlaceholderText("Qué hay que estudiar")
        self._description = QPlainTextEdit(detail.description if detail else "")
        self._description.setPlaceholderText("Detalles, objetivos, criterios…")
        self._description.setMaximumHeight(90)

        self._category = category_combo(categories)
        preselect = detail.task.category_id if detail else default_category
        if preselect:
            index = self._category.findData(preselect)
            if index >= 0:
                self._category.setCurrentIndex(index)

        self._priority = QComboBox()
        for priority, label in PRIORITY_LABEL.items():
            self._priority.addItem(label, priority)
        if detail:
            index = self._priority.findData(detail.task.priority)
            if index >= 0:
                self._priority.setCurrentIndex(index)
        else:
            self._priority.setCurrentIndex(1)

        self._has_due = QCheckBox("Con fecha límite")
        self._due = QDateTimeEdit()
        self._due.setCalendarPopup(True)
        self._due.setDisplayFormat("dd/MM/yyyy HH:mm")
        # Defensivo: una señal de Qt puede colar un bool aquí y no debe romper el
        # diálogo. Solo una fecha real preselecciona el campo.
        candidate = detail.task.due_at if detail else default_due
        base = candidate if isinstance(candidate, datetime) else None
        if base is not None:
            self._has_due.setChecked(True)
            self._due.setDateTime(QDateTime(base.astimezone()))
        else:
            self._due.setDateTime(QDateTime.currentDateTime().addDays(1))
            self._due.setEnabled(False)
        self._has_due.toggled.connect(self._due.setEnabled)

        self._estimated = QSpinBox()
        self._estimated.setRange(0, 60 * 24)
        self._estimated.setSuffix(" min")
        self._estimated.setSpecialValueText("sin estimar")
        if detail and detail.task.estimated_minutes:
            self._estimated.setValue(detail.task.estimated_minutes)

        form = QFormLayout()
        form.addRow("Título", self._title)
        form.addRow("Descripción", self._description)
        form.addRow("Categoría", self._category)
        form.addRow("Prioridad", self._priority)
        form.addRow(self._has_due, self._due)
        form.addRow("Duración estimada", self._estimated)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Guardar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def data(self) -> TaskFormData:
        due = None
        if self._has_due.isChecked():
            due = self._due.dateTime().toPython().astimezone().astimezone(UTC)
        return TaskFormData(
            title=self._title.text().strip(),
            description=self._description.toPlainText().strip(),
            category_id=self._category.currentData(),
            priority=self._priority.currentData(),
            due_at=due,
            estimated_minutes=self._estimated.value() or None,
        )


class AssignSectionsDialog(QDialog):
    """Elige secciones activas y no estudiadas para asignarlas a una tarea.

    ``as_solution`` solo cambia los textos: lo que se asigna es material igual, pero
    el usuario tiene que ver sin dudar si está poniendo el enunciado o la respuesta.
    """

    def __init__(
        self,
        sections: list[SectionRow],
        *,
        parent: QWidget | None = None,
        as_solution: bool = False,
    ) -> None:
        super().__init__(parent)
        self._as_solution = as_solution
        self.setWindowTitle("Añadir solución" if as_solution else "Asignar material")
        self.setMinimumSize(560, 460)

        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Filtrar por material o sección…")
        self._list = QListWidget()
        self._all = sections
        self._populate(sections)
        self._filter.textChanged.connect(self._on_filter)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Añadir como solución" if as_solution else "Asignar"
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        heading = (
            "Elige la solución de esta tarea. Queda guardada aparte y en el modo "
            "estudio no se abre hasta que la pidas."
            if as_solution
            else "Secciones disponibles (activas y sin estudiar)"
        )
        title = QLabel(heading)
        title.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self._filter)
        layout.addWidget(self._list, 1)
        layout.addWidget(buttons)

    def _populate(self, sections: list[SectionRow]) -> None:
        self._list.clear()
        for row in sections:
            label = f"{row.material_title} · {row.title}"
            if row.range_label:
                label += f"  ({row.range_label})"
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, row.id)
            self._list.addItem(item)

    def _on_filter(self, text: str) -> None:
        needle = text.strip().lower()
        filtered = [
            row
            for row in self._all
            if needle in row.material_title.lower() or needle in row.title.lower()
        ]
        self._populate(filtered)

    def selected_ids(self) -> list[EntityId]:
        out: list[EntityId] = []
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                out.append(item.data(Qt.ItemDataRole.UserRole))
        return out


class ExamDialog(QDialog):
    def __init__(
        self,
        categories: tuple[CategoryNode, ...],
        sections: list[SectionRow],
        *,
        parent: QWidget | None = None,
        default_date: datetime | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nuevo examen")
        self.setMinimumSize(560, 520)

        self._title = QLineEdit()
        self._title.setPlaceholderText("Parcial 1, quiz de derivadas…")
        self._category = category_combo(categories)
        self._when = QDateTimeEdit(
            QDateTime(default_date.astimezone())
            if default_date
            else QDateTime.currentDateTime().addDays(7)
        )
        self._when.setCalendarPopup(True)
        self._when.setDisplayFormat("dd/MM/yyyy HH:mm")

        self._sections = AssignSectionsDialog(sections, parent=self)
        self._sections.setParent(self)
        self._sections.setWindowFlags(Qt.WindowType.Widget)

        form = QFormLayout()
        form.addRow("Título", self._title)
        form.addRow("Categoría", self._category)
        form.addRow("Fecha", self._when)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Crear")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("Temario: qué secciones cubre este examen"))
        layout.addWidget(self._sections, 1)
        layout.addWidget(buttons)

    def title(self) -> str:
        return self._title.text().strip()

    def category_id(self) -> EntityId | None:
        return self._category.currentData()

    def scheduled_at(self) -> datetime:
        return self._when.dateTime().toPython().astimezone().astimezone(UTC)

    def section_ids(self) -> list[EntityId]:
        return self._sections.selected_ids()


class RecordExamDialog(QDialog):
    """Registra el resultado. Aprobar archiva el temario."""

    def __init__(self, exam_title: str, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Registrar resultado")
        self.setMinimumWidth(420)

        self._passed = QComboBox()
        self._passed.addItem("Aprobado — archivar el temario", True)
        self._passed.addItem("Reprobado — el material sigue activo", False)
        self._score = QDoubleSpinBox()
        self._score.setRange(0, 100)
        self._score.setDecimals(2)
        self._score.setSpecialValueText("sin nota")

        form = QFormLayout()
        form.addRow(QLabel(f"Examen: {exam_title}"))
        form.addRow("Resultado", self._passed)
        form.addRow("Nota", self._score)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Registrar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def passed(self) -> bool:
        return bool(self._passed.currentData())

    def score(self) -> float | None:
        return self._score.value() or None


class ManualSessionDialog(QDialog):
    """Registra tiempo de estudio hecho fuera de la aplicación."""

    def __init__(self, task_title: str, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Registrar tiempo")
        self.setMinimumWidth(420)

        self._when = QDateTimeEdit(QDateTime.currentDateTime().addSecs(-3600))
        self._when.setCalendarPopup(True)
        self._when.setDisplayFormat("dd/MM/yyyy HH:mm")
        self._minutes = QSpinBox()
        self._minutes.setRange(1, 60 * 12)
        self._minutes.setValue(30)
        self._minutes.setSuffix(" min")

        form = QFormLayout()
        form.addRow(QLabel(f"Tarea: {task_title}"))
        form.addRow("Empezó", self._when)
        form.addRow("Duración", self._minutes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Registrar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def started_at(self) -> datetime:
        return self._when.dateTime().toPython().astimezone().astimezone(UTC)

    def minutes(self) -> int:
        return self._minutes.value()


class LinkDialog(QDialog):
    """Alta rápida de enlace con título opcional."""

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Agregar enlace")
        self.setMinimumWidth(460)
        self._url = QLineEdit()
        self._url.setPlaceholderText("https://www.youtube.com/watch?v=…")
        self._title = QLineEdit()
        self._title.setPlaceholderText("Opcional")

        form = QFormLayout()
        form.addRow("Dirección", self._url)
        form.addRow("Título", self._title)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def url(self) -> str:
        return self._url.text().strip()

    def title(self) -> str | None:
        return self._title.text().strip() or None


def horizontal(*widgets: QWidget) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    for widget in widgets:
        layout.addWidget(widget)
    return container
