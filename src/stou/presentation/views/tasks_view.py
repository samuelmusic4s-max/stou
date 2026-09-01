"""Tareas: el trabajo por hacer.

Se dejó la tabla atrás. Cada tarea es una fila alta con su propia acción de estudiar
y su propio menú, así que no hace falta seleccionar primero y actuar después: un
clic hace lo que dice. Cuando no hay tareas, la pantalla explica cómo se crean.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from stou.application.dto import TaskRow
from stou.domain.events import (
    StudySessionClosed,
    TaskCompleted,
    TaskCreated,
    TaskDeleted,
    TaskMaterialAssigned,
    TaskMaterialUnassigned,
    TaskScheduled,
    TaskStatusChanged,
    TaskUpdated,
)
from stou.domain.values import ItemRole, TaskStatus
from stou.presentation.qt import motion
from stou.presentation.qt.theme import (
    SPACE,
    format_duration_short,
    relative_day,
)
from stou.presentation.services import AppServices
from stou.presentation.widgets.components import (
    GLYPH,
    EmptyState,
    label,
    pill,
)
from stou.presentation.widgets.dialogs import (
    AssignSectionsDialog,
    ManualSessionDialog,
    TaskDialog,
)
from stou.shared.ids import EntityId

CONTENT_MAX_WIDTH = 1360

FILTERS: list[tuple[str, list[TaskStatus] | None]] = [
    ("Abiertas", [TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
    ("Completadas", [TaskStatus.DONE]),
    ("Todas", None),
]

STATUS_LABEL = {
    TaskStatus.PENDING: "pendiente",
    TaskStatus.IN_PROGRESS: "en progreso",
    TaskStatus.DONE: "completada",
    TaskStatus.CANCELLED: "cancelada",
}


class TasksView(QWidget):
    studyRequested = Signal(str)
    importRequested = Signal()

    def __init__(self, services: AppServices, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._s = services
        self._filter_index = 0
        self._rows: list[TaskRow] = []
        self._build_ui()
        self._connect_events()
        self.refresh()

    # --- construcción ---------------------------------------------------------

    def _build_ui(self) -> None:
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(label("TU TRABAJO", "Eyebrow"))
        titles.addWidget(label("Tareas", "H1"))

        self._new_btn = QPushButton("Nueva tarea")
        self._new_btn.setObjectName("Primary")
        self._new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # lambda a propósito: clicked emite un bool que se colaría como argumento.
        self._new_btn.clicked.connect(lambda: self.create_task())

        header = QHBoxLayout()
        header.addLayout(titles, 1)
        header.addWidget(self._new_btn, 0, Qt.AlignmentFlag.AlignBottom)

        self._search = QLineEdit()
        self._search.setObjectName("Search")
        self._search.setPlaceholderText("Buscar entre tus tareas…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(lambda _: self.refresh())

        self._chips: list[QPushButton] = []
        chips_row = QHBoxLayout()
        chips_row.setSpacing(SPACE["sm"])
        for index, (text, _statuses) in enumerate(FILTERS):
            chip = QPushButton(text)
            chip.setCheckable(True)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setObjectName("Primary" if index == 0 else "Ghost")
            chip.setChecked(index == 0)
            chip.clicked.connect(lambda _checked=False, i=index: self._set_filter(i))
            self._chips.append(chip)
            chips_row.addWidget(chip)
        chips_row.addStretch(1)
        self._summary = label("", "Faint")
        chips_row.addWidget(self._summary)

        filters = QHBoxLayout()
        filters.setSpacing(SPACE["md"])
        filters.addWidget(self._search, 1)

        self._list_column = QVBoxLayout()
        self._list_column.setContentsMargins(0, 0, 0, 0)
        self._list_column.setSpacing(SPACE["sm"])
        list_holder = QWidget()
        list_holder.setLayout(self._list_column)

        canvas = QWidget()
        canvas.setMaximumWidth(CONTENT_MAX_WIDTH)
        column = QVBoxLayout(canvas)
        column.setContentsMargins(0, SPACE["xl"], 0, SPACE["2xl"])
        column.setSpacing(SPACE["lg"])
        column.addLayout(header)
        column.addLayout(filters)
        column.addLayout(chips_row)
        column.addWidget(list_holder)
        column.addStretch(1)

        centered = QWidget()
        centering = QHBoxLayout(centered)
        centering.setContentsMargins(SPACE["xl"], 0, SPACE["xl"], 0)
        centering.addStretch(1)
        centering.addWidget(canvas, 20)
        centering.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(centered)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _connect_events(self) -> None:
        self._s.events.on(
            (
                TaskCreated,
                TaskUpdated,
                TaskDeleted,
                TaskStatusChanged,
                TaskCompleted,
                TaskScheduled,
                TaskMaterialAssigned,
                TaskMaterialUnassigned,
                StudySessionClosed,
            ),
            lambda _e: self.refresh(),
        )

    # --- datos ----------------------------------------------------------------

    def refresh(self) -> None:
        _text, statuses = FILTERS[self._filter_index]
        self._rows = self._s.list_tasks.execute(
            statuses=statuses, search=self._search.text().strip() or None
        )
        self._render()

    def _render(self) -> None:
        while self._list_column.count():
            item = self._list_column.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        if not self._rows:
            self._list_column.addWidget(self._empty_state())
            self._summary.setText("")
            return

        widgets: list[QWidget] = []
        for row in self._rows:
            card = _TaskCard(row, parent=self)
            card.studyRequested.connect(self.studyRequested.emit)
            card.menuRequested.connect(self._menu_for)
            self._list_column.addWidget(card)
            widgets.append(card)

        spent = sum(r.spent_seconds for r in self._rows)
        open_count = sum(
            1 for r in self._rows if r.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)
        )
        self._summary.setText(
            f"{len(self._rows)} tareas · {open_count} abiertas · "
            f"{format_duration_short(spent)} dedicados"
        )
        motion.stagger(widgets[:8], step=30, distance=8)

    def _empty_state(self) -> QWidget:
        searching = bool(self._search.text().strip())
        if searching:
            return EmptyState(
                glyph=GLYPH["empty"],
                title="Ninguna tarea coincide",
                body="Prueba con otras palabras, o cambia el filtro de arriba.",
                action="Limpiar búsqueda",
                on_action=lambda: self._search.clear(),
            )

        if self._filter_index == 1:
            return EmptyState(
                glyph=GLYPH["check"],
                title="Todavía no has completado ninguna tarea",
                body="Cuando marques una como completada aparecerá aquí con el tiempo "
                "que le dedicaste.",
            )

        has_material = self._s.home.execute().has_material
        if not has_material:
            return EmptyState(
                glyph=GLYPH["import"],
                title="Primero sube tu material",
                body="Una tarea en STOU apunta a capítulos concretos de tu material. "
                "Sube un libro o un video y podrás armar tareas con sus capítulos.",
                action="Subir material",
                on_action=self.importRequested.emit,
                secondary="Crear una tarea sin material",
                on_secondary=lambda: self.create_task(),
            )

        return EmptyState(
            glyph=GLYPH["tasks"],
            title="No tienes tareas",
            body="Una tarea dice qué vas a estudiar y cuándo. Al abrirla, STOU te sirve "
            "el material que le asignaste y empieza a contar el tiempo.",
            action="Crear tu primera tarea",
            on_action=lambda: self.create_task(),
        )

    def _set_filter(self, index: int) -> None:
        self._filter_index = index
        for position, chip in enumerate(self._chips):
            chip.setChecked(position == index)
            chip.setObjectName("Primary" if position == index else "Ghost")
            chip.style().unpolish(chip)
            chip.style().polish(chip)
        self.refresh()

    def focus_search(self) -> None:
        self._search.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def row_titles(self) -> list[str]:
        return [row.title for row in self._rows]

    # --- acciones -------------------------------------------------------------

    def create_task(self, *, default_due: datetime | None = None) -> EntityId | None:
        """Crea una tarea. Se llama desde el botón, desde Ctrl+N y desde Inicio."""
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
            task_id = self._s.create_task.execute(
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

        self._offer_assign(task_id, data.category_id, first_time=True)
        return task_id

    def _offer_assign(
        self, task_id: EntityId, category_id: EntityId | None, *, first_time: bool = False
    ) -> None:
        sections = self._s.suggest_sections.execute(category_id=category_id)
        if not sections:
            if first_time:
                QMessageBox.information(
                    self,
                    "Tarea creada sin material",
                    "No hay secciones activas sin estudiar en esa materia. Sube material "
                    "a la biblioteca o divídelo en capítulos, y luego asígnalo a la tarea "
                    "desde su menú.",
                )
            else:
                QMessageBox.information(
                    self,
                    "Nada que asignar",
                    "No quedan secciones activas sin estudiar en esa materia.",
                )
            return

        dialog = AssignSectionsDialog(sections, parent=self)
        if dialog.exec() != AssignSectionsDialog.DialogCode.Accepted:
            return
        ids = dialog.selected_ids()
        if ids:
            self._s.assign_material.execute(task_id=task_id, section_ids=ids)

    def _offer_solution(self, task_id: EntityId) -> None:
        """Añade la solución de la tarea.

        La solución se busca en **toda** la biblioteca, no solo en la materia de la
        tarea: el solucionario suele ser un archivo aparte, y a menudo sin seccionar.
        """
        sections = self._s.suggest_sections.execute(category_id=None)
        if not sections:
            QMessageBox.information(
                self,
                "Todavía no hay nada que añadir",
                "Una solución es material de tu biblioteca. Sube el solucionario "
                "—un PDF, una foto de tus apuntes, un video— y después añádelo aquí.",
            )
            return

        dialog = AssignSectionsDialog(sections, parent=self, as_solution=True)
        if dialog.exec() != AssignSectionsDialog.DialogCode.Accepted:
            return
        ids = dialog.selected_ids()
        if not ids:
            return
        self._s.assign_material.execute(
            task_id=task_id, section_ids=ids, role=ItemRole.SOLUTION
        )
        QMessageBox.information(
            self,
            "Solución añadida",
            "Queda guardada aparte del enunciado. En el modo estudio no se abre hasta "
            "que pulses «Ver solución».",
        )

    def _menu_for(self, task_id: EntityId, global_position) -> None:  # noqa: ANN001
        row = next((r for r in self._rows if r.id == task_id), None)
        if row is None:
            return

        menu = QMenu(self)
        study = menu.addAction(f"{GLYPH['study']}  Estudiar")
        edit = menu.addAction("Editar…")
        assign = menu.addAction("Asignar material…")
        # Al final del menú de material: la solución es lo último que se añade.
        solution = menu.addAction(f"{GLYPH['check']}  Añadir solución…")
        manual = menu.addAction("Registrar tiempo a mano…")
        menu.addSeparator()
        toggle = menu.addAction(
            "Reabrir" if row.status is TaskStatus.DONE else "Marcar completada"
        )
        cancel = menu.addAction("Cancelar tarea")
        menu.addSeparator()
        delete = menu.addAction("Eliminar")

        chosen = menu.exec(global_position)
        if chosen is None:
            return
        if chosen == study:
            self.studyRequested.emit(row.id)
        elif chosen == edit:
            self._edit(row)
        elif chosen == assign:
            self._offer_assign(row.id, row.category_id)
        elif chosen == solution:
            self._offer_solution(row.id)
        elif chosen == manual:
            self._manual_time(row)
        elif chosen == toggle:
            new_status = (
                TaskStatus.PENDING if row.status is TaskStatus.DONE else TaskStatus.DONE
            )
            self._s.change_task_status.execute(task_id=row.id, status=new_status)
        elif chosen == cancel:
            self._s.change_task_status.execute(task_id=row.id, status=TaskStatus.CANCELLED)
        elif chosen == delete:
            confirm = QMessageBox.question(
                self,
                "Eliminar tarea",
                f"¿Eliminar «{row.title}»?\n\nEl material se conserva en la biblioteca; "
                "solo se pierde la tarea y su registro de tiempo.",
            )
            if confirm == QMessageBox.StandardButton.Yes:
                self._s.delete_task.execute(task_id=row.id)

    def _manual_time(self, row: TaskRow) -> None:
        dialog = ManualSessionDialog(row.title, parent=self)
        if dialog.exec() != ManualSessionDialog.DialogCode.Accepted:
            return
        self._s.add_manual_session.execute(
            task_id=row.id, started_at=dialog.started_at(), minutes=dialog.minutes()
        )

    def _edit(self, row: TaskRow) -> None:
        detail = self._s.task_detail.execute(task_id=row.id)
        dialog = TaskDialog(self._s.category_tree.execute(), parent=self, detail=detail)
        if dialog.exec() != TaskDialog.DialogCode.Accepted:
            return
        data = dialog.data()
        if not data.title:
            QMessageBox.information(
                self, "Falta el título", "Una tarea necesita al menos un título."
            )
            return
        self._s.update_task.execute(
            task_id=row.id,
            title=data.title,
            description=data.description,
            category_id=data.category_id,
            priority=data.priority,
            estimated_minutes=data.estimated_minutes,
        )
        self._s.reschedule_task.execute(task_id=row.id, due_at=data.due_at)


class _TaskCard(QFrame):
    """Fila de tarea: título, contexto, píldoras y sus dos acciones."""

    studyRequested = Signal(str)
    menuRequested = Signal(str, object)

    def __init__(self, row: TaskRow, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._row = row
        self.setObjectName("ActionCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        line = QHBoxLayout(self)
        line.setContentsMargins(SPACE["lg"], SPACE["md"], SPACE["md"], SPACE["md"])
        line.setSpacing(SPACE["md"])

        done = row.status is TaskStatus.DONE
        glyph = label(GLYPH["check"] if done else GLYPH["study"], "Dim")
        glyph.setFixedWidth(18)
        line.addWidget(glyph)

        texts = QVBoxLayout()
        texts.setSpacing(3)
        title = label(row.title, "H3")
        if done:
            title.setObjectName("Dim")
        texts.addWidget(title)

        context = [row.category_path]
        if row.item_count:
            context.append(f"{row.studied_items}/{row.item_count} del material estudiado")
        else:
            context.append("sin material asignado")
        if row.spent_seconds:
            context.append(f"{format_duration_short(row.spent_seconds)} dedicados")
        texts.addWidget(label("  ·  ".join(context), "Faint"))
        line.addLayout(texts, 1)

        if row.overdue:
            line.addWidget(pill("atrasada", "Danger"))
        elif row.due_at is not None:
            line.addWidget(pill(relative_day(row.due_at, datetime.now().astimezone())))
        if row.status is TaskStatus.IN_PROGRESS:
            line.addWidget(pill(STATUS_LABEL[row.status], "Accent"))
        elif done:
            line.addWidget(pill(STATUS_LABEL[row.status], "Ok"))

        self._study_btn = QPushButton("Estudiar")
        self._study_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._study_btn.clicked.connect(lambda: self.studyRequested.emit(self._row.id))
        line.addWidget(self._study_btn)

        self._menu_btn = QPushButton("⋯")
        self._menu_btn.setObjectName("Ghost")
        self._menu_btn.setFixedWidth(36)
        self._menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._menu_btn.clicked.connect(
            lambda: self.menuRequested.emit(
                self._row.id, self._menu_btn.mapToGlobal(self._menu_btn.rect().bottomLeft())
            )
        )
        line.addWidget(self._menu_btn)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda position: self.menuRequested.emit(self._row.id, self.mapToGlobal(position))
        )
        motion.hover_lift(self, normal="ActionCard", hot="ActionCardHot")

    @property
    def task_id(self) -> EntityId:
        return self._row.id

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: ANN001, N802 - API de Qt
        self.studyRequested.emit(self._row.id)
        super().mouseDoubleClickEvent(event)
