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
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from stou.application.dto import HomeOverview, TaskRow
from stou.domain.events import (
    CategoryCreated,
    CategoryDeleted,
    ExamCreated,
    ExamRecorded,
    MaterialDeleted,
    MaterialImported,
    SectionsCreated,
    SectionStudied,
    StudySessionClosed,
    TaskCompleted,
    TaskCreated,
    TaskDeleted,
    TaskScheduled,
    TaskStatusChanged,
)
from stou.presentation.qt import motion
from stou.presentation.qt.theme import (
    COLORS,
    SPACE,
    format_duration_short,
    relative_day,
)
from stou.presentation.services import AppServices
from stou.presentation.widgets.charts import ActivityChart, SubjectBars, SubjectRow, Track
from stou.presentation.widgets.components import (
    GLYPH,
    ActionCard,
    Card,
    EmptyState,
    SectionHeader,
    StepRow,
    label,
    pill,
)
from stou.shared.ids import EntityId

# En una pantalla ancha una columna de 1080 px deja la mitad del espacio vacío; a la
# vez, una línea de texto de 1600 px no se lee. 1360 es el punto medio.
CONTENT_MAX_WIDTH = 1360

# Filas de pendientes que se muestran en Inicio. El resto está en Tareas: la pantalla
# tiene que caber de una vez, si no deja de servir para decidir de un vistazo.
VISIBLE_PENDING = 5


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
        self._column.setSpacing(SPACE["lg"])

        centered = QWidget()
        centering = QHBoxLayout(centered)
        centering.setContentsMargins(SPACE["xl"], 0, SPACE["xl"], 0)
        centering.addStretch(1)
        centering.addWidget(self._canvas, 20)
        centering.addStretch(1)
        self._scroll.setWidget(centered)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._scroll)

        self._connect_events()
        self.refresh()

    def _connect_events(self) -> None:
        # Inicio reacciona a todo lo que puede cambiar la respuesta a «qué hago ahora»,
        # incluidas las categorías: sin ellas el primer paso de la guía no avanzaría.
        self._s.events.on(
            (
                CategoryCreated,
                CategoryDeleted,
                TaskCreated,
                TaskDeleted,
                TaskCompleted,
                TaskStatusChanged,
                TaskScheduled,
                StudySessionClosed,
                MaterialImported,
                MaterialDeleted,
                SectionsCreated,
                SectionStudied,
                ExamCreated,
                ExamRecorded,
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
            blocks.append(self._build_pending())
            blocks.append(self._build_rhythm())

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
        column.setContentsMargins(0, SPACE["md"], 0, 0)
        column.setSpacing(SPACE["xs"])

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
        """La banda de «qué toca ahora». Una fila, no una caja alta."""
        assert self._overview is not None
        task = self._overview.next_task

        if task is None:
            card = ActionCard(
                glyph=GLYPH["tasks"],
                title="No tienes ninguna tarea abierta",
                description="Crea una para volver a tener un plan.",
                hint="empezar",
                primary=True,
                compact=True,
            )
            card.clicked.connect(self.newTaskRequested.emit)
            return card

        verb = "Sigue con" if self._overview.in_progress else "Empieza con"
        detail = [task.category_path]
        if task.item_count:
            detail.append(f"{task.studied_items}/{task.item_count} del material")
        else:
            detail.append("sin material asignado")
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
            compact=True,
        )
        card.clicked.connect(lambda: self.studyRequested.emit(task.id))
        return card

    def _build_pending(self) -> QWidget:
        """Lo pendiente, ordenado por urgencia. Es el bloque que gobierna la pantalla."""
        assert self._overview is not None
        data = self._overview

        card = Card()
        counts = []
        if data.overdue_tasks:
            counts.append(
                f"{data.overdue_tasks} atrasada"
                if data.overdue_tasks == 1
                else f"{data.overdue_tasks} atrasadas"
            )
        counts.append(
            "1 abierta" if data.open_tasks == 1 else f"{data.open_tasks} abiertas"
        )
        card.add(
            SectionHeader(
                "Pendientes",
                subtitle=" · ".join(counts) + " · lo atrasado primero",
                action="Ver todas  " + GLYPH["arrow"],
                on_action=lambda: self.navigateRequested.emit("tasks"),
            )
        )

        if not data.pending_tasks:
            card.add(
                EmptyState(
                    glyph=GLYPH["check"],
                    title="No tienes nada pendiente",
                    body="Cuando crees una tarea aparecerá aquí, ordenada por lo que "
                    "vence antes.",
                    action="Crear tarea",
                    on_action=self.newTaskRequested.emit,
                )
            )
            return card

        # Cinco caben en una pantalla junto con el resto. El total va en el subtítulo y
        # la lista completa está a un clic: es mejor que una columna que no se acaba.
        for row in data.pending_tasks[:VISIBLE_PENDING]:
            card.add(_TaskButton(row, on_click=self.studyRequested.emit))
        return card

    def _build_rhythm(self) -> QWidget:
        """Lo hecho: tres cifras, el gráfico de dos semanas y el reparto por materia.

        Van en una sola tarjeta a propósito. Repartidos en tres, cada uno pedía su
        título y su marco, y la pantalla acababa siendo una lista de cajas.
        """
        assert self._overview is not None
        data = self._overview

        card = Card()
        card.body.setSpacing(SPACE["md"])
        card.add(
            SectionHeader(
                "Tu ritmo",
                subtitle=f"Últimos {data.recent_window_days} días. Solo tiempo medido "
                "dentro de una sesión.",
                action="Ver historial  " + GLYPH["arrow"],
                on_action=lambda: self.navigateRequested.emit("dashboard"),
            )
        )

        figures = QHBoxLayout()
        figures.setSpacing(SPACE["2xl"])
        figures.addWidget(_Stat("hoy", format_duration_short(data.today_seconds)))
        figures.addWidget(_Stat("esta semana", format_duration_short(data.week_seconds)))
        figures.addWidget(
            _Stat("racha", f"{data.streak_days} d" if data.streak_days else "—")
        )
        figures.addWidget(
            _Stat(
                "sin estudiar",
                str(data.unstudied_sections) if data.unstudied_sections else "—",
                accent=False,
            )
        )
        figures.addStretch(1)
        figures_holder = QWidget()
        figures_holder.setLayout(figures)
        card.add(figures_holder)

        chart = ActivityChart(height=132)
        chart.set_data(list(data.recent_days), today=datetime.now().astimezone().date())

        columns = QHBoxLayout()
        columns.setSpacing(SPACE["2xl"])
        columns.addWidget(chart, 3)

        subjects = QVBoxLayout()
        subjects.setSpacing(SPACE["xs"])
        subjects.addWidget(label("POR MATERIA", "Eyebrow"))
        rows = self._subject_rows()
        if rows:
            bars = SubjectBars()
            bars.set_rows(rows)
            subjects.addWidget(bars)
        else:
            subjects.addWidget(
                label(
                    "Cuando importes material y estudies desde una tarea, aquí verás en "
                    "qué se te va el tiempo.",
                    "Faint",
                    wrap=True,
                )
            )
        subjects.addStretch(1)
        subjects_holder = QWidget()
        subjects_holder.setLayout(subjects)
        columns.addWidget(subjects_holder, 2)

        body = QWidget()
        body.setLayout(columns)
        card.add(body)
        return card

    def _subject_rows(self) -> list[SubjectRow]:
        """Una fila por materia con las dos cosas que importan: tiempo y avance.

        Se juntan en la misma fila en lugar de en dos columnas porque son la misma
        pregunta vista de dos maneras: en qué estoy gastando el tiempo y cuánto me
        queda de eso.
        """
        assert self._overview is not None
        data = self._overview

        seconds = {row.category_id: row for row in data.recent_by_category}
        peak = max((row.seconds for row in data.recent_by_category), default=0)

        # Primero los datos, y solo al final los widgets: ordenar widgets obliga a que
        # el widget guarde sus propios datos, que es justo lo que no debe hacer.
        entries: list[tuple[str, str, float, str, str]] = []
        for progress in data.progress:
            time_row = seconds.get(progress.category_id)
            spent = time_row.seconds if time_row else 0
            color = time_row.color if time_row else COLORS["ok"]
            # Tiempo y avance en la misma línea: dos líneas por materia en vez de
            # tres, que es lo que hacía que la pantalla no cupiera de una vez.
            parts = [format_duration_short(spent) if spent else "sin tiempo"]
            if progress.total_sections:
                parts.append(
                    f"{progress.studied_sections}/{progress.total_sections} cap."
                )
            if progress.archived_sections == progress.total_sections > 0:
                parts.append("archivada")
            entries.append(
                (
                    progress.category_path,
                    "  ·  ".join(parts),
                    (spent / peak) if peak else 0.0,
                    color,
                    "",
                )
            )

        # Las materias sin material seccionado no salen de `progress`, pero si tienen
        # tiempo medido merecen aparecer: es tiempo que el usuario dedicó.
        known = {progress.category_id for progress in data.progress}
        for row in data.recent_by_category:
            if row.category_id not in known:
                entries.append(
                    (
                        row.category_path,
                        f"{format_duration_short(row.seconds)}  ·  sin seccionar",
                        (row.seconds / peak) if peak else 0.0,
                        row.color,
                        "",
                    )
                )

        entries.sort(key=lambda entry: entry[0].lower())
        return [
            SubjectRow(title=title, value=value, ratio=ratio, color=color, note=note)
            for title, value, ratio, color, note in entries
        ]

class _Stat(QWidget):
    """Una cifra con su nombre debajo. Sin caja: cuatro cajas seguidas son una tabla."""

    def __init__(self, caption: str, value: str, *, accent: bool = True) -> None:
        super().__init__()
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(label(value, "MetricMedium" if accent else "H2"))
        column.addWidget(label(caption, "Faint"))
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)


class _TaskButton(QFrame):
    """Fila de tarea clicable: abre el modo estudio directamente.

    La fila aprovecha el ancho en lugar de dejar un vacío entre el título y la fecha:
    al centro va el avance del material y el tiempo dedicado, que es lo que decide si
    esta tarea es la que toca.
    """

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
        line.setContentsMargins(SPACE["lg"], SPACE["sm"], SPACE["lg"], SPACE["sm"])
        line.setSpacing(SPACE["lg"])

        glyph = label(GLYPH["study"], "Dim")
        glyph.setFixedWidth(18)
        line.addWidget(glyph)

        texts = QVBoxLayout()
        texts.setSpacing(1)
        texts.addWidget(label(row.title, "H3"))
        texts.addWidget(label(row.category_path, "Faint"))
        line.addLayout(texts, 1)

        # Avance del material: solo si hay material, para no mostrar una barra vacía
        # que no significa nada. Ancho fijo para que la columna quede alineada entre
        # filas: si se estirara, cada título la movería de sitio.
        middle = QVBoxLayout()
        middle.setSpacing(3)
        if row.item_count:
            middle.addWidget(
                label(f"{row.studied_items}/{row.item_count} estudiado", "Faint")
            )
            middle.addWidget(Track(row.studied_items / row.item_count, COLORS["ok"]))
        else:
            middle.addWidget(label("sin material asignado", "Faint"))
        holder = QWidget()
        holder.setLayout(middle)
        holder.setFixedWidth(180)
        line.addWidget(holder)

        spent = label(
            format_duration_short(row.spent_seconds) if row.spent_seconds else "—", "Dim"
        )
        spent.setFixedWidth(58)
        spent.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        line.addWidget(spent)

        if row.overdue:
            tag = pill("atrasada", "Danger")
        elif row.due_at is not None:
            tag = pill(relative_day(row.due_at, datetime.now().astimezone()))
        else:
            tag = pill("sin fecha")
        # Las píldoras miden distinto según su texto; en un contenedor de ancho fijo la
        # columna de fechas queda a plomo.
        tag_holder = QWidget()
        tag_row = QHBoxLayout(tag_holder)
        tag_row.setContentsMargins(0, 0, 0, 0)
        tag_row.addStretch(1)
        tag_row.addWidget(tag)
        tag_holder.setFixedWidth(94)
        line.addWidget(tag_holder)

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
