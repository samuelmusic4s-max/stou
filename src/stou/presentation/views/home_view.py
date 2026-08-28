"""Inicio: el menú principal.

No es un resumen de datos: es una respuesta a «qué hago ahora». Tiene una sola
acción dominante, tres accesos secundarios y nada más. Si el sistema está vacío, la
pantalla se convierte en una guía de tres pasos y muestra un botón por vez.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from stou.application.dto import HomeOverview, TaskRow
from stou.domain.events import (
    MaterialImported,
    SectionStudied,
    StudySessionClosed,
    TaskCompleted,
    TaskCreated,
    TaskDeleted,
    TaskStatusChanged,
)
from stou.presentation.qt import motion
from stou.presentation.qt.theme import (
    SPACE,
    format_duration_short,
    relative_day,
)
from stou.presentation.services import AppServices
from stou.presentation.widgets.components import (
    GLYPH,
    ActionCard,
    Card,
    EmptyState,
    MetricTile,
    SectionHeader,
    StepRow,
    label,
    pill,
)
from stou.shared.ids import EntityId

CONTENT_MAX_WIDTH = 1080


class HomeView(QWidget):
    """Pantalla de inicio. No consulta datos: los pide y los presenta."""

    studyRequested = Signal(str)
    navigateRequested = Signal(str)  # library | tasks | calendar | dashboard
    importRequested = Signal()
    newTaskRequested = Signal()
    newCategoryRequested = Signal()

    def __init__(self, services: AppServices, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._s = services
        self._overview: HomeOverview | None = None

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._canvas = QWidget()
        self._canvas.setMaximumWidth(CONTENT_MAX_WIDTH)
        self._column = QVBoxLayout(self._canvas)
        self._column.setContentsMargins(0, SPACE["lg"], 0, SPACE["3xl"])
        self._column.setSpacing(SPACE["xl"])

        centered = QWidget()
        centering = QHBoxLayout(centered)
        centering.setContentsMargins(SPACE["xl"], 0, SPACE["xl"], 0)
        centering.addStretch(1)
        centering.addWidget(self._canvas, 1)
        centering.addStretch(1)
        self._scroll.setWidget(centered)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._scroll)

        self._connect_events()
        self.refresh()

    def _connect_events(self) -> None:
        self._s.events.on(
            (
                TaskCreated,
                TaskDeleted,
                TaskCompleted,
                TaskStatusChanged,
                StudySessionClosed,
                MaterialImported,
                SectionStudied,
            ),
            lambda _e: self.refresh(),
        )

    # --- composición ----------------------------------------------------------

    def refresh(self) -> None:
        self._overview = self._s.home.execute()
        self._clear()

        blocks: list[QWidget] = []
        if self._overview.is_first_run:
            blocks.append(self._build_welcome())
            blocks.append(self._build_steps())
        else:
            blocks.append(self._build_greeting())
            blocks.append(self._build_hero())
            blocks.append(self._build_shortcuts())
            blocks.append(self._build_continue())
            blocks.append(self._build_metrics())

        for block in blocks:
            self._column.addWidget(block)
        self._column.addStretch(1)

        motion.stagger(blocks)

    def _clear(self) -> None:
        while self._column.count():
            item = self._column.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    # --- primer uso -----------------------------------------------------------

    def _build_welcome(self) -> QWidget:
        block = QWidget()
        column = QVBoxLayout(block)
        column.setContentsMargins(0, SPACE["2xl"], 0, 0)
        column.setSpacing(SPACE["md"])

        column.addWidget(label("BIENVENIDO A STOU", "Eyebrow"))
        column.addWidget(
            label("Pon tu material adentro y STOU te dirá qué estudiar.", "Display", wrap=True)
        )
        explanation = label(
            "Un libro entra una vez, se parte en capítulos, y tus tareas apuntan a esos "
            "capítulos. Cuando abres una tarea, el material ya está servido y el tiempo "
            "se cuenta solo.",
            "Dim",
            wrap=True,
        )
        explanation.setMaximumWidth(680)
        column.addWidget(explanation)
        return block

    def _build_steps(self) -> QWidget:
        assert self._overview is not None
        step = self._overview.onboarding_step

        card = Card()
        card.body.setSpacing(SPACE["xs"])
        card.add(
            SectionHeader(
                "Tres pasos para empezar",
                subtitle="Toma un minuto. Después de esto la pantalla de inicio te dirá "
                "qué estudiar cada día.",
            )
        )

        definitions = [
            (
                1,
                "Crea una materia",
                "Matemáticas, Historia, Cálculo I… Puedes anidarlas: una materia "
                "dentro de otra.",
                "Crear materia",
                self.newCategoryRequested,
            ),
            (
                2,
                "Sube tu material",
                "Arrastra tus PDFs, EPUBs o videos. STOU se queda con una copia y "
                "parte los libros en capítulos leyendo su índice.",
                "Subir material",
                self.importRequested,
            ),
            (
                3,
                "Crea tu primera tarea",
                "Elige qué capítulos vas a estudiar y cuándo. Al abrirla entras al modo "
                "estudio con todo a mano.",
                "Crear tarea",
                self.newTaskRequested,
            ),
        ]

        for number, title, description, action_text, signal in definitions:
            state = "done" if number < step else ("current" if number == step else "todo")
            row = StepRow(
                number=number,
                title=title,
                description=description,
                action_text=action_text,
                state=state,
            )
            row.action.connect(signal.emit)
            card.add(row)

        return card

    # --- uso normal -----------------------------------------------------------

    def _build_greeting(self) -> QWidget:
        assert self._overview is not None
        now = datetime.now().astimezone()

        block = QWidget()
        column = QVBoxLayout(block)
        column.setContentsMargins(0, SPACE["xl"], 0, 0)
        column.setSpacing(SPACE["sm"])

        column.addWidget(label(_date_line(now).upper(), "Eyebrow"))
        column.addWidget(label(_greeting(now.hour), "Display"))
        column.addWidget(label(self._situation_line(), "Dim", wrap=True))
        return block

    def _situation_line(self) -> str:
        """Una frase que resume la situación. Sin cifras que no cambien nada."""
        assert self._overview is not None
        data = self._overview
        parts: list[str] = []

        if data.overdue_tasks:
            parts.append(
                f"{data.overdue_tasks} tarea atrasada"
                if data.overdue_tasks == 1
                else f"{data.overdue_tasks} tareas atrasadas"
            )
        if data.open_tasks:
            parts.append(
                "1 tarea abierta" if data.open_tasks == 1 else f"{data.open_tasks} tareas abiertas"
            )
        else:
            parts.append("nada pendiente")

        if data.next_exam is not None and data.days_to_exam is not None:
            if data.days_to_exam <= 0:
                parts.append(f"«{data.next_exam.title}» es hoy")
            else:
                parts.append(f"«{data.next_exam.title}» en {data.days_to_exam} días")

        return " · ".join(parts).capitalize()

    def _build_hero(self) -> QWidget:
        assert self._overview is not None
        task = self._overview.next_task

        if task is None:
            card = ActionCard(
                glyph=GLYPH["tasks"],
                title="No tienes ninguna tarea abierta",
                description="Crea una para volver a tener un plan. Puedes armarla con los "
                "capítulos que aún no has estudiado.",
                hint="empezar aquí",
                primary=True,
            )
            card.clicked.connect(self.newTaskRequested.emit)
            card.setMinimumHeight(150)
            return card

        verb = "Sigue con" if self._overview.in_progress else "Empieza con"
        detail = [task.category_path]
        if task.item_count:
            detail.append(f"{task.studied_items}/{task.item_count} del material estudiado")
        else:
            detail.append("sin material asignado todavía")
        if task.due_at is not None:
            detail.append(f"vence {relative_day(task.due_at, datetime.now().astimezone())}")
        if task.spent_seconds:
            detail.append(f"{format_duration_short(task.spent_seconds)} dedicados")

        card = ActionCard(
            glyph=GLYPH["study"],
            title=f"{verb} «{task.title}»",
            description="  ·  ".join(detail),
            hint="retomar" if self._overview.in_progress else "estudiar ahora",
            primary=True,
        )
        card.setMinimumHeight(170)
        card.clicked.connect(lambda: self.studyRequested.emit(task.id))
        return card

    def _build_shortcuts(self) -> QWidget:
        assert self._overview is not None
        block = QWidget()
        grid = QGridLayout(block)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(SPACE["lg"])

        material_note = (
            f"{self._overview.material_count} en la biblioteca"
            if self._overview.material_count
            else "aún no hay nada"
        )
        cards = [
            (
                GLYPH["import"],
                "Subir material",
                f"PDFs, EPUBs, videos o enlaces. {material_note}.",
                self.importRequested.emit,
            ),
            (
                GLYPH["tasks"],
                "Nueva tarea",
                "Elige los capítulos y la fecha. El material queda pegado a la tarea.",
                self.newTaskRequested.emit,
            ),
            (
                GLYPH["calendar"],
                "Ver calendario",
                "Reparte el estudio y registra tus exámenes antes de que se junten.",
                lambda: self.navigateRequested.emit("calendar"),
            ),
        ]

        for column, (glyph, title, description, action) in enumerate(cards):
            card = ActionCard(glyph=glyph, title=title, description=description)
            card.clicked.connect(action)
            grid.addWidget(card, 0, column)
            grid.setColumnStretch(column, 1)

        return block

    def _build_continue(self) -> QWidget:
        assert self._overview is not None
        card = Card()
        card.add(
            SectionHeader(
                "Sigue donde ibas",
                subtitle="Tus tareas abiertas, por lo último que tocaste.",
                action="Ver todas  " + GLYPH["arrow"],
                on_action=lambda: self.navigateRequested.emit("tasks"),
            )
        )

        rows = self._overview.recent_tasks
        if not rows:
            card.add(
                EmptyState(
                    glyph=GLYPH["empty"],
                    title="Sin tareas abiertas",
                    body="Cuando crees una tarea aparecerá aquí para que la retomes con "
                    "un clic.",
                    action="Crear tarea",
                    on_action=self.newTaskRequested.emit,
                )
            )
            return card

        for row in rows:
            card.add(_TaskButton(row, on_click=self.studyRequested.emit))
        return card

    def _build_metrics(self) -> QWidget:
        assert self._overview is not None
        data = self._overview

        block = QWidget()
        row = QHBoxLayout(block)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(SPACE["lg"])

        today = MetricTile("hoy", glyph=GLYPH["time"], big=True)
        today.set_value(format_duration_short(data.today_seconds))
        today.set_note(
            "Solo cuenta el tiempo medido dentro de una sesión."
            if data.today_seconds
            else "Todavía no has estudiado hoy."
        )

        week = MetricTile("esta semana", glyph=GLYPH["dashboard"], big=True)
        week.set_value(format_duration_short(data.week_seconds))
        week.set_note(
            f"{data.unstudied_sections} secciones sin estudiar"
            if data.unstudied_sections
            else "No queda material activo sin estudiar."
        )

        streak = MetricTile("racha", glyph=GLYPH["streak"], big=True)
        streak.set_value(f"{data.streak_days} d" if data.streak_days else "—")
        streak.set_note(
            "Días seguidos con al menos una sesión."
            if data.streak_days
            else "Estudia hoy para empezar una."
        )
        if data.streak_days:
            motion.count_up(
                lambda value: streak.set_value(f"{value} d"), target=data.streak_days
            )

        for tile in (today, week, streak):
            row.addWidget(tile, 1)
        return block


class _TaskButton(QFrame):
    """Fila de tarea clicable: abre el modo estudio directamente."""

    def __init__(
        self,
        row: TaskRow,
        *,
        on_click,  # noqa: ANN001 - callable
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._row = row
        self._on_click = on_click
        self.setObjectName("ActionCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        line = QHBoxLayout(self)
        line.setContentsMargins(SPACE["lg"], SPACE["md"], SPACE["lg"], SPACE["md"])
        line.setSpacing(SPACE["md"])

        glyph = label(GLYPH["study"], "Dim")
        glyph.setFixedWidth(18)
        line.addWidget(glyph)

        texts = QVBoxLayout()
        texts.setSpacing(1)
        texts.addWidget(label(row.title, "H3"))
        subtitle = row.category_path
        if row.item_count:
            subtitle += f"  ·  {row.studied_items}/{row.item_count} estudiado"
        texts.addWidget(label(subtitle, "Faint"))
        line.addLayout(texts, 1)

        if row.overdue:
            line.addWidget(pill("atrasada", "Danger"))
        elif row.due_at is not None:
            line.addWidget(pill(relative_day(row.due_at, datetime.now().astimezone())))

        motion.hover_lift(self, normal="ActionCard", hot="ActionCardHot")

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001, N802 - API de Qt
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click(self._row.id)
        super().mouseReleaseEvent(event)

    @property
    def task_id(self) -> EntityId:
        return self._row.id


def _greeting(hour: int) -> str:
    if hour < 6:
        return "Buenas noches"
    if hour < 12:
        return "Buenos días"
    if hour < 20:
        return "Buenas tardes"
    return "Buenas noches"


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


def _date_line(moment: datetime) -> str:
    return f"{_DAYS[moment.weekday()]} {moment.day} de {_MONTHS[moment.month - 1]}"
