"""Ventana principal.

La navegación tiene cinco destinos y un orden que cuenta una historia: empiezas en
Inicio (qué hago ahora), pasas por Tareas y Biblioteca (el trabajo y el material),
Calendario (cuándo) y terminas en Historial (qué hice). El Dashboard dejó de ser la
puerta de entrada porque un tablero de cifras no le dice a nadie qué hacer.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from stou.domain.events import DomainEvent
from stou.presentation.qt import motion
from stou.presentation.qt.theme import SPACE, format_duration
from stou.presentation.services import AppServices
from stou.presentation.views.calendar_view import CalendarView
from stou.presentation.views.dashboard_view import DashboardView
from stou.presentation.views.home_view import HomeView
from stou.presentation.views.library_view import LibraryView
from stou.presentation.views.study_view import StudyWindow
from stou.presentation.views.tasks_view import TasksView
from stou.presentation.views.viewer_window import ViewerWindow
from stou.presentation.widgets.components import GLYPH, label
from stou.shared.ids import EntityId

# (clave, etiqueta, glifo)
SECTIONS = [
    ("home", "Inicio", GLYPH["home"]),
    ("tasks", "Tareas", GLYPH["tasks"]),
    ("library", "Biblioteca", GLYPH["library"]),
    ("calendar", "Calendario", GLYPH["calendar"]),
    ("dashboard", "Historial", GLYPH["dashboard"]),
]
STATUS_CLEAR_MS = 4000


class MainWindow(QMainWindow):
    def __init__(self, services: AppServices) -> None:
        super().__init__()
        self._s = services
        self._windows: list[QWidget] = []

        self.setWindowTitle("STOU")
        self.resize(1400, 900)
        self.setMinimumSize(1040, 680)

        self._build_views()
        self._build_chrome()
        self._wire()
        self._restore_state()
        self.go_to("home")

    # --- construcción ---------------------------------------------------------

    def _build_views(self) -> None:
        self._stack = QStackedWidget()
        self._home = HomeView(self._s)
        self._tasks = TasksView(self._s)
        self._library = LibraryView(self._s)
        self._calendar = CalendarView(self._s)
        self._dashboard = DashboardView(self._s)
        self._views = {
            "home": self._home,
            "tasks": self._tasks,
            "library": self._library,
            "calendar": self._calendar,
            "dashboard": self._dashboard,
        }
        for key, _text, _glyph in SECTIONS:
            self._stack.addWidget(self._views[key])

    def _build_chrome(self) -> None:
        brand = QWidget()
        brand_row = QHBoxLayout(brand)
        brand_row.setContentsMargins(SPACE["xl"], SPACE["xl"], SPACE["xl"], SPACE["lg"])
        brand_row.setSpacing(SPACE["sm"])
        brand_row.addWidget(label("STOU", "H2"))
        brand_row.addStretch(1)

        self._nav = QListWidget()
        self._nav.setObjectName("Nav")
        self._nav.setFrameShape(QListWidget.Shape.NoFrame)
        self._nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        for _key, text, glyph in SECTIONS:
            item = QListWidgetItem(f"  {glyph}    {text}")
            self._nav.addItem(item)
        self._nav.currentRowChanged.connect(self._on_nav)

        self._hint = QLabel("Ctrl+1…5 para moverte\nCtrl+N nueva tarea\nCtrl+I subir material")
        self._hint.setObjectName("Faint")
        self._hint.setWordWrap(True)

        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(212)
        side_column = QVBoxLayout(sidebar)
        side_column.setContentsMargins(0, 0, 0, SPACE["xl"])
        side_column.setSpacing(SPACE["sm"])
        side_column.addWidget(brand)
        side_column.addWidget(self._nav, 1)
        hint_holder = QWidget()
        hint_layout = QVBoxLayout(hint_holder)
        hint_layout.setContentsMargins(SPACE["xl"], 0, SPACE["lg"], 0)
        hint_layout.addWidget(self._hint)
        side_column.addWidget(hint_holder)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(sidebar)
        layout.addWidget(self._stack, 1)
        self.setCentralWidget(central)

        self._status = QStatusBar()
        self._status.setSizeGripEnabled(False)
        self._status_label = QLabel("")
        self._status.addWidget(self._status_label)
        self.setStatusBar(self._status)
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(lambda: self._status_label.setText(""))

    def _wire(self) -> None:
        self._tasks.studyRequested.connect(self.open_study)
        self._tasks.importRequested.connect(self.import_material)
        self._calendar.studyRequested.connect(self.open_study)
        self._dashboard.studyRequested.connect(self.open_study)
        self._library.openMaterialRequested.connect(self.open_material)

        self._home.studyRequested.connect(self.open_study)
        self._home.navigateRequested.connect(self.go_to)
        self._home.importRequested.connect(self.import_material)
        self._home.newTaskRequested.connect(self.new_task)
        self._home.newCategoryRequested.connect(self.new_category)

        self._s.events.on_any(self._on_event)

        for index, (key, _text, _glyph) in enumerate(SECTIONS):
            QShortcut(QKeySequence(f"Ctrl+{index + 1}"), self, lambda k=key: self.go_to(k))
        QShortcut(QKeySequence("Ctrl+N"), self, self.new_task)
        QShortcut(QKeySequence("Ctrl+I"), self, self.import_material)
        QShortcut(QKeySequence("Ctrl+F"), self, self.focus_search)

    # --- navegación -----------------------------------------------------------

    def go_to(self, key: str) -> None:
        keys = [k for k, _t, _g in SECTIONS]
        if key not in keys:
            return
        index = keys.index(key)
        if self._nav.currentRow() != index:
            self._nav.setCurrentRow(index)
            return
        self._show(index)

    def _on_nav(self, row: int) -> None:
        if row >= 0:
            self._show(row)

    def _show(self, index: int) -> None:
        motion.cross_fade(self._stack, index)
        current = self._stack.currentWidget()
        refresh = getattr(current, "refresh", None)
        if callable(refresh):
            refresh()

    def focus_search(self) -> None:
        current = self._stack.currentWidget()
        search = getattr(current, "focus_search", None)
        if callable(search):
            search()

    # --- acciones globales ----------------------------------------------------

    def new_task(self) -> None:
        """Crear tarea funciona igual desde cualquier parte de la aplicación."""
        self.go_to("tasks")
        self._tasks.create_task()

    def new_category(self) -> None:
        self.go_to("library")
        self._library.create_category()

    def import_material(self) -> None:
        self.go_to("library")
        self._library.import_files()

    def open_study(self, task_id: EntityId) -> None:
        window = StudyWindow(self._s, task_id)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        window.sessionFinished.connect(self._on_session_finished)
        window.destroyed.connect(lambda: self._forget(window))
        self._windows.append(window)
        window.show()
        motion.fade_in(window, start=0.0)

    def open_material(self, material_id: EntityId, position: float = 0.0) -> None:
        window = ViewerWindow(self._s, material_id, position)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        window.destroyed.connect(lambda: self._forget(window))
        self._windows.append(window)
        window.show()
        motion.fade_in(window, start=0.0)

    def _forget(self, window: QWidget) -> None:
        if window in self._windows:
            self._windows.remove(window)

    # --- estado ---------------------------------------------------------------

    def notify(self, message: str) -> None:
        self._status_label.setText(message)
        self._status_timer.start(STATUS_CLEAR_MS)

    def _on_session_finished(self, _task_id: str, seconds: int) -> None:
        self.notify(
            f"Sesión cerrada · {format_duration(seconds)} registrados"
            if seconds
            else "Sesión cerrada sin tiempo efectivo: no se registró nada"
        )

    def _on_event(self, event: DomainEvent) -> None:
        message = _HUMAN.get(event.event_name)
        if message:
            self.notify(message)

    def _settings(self) -> QSettings:
        return QSettings("stou", "stou")

    def _restore_state(self) -> None:
        geometry = self._settings().value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

    def closeEvent(self, event) -> None:  # noqa: ANN001, N802 - API de Qt
        self._settings().setValue("window/geometry", self.saveGeometry())
        for window in list(self._windows):
            window.close()
        super().closeEvent(event)


# Solo los hechos que el usuario reconoce como resultado de lo que acaba de hacer.
_HUMAN = {
    "CategoryCreated": "Materia creada",
    "CategoryRenamed": "Materia renombrada",
    "CategoryDeleted": "Materia eliminada",
    "MaterialImported": "Material agregado a la biblioteca",
    "MaterialDeleted": "Material eliminado",
    "MaterialArchived": "Material archivado",
    "MaterialReactivated": "Material reactivado",
    "SectionsCreated": "Material seccionado",
    "SectionStudied": "Sección marcada como estudiada",
    "TaskCreated": "Tarea creada",
    "TaskCompleted": "Tarea completada",
    "TaskDeleted": "Tarea eliminada",
    "TaskScheduled": "Tarea reprogramada",
    "TaskMaterialAssigned": "Material asignado a la tarea",
    "StudySessionPaused": "Conteo en pausa por inactividad",
    "StudySessionResumed": "Conteo reanudado",
    "ExamCreated": "Examen registrado en el calendario",
    "ExamRecorded": "Resultado de examen registrado",
}
