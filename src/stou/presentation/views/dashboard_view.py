"""Dashboard: la mirada hacia atrás.

Menos denso a propósito. Antes eran seis cuadros del mismo tamaño compitiendo entre
sí; ahora hay una cifra dominante, una gráfica, y el detalle se pide por pestañas.
Lo que no se midió se dice con palabras en lugar de dibujar un cero.
"""

from __future__ import annotations

from datetime import UTC, datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from stou.application import periods
from stou.application.dto import CategoryTime, DashboardData, DayTime, TaskRow
from stou.domain.events import (
    ExamRecorded,
    SectionStudied,
    StudySessionClosed,
    TaskCompleted,
    TaskCreated,
    TaskDeleted,
    TaskScheduled,
)
from stou.presentation.qt import motion
from stou.presentation.qt.theme import (
    COLORS,
    SPACE,
    format_duration,
    format_duration_short,
    relative_day,
)
from stou.presentation.services import AppServices
from stou.presentation.widgets.components import (
    GLYPH,
    Card,
    EmptyState,
    ListRow,
    MetricTile,
    SectionHeader,
    label,
)

PERIODS = [
    ("Hoy", "today"),
    ("Esta semana", "week"),
    ("Este mes", "month"),
    ("Últimos 30 días", "last30"),
]
CONTENT_MAX_WIDTH = 1080


class DashboardView(QWidget):
    studyRequested = Signal(str)

    def __init__(self, services: AppServices, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._s = services
        self._data: DashboardData | None = None
        self._build_ui()
        self._connect_events()
        self.refresh()

    # --- construcción ---------------------------------------------------------

    def _build_ui(self) -> None:
        self._period = QComboBox()
        for text, _key in PERIODS:
            self._period.addItem(text)
        self._period.setCurrentIndex(1)
        self._period.currentIndexChanged.connect(lambda _: self.refresh())

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(label("TU HISTORIAL", "Eyebrow"))
        titles.addWidget(label("Cuánto has estudiado", "H1"))
        header.addLayout(titles, 1)
        header.addWidget(self._period, 0, Qt.AlignmentFlag.AlignBottom)

        # Cifra dominante + gráfica, en una sola tarjeta ancha.
        self._headline = MetricTile("tiempo estudiado", glyph=GLYPH["time"], big=True)
        self._headline.setMinimumWidth(240)
        self._bars = _DayBars()

        chart_card = Card()
        chart_row = QHBoxLayout()
        chart_row.setSpacing(SPACE["xl"])
        chart_row.addWidget(self._headline, 0)
        chart_row.addWidget(self._bars, 1)
        holder = QWidget()
        holder.setLayout(chart_row)
        chart_card.add(
            SectionHeader("Ritmo", subtitle="Tiempo efectivo por día del período.")
        )
        chart_card.add(holder, 1)

        # Métricas secundarias, en una tira ligera.
        self._done = MetricTile("tareas completadas", glyph=GLYPH["check"])
        self._streak = MetricTile("días seguidos", glyph=GLYPH["streak"])
        self._open = MetricTile("tareas abiertas", glyph=GLYPH["tasks"])
        strip = QWidget()
        strip_row = QHBoxLayout(strip)
        strip_row.setContentsMargins(0, 0, 0, 0)
        strip_row.setSpacing(SPACE["lg"])
        for tile in (self._done, self._streak, self._open):
            strip_row.addWidget(tile, 1)

        # El detalle vive en pestañas: se pide, no se impone.
        self._tabs = QTabWidget()
        self._by_category = _RowList()
        self._agenda = _RowList(on_click=self.studyRequested.emit)
        self._exams = _RowList()
        self._progress = _RowList()
        self._tabs.addTab(self._wrap(self._by_category), "Por materia")
        self._tabs.addTab(self._wrap(self._agenda), "Pendientes")
        self._tabs.addTab(self._wrap(self._exams), "Exámenes")
        self._tabs.addTab(self._wrap(self._progress), "Avance del material")

        detail_card = Card()
        detail_card.add(self._tabs, 1)

        canvas = QWidget()
        canvas.setMaximumWidth(CONTENT_MAX_WIDTH)
        column = QVBoxLayout(canvas)
        column.setContentsMargins(0, SPACE["xl"], 0, SPACE["2xl"])
        column.setSpacing(SPACE["xl"])
        column.addLayout(header)
        column.addWidget(chart_card)
        column.addWidget(strip)
        column.addWidget(detail_card, 1)

        centered = QWidget()
        centering = QHBoxLayout(centered)
        centering.setContentsMargins(SPACE["xl"], 0, SPACE["xl"], 0)
        centering.addStretch(1)
        centering.addWidget(canvas, 1)
        centering.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(centered)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._blocks = [chart_card, strip, detail_card]

    @staticmethod
    def _wrap(content: QWidget) -> QWidget:
        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, SPACE["md"], 0, 0)
        layout.addWidget(content)
        return holder

    def _connect_events(self) -> None:
        self._s.events.on(
            (
                StudySessionClosed,
                TaskCompleted,
                TaskCreated,
                TaskDeleted,
                TaskScheduled,
                SectionStudied,
                ExamRecorded,
            ),
            lambda _e: self.refresh(),
        )

    # --- datos ----------------------------------------------------------------

    def refresh(self) -> None:
        now = datetime.now(UTC)
        window = {
            "today": periods.today,
            "week": periods.current_week,
            "month": periods.current_month,
            "last30": lambda moment: periods.last_days(moment, 30),
        }[PERIODS[self._period.currentIndex()][1]](now)

        data = self._s.dashboard.execute(period=window)
        self._data = data
        local_now = now.astimezone()

        self._headline.set_value(
            format_duration_short(data.total_seconds) if data.total_seconds else "—"
        )
        self._headline.set_note(
            f"{data.period_label.lower()} · solo sesiones medidas"
            if data.total_seconds
            else "Sin sesiones registradas en este período."
        )
        self._bars.set_data(list(data.by_day))

        self._done.set_value(str(data.completed_tasks))
        self._done.set_note("en el período elegido")
        self._streak.set_value(f"{data.streak_days}" if data.streak_days else "—")
        self._streak.set_note("con al menos una sesión")
        self._open.set_value(str(data.open_tasks))
        self._open.set_note(
            f"{len(data.overdue)} atrasadas" if data.overdue else "ninguna atrasada"
        )

        self._fill_categories(list(data.by_category))
        self._fill_agenda(data, local_now)
        self._fill_exams(data, local_now)
        self._fill_progress(data)

        motion.fade_in(self._tabs, duration=160, start=0.4)

    def _fill_categories(self, rows: list[CategoryTime]) -> None:
        self._by_category.clear()
        if not rows:
            self._by_category.set_empty(
                EmptyState(
                    glyph=GLYPH["time"],
                    title="Nada medido todavía",
                    body="El tiempo aparece aquí cuando estudias desde una tarea: STOU lo "
                    "cuenta solo mientras trabajas.",
                )
            )
            return
        top = max(r.seconds for r in rows) or 1
        for row in rows:
            self._by_category.add(
                _BarRow(
                    title=row.category_path,
                    value=format_duration(row.seconds),
                    ratio=row.seconds / top,
                    color=row.color,
                )
            )

    def _fill_agenda(self, data: DashboardData, now: datetime) -> None:
        self._agenda.clear()
        rows: list[tuple[TaskRow, str, str]] = []
        for task in data.overdue:
            rows.append((task, "atrasada", "Danger"))
        for task in data.upcoming_tasks:
            when = relative_day(task.due_at, now) if task.due_at else "sin fecha"
            rows.append((task, when, ""))

        if not rows:
            self._agenda.set_empty(
                EmptyState(
                    glyph=GLYPH["check"],
                    title="No hay nada pendiente con fecha",
                    body="Cuando pongas fecha límite a una tarea aparecerá aquí ordenada "
                    "por urgencia.",
                )
            )
            return

        for task, tag, tone in rows:
            self._agenda.add(
                ListRow(
                    glyph=GLYPH["study"],
                    title=task.title,
                    subtitle=f"{task.category_path}  ·  "
                    f"{task.studied_items}/{task.item_count} del material",
                    tag=tag,
                    tone=tone,
                ),
                task_id=task.id,
            )

    def _fill_exams(self, data: DashboardData, now: datetime) -> None:
        self._exams.clear()
        if not data.upcoming_exams:
            self._exams.set_empty(
                EmptyState(
                    glyph=GLYPH["exam"],
                    title="Sin exámenes programados",
                    body="Registra un examen en el calendario y elige qué capítulos cubre. "
                    "Al aprobarlo, ese material sale del circuito activo.",
                )
            )
            return
        for exam in data.upcoming_exams:
            when = relative_day(exam.scheduled_at, now) if exam.scheduled_at else "sin fecha"
            self._exams.add(
                ListRow(
                    glyph=GLYPH["exam"],
                    title=exam.title,
                    subtitle=f"{exam.category_path}  ·  {exam.section_count} secciones de temario",
                    tag=when,
                    tone="Warn",
                )
            )

    def _fill_progress(self, data: DashboardData) -> None:
        self._progress.clear()
        if not data.progress:
            self._progress.set_empty(
                EmptyState(
                    glyph=GLYPH["library"],
                    title="Aún no hay material seccionado",
                    body="Importa un libro y STOU lo parte en capítulos usando su índice. "
                    "Cada capítulo es una sección que puedes asignar y marcar.",
                )
            )
            return
        for row in data.progress:
            active = row.total_sections - row.archived_sections
            self._progress.add(
                _BarRow(
                    title=row.category_path,
                    value=f"{row.studied_sections}/{row.total_sections} estudiadas",
                    ratio=(row.studied_sections / row.total_sections)
                    if row.total_sections
                    else 0,
                    color=COLORS["ok"],
                    note=f"{active} activas · {row.archived_sections} archivadas",
                )
            )


class _RowList(QWidget):
    """Lista vertical de filas con estado vacío propio."""

    def __init__(self, *, on_click=None, parent: QWidget | None = None) -> None:  # noqa: ANN001
        super().__init__(parent)
        self._on_click = on_click
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

    def add(self, widget: QWidget, *, task_id: str | None = None) -> None:
        if task_id and self._on_click is not None:
            widget.setCursor(Qt.CursorShape.PointingHandCursor)
            widget.mouseReleaseEvent = lambda _e, tid=task_id: self._on_click(tid)  # type: ignore[method-assign]
        self._column.addWidget(widget)

    def set_empty(self, state: QWidget) -> None:
        self.clear()
        self._column.addWidget(state)

    @property
    def count(self) -> int:
        return self._column.count()

    def row_texts(self) -> list[str]:
        texts = []
        for index in range(self._column.count()):
            widget = self._column.itemAt(index).widget()
            if widget is not None:
                texts.append(widget.property("rowText") or "")
        return texts


class _BarRow(QWidget):
    """Fila con barra proporcional. Comparar de un vistazo, sin leer números."""

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
        self._ratio = max(0.0, min(1.0, ratio))
        self._color = color

        column = QVBoxLayout(self)
        column.setContentsMargins(SPACE["md"], SPACE["sm"], SPACE["md"], SPACE["sm"])
        column.setSpacing(SPACE["xs"])

        top = QHBoxLayout()
        top.addWidget(label(title, "H3"), 1)
        top.addWidget(label(value, "Dim"))
        column.addLayout(top)

        self._track = _Bar(self._ratio, color)
        column.addWidget(self._track)
        if note:
            column.addWidget(label(note, "Faint"))


class _Bar(QWidget):
    def __init__(self, ratio: float, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ratio = ratio
        self._color = color
        self.setFixedHeight(6)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - API de Qt
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS["surface_3"]))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 3, 3)
        if self._ratio > 0:
            painter.setBrush(QColor(self._color))
            painter.drawRoundedRect(
                0, 0, max(4, int(self.width() * self._ratio)), self.height(), 3, 3
            )


class _DayBars(QWidget):
    """Barras por día. Dibujadas a mano: una gráfica de verdad sobraría aquí."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data: list[DayTime] = []
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, data: list[DayTime]) -> None:
        self._data = data
        self.update()

    @property
    def has_data(self) -> bool:
        return bool(self._data) and any(d.seconds for d in self._data)

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - API de Qt
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self.has_data:
            painter.setPen(QColor(COLORS["text_faint"]))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Aquí verás tus días en cuanto estudies desde una tarea",
            )
            return

        top = max(d.seconds for d in self._data) or 1
        pad = 10
        labels_h = 18
        width = self.width() - 2 * pad
        height = self.height() - 2 * pad - labels_h
        count = len(self._data)
        slot = width / count
        bar_w = max(5.0, min(26.0, slot * 0.55))

        painter.setPen(Qt.PenStyle.NoPen)
        for index, day in enumerate(self._data):
            bar_h = (day.seconds / top) * height
            x = pad + index * slot + (slot - bar_w) / 2
            y = pad + height - bar_h
            painter.setBrush(
                QColor(COLORS["accent"] if day.seconds else COLORS["surface_3"])
            )
            painter.drawRoundedRect(x, y, bar_w, max(3.0, bar_h), 3, 3)

        painter.setPen(QColor(COLORS["text_faint"]))
        step = max(1, count // 8)
        for index in range(0, count, step):
            x = pad + index * slot
            painter.drawText(
                int(x),
                self.height() - 3,
                int(slot * step) + 20,
                labels_h,
                Qt.AlignmentFlag.AlignLeft,
                self._data[index].day.strftime("%d/%m"),
            )
