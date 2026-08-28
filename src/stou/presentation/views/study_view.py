"""Modo estudio: la tarea abierta con todo su material servido.

Aquí ocurre el conteo de tiempo: un tick cada pocos segundos que la capa de
aplicación convierte en tiempo efectivo o en pausa por inactividad.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from stou.application.dto import TaskDetail, TaskItemRow
from stou.presentation.qt.theme import format_clock
from stou.presentation.qt.worker import run_async
from stou.presentation.services import AppServices
from stou.presentation.widgets.viewers import BaseViewer, NoteViewer, build_viewer
from stou.shared.ids import EntityId

TICK_MS = 5000
ROLE_ITEM = Qt.ItemDataRole.UserRole


class StudyWindow(QWidget):
    """Ventana de estudio de una tarea. Al cerrarse, cierra la sesión."""

    sessionFinished = Signal(str, int)  # task_id, segundos efectivos

    def __init__(
        self,
        services: AppServices,
        task_id: EntityId,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._s = services
        self._task_id = task_id
        self._session_id: EntityId | None = None
        self._viewer: BaseViewer | None = None
        self._current_item: TaskItemRow | None = None
        self._current_position = 0.0
        self._had_activity = True
        self._focus_mode = False

        self._detail: TaskDetail = self._s.task_detail.execute(task_id=task_id)

        self.setWindowTitle(f"Estudiando · {self._detail.task.title}")
        self.setMinimumSize(1100, 700)
        self._build_ui()

        self._session_id = self._s.start_session.execute(task_id=task_id)

        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        QApplication.instance().installEventFilter(self)
        QShortcut(QKeySequence("F11"), self, self._toggle_focus_mode)
        QShortcut(QKeySequence("Ctrl+Return"), self, self._mark_current_studied)

        if self._detail.items:
            self._items.setCurrentRow(0)

    # --- construcción ---------------------------------------------------------

    def _build_ui(self) -> None:
        self._title = QLabel(self._detail.task.title)
        self._title.setObjectName("Title")
        self._subtitle = QLabel(self._detail.task.category_path)
        self._subtitle.setObjectName("Subtitle")

        self._clock = QLabel("00:00:00")
        self._clock.setObjectName("Metric")
        self._clock_state = QLabel("contando")
        self._clock_state.setObjectName("Subtitle")

        studied_btn = QPushButton("Marcar estudiada")
        studied_btn.clicked.connect(self._mark_current_studied)
        finish_btn = QPushButton("Terminar sesión")
        finish_btn.setObjectName("Primary")
        finish_btn.clicked.connect(self.close)
        focus_btn = QPushButton("Sin distracciones (F11)")
        focus_btn.clicked.connect(self._toggle_focus_mode)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(self._title)
        titles.addWidget(self._subtitle)
        header.addLayout(titles, 1)
        clock_box = QVBoxLayout()
        clock_box.setSpacing(0)
        clock_box.addWidget(self._clock, alignment=Qt.AlignmentFlag.AlignRight)
        clock_box.addWidget(self._clock_state, alignment=Qt.AlignmentFlag.AlignRight)
        header.addLayout(clock_box)
        header.addWidget(studied_btn)
        header.addWidget(focus_btn)
        header.addWidget(finish_btn)

        # Material asignado
        self._items = QListWidget()
        self._items.setMinimumWidth(240)
        self._items.currentItemChanged.connect(self._on_item_selected)
        self._refresh_items()

        self._left = QWidget()
        left_layout = QVBoxLayout(self._left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Material de la tarea"))
        left_layout.addWidget(self._items, 1)

        # Visor
        self._viewer_host = QWidget()
        self._viewer_layout = QVBoxLayout(self._viewer_host)
        self._viewer_layout.setContentsMargins(0, 0, 0, 0)
        self._section_label = QLabel("Selecciona material para empezar")
        self._section_label.setObjectName("Subtitle")
        self._viewer_layout.addWidget(self._section_label)

        # Notas rápidas
        self._notes = QTextEdit()
        self._notes.setPlaceholderText(
            "Notas de esta sesión…\nSe guardan como una nota de la tarea."
        )
        save_note = QPushButton("Guardar nota")
        save_note.clicked.connect(self._save_note)
        description = QLabel(self._detail.description or "Sin descripción")
        description.setWordWrap(True)
        description.setObjectName("Subtitle")

        self._right = QWidget()
        right_layout = QVBoxLayout(self._right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("Descripción"))
        right_layout.addWidget(description)
        right_layout.addWidget(QLabel("Notas"))
        right_layout.addWidget(self._notes, 1)
        right_layout.addWidget(save_note)
        self._right.setMaximumWidth(320)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._left)
        self._splitter.addWidget(self._viewer_host)
        self._splitter.addWidget(self._right)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([250, 850, 300])

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(self._splitter, 1)

    def _refresh_items(self) -> None:
        current_id = self._current_item.item_id if self._current_item else None
        self._items.blockSignals(True)
        self._items.clear()
        for item in self._detail.items:
            label = item.title
            if item.range_label:
                label += f"\n{item.range_label}"
            entry = QListWidgetItem(("✓  " if item.studied else "•  ") + label)
            entry.setData(ROLE_ITEM, item)
            self._items.addItem(entry)
        self._items.blockSignals(False)
        if current_id:
            for index in range(self._items.count()):
                data: TaskItemRow = self._items.item(index).data(ROLE_ITEM)
                if data.item_id == current_id:
                    self._items.setCurrentRow(index)
                    break

    # --- material -------------------------------------------------------------

    def _on_item_selected(self, current: QListWidgetItem | None, _prev) -> None:
        if current is None:
            return
        item: TaskItemRow = current.data(ROLE_ITEM)
        self._open_item(item)

    def _open_item(self, item: TaskItemRow) -> None:
        self._persist_position()
        self._teardown_viewer()

        self._current_item = item
        source = self._s.resolve_source.execute(material_id=item.material_id)
        epub_docs = None
        if source.kind.value == "epub":
            try:
                epub_docs = self._s.prepare_epub.execute(material_id=item.material_id)
            except Exception:
                epub_docs = []

        viewer = build_viewer(source, epub_documents=epub_docs, parent=self._viewer_host)
        viewer.positionChanged.connect(self._on_position_changed)
        if isinstance(viewer, NoteViewer):
            viewer.saveRequested.connect(
                lambda body, mid=item.material_id: self._s.update_material.execute(
                    material_id=mid, body=body
                )
            )

        self._viewer = viewer
        self._viewer_layout.addWidget(viewer, 1)

        label = item.title
        if item.range_label:
            label += f"  ·  {item.range_label}"
        self._section_label.setText(label)

        if item.section_id and item.position is not None:
            # Saltar al inicio de la sección asignada.
            start = self._section_start(item)
            if start is not None:
                QTimer.singleShot(400, lambda: viewer.go_to(start))

        if self._session_id:
            self._had_activity = True

    def _section_start(self, item: TaskItemRow) -> float | None:
        if not item.section_id:
            return None
        rows = self._s.list_sections.execute(material_id=item.material_id)
        for row in rows:
            if row.id == item.section_id:
                return row.start
        return None

    def _teardown_viewer(self) -> None:
        if self._viewer is None:
            return
        self._viewer.shutdown()
        self._viewer_layout.removeWidget(self._viewer)
        self._viewer.setParent(None)
        self._viewer.deleteLater()
        self._viewer = None

    def _on_position_changed(self, position: float) -> None:
        self._current_position = position

    def _persist_position(self) -> None:
        if self._current_item is None or self._viewer is None:
            return
        if self._current_position <= 0:
            return
        material_id = self._current_item.material_id
        position = self._current_position
        run_async(
            lambda: self._s.save_position.execute(
                material_id=material_id, position=position
            )
        )

    # --- tiempo ---------------------------------------------------------------

    def eventFilter(self, watched, event) -> bool:  # noqa: ANN001, N802 - API de Qt
        if event.type() in (
            QEvent.Type.KeyPress,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseMove,
            QEvent.Type.Wheel,
        ):
            self._had_activity = True
        return False

    def _tick(self) -> None:
        if not self._session_id:
            return
        media = bool(self._viewer and self._viewer.media_playing)
        activity = self._had_activity
        self._had_activity = False
        material_id = self._current_item.material_id if self._current_item else None

        state = self._s.tick_session.execute(
            session_id=self._session_id,
            had_activity=activity,
            media_playing=media,
            material_id=material_id,
        )
        if state is None:
            return
        self._clock.setText(format_clock(state.effective_seconds))
        self._clock_state.setText("en pausa por inactividad" if state.paused else "contando")

    # --- acciones -------------------------------------------------------------

    def _mark_current_studied(self) -> None:
        if self._current_item is None or not self._current_item.section_id:
            QMessageBox.information(
                self,
                "Marcar estudiada",
                "Solo las secciones se marcan como estudiadas. Este material está asignado "
                "completo.",
            )
            return
        self._s.mark_studied.execute(
            section_id=self._current_item.section_id,
            studied=not self._current_item.studied,
        )
        self._detail = self._s.task_detail.execute(task_id=self._task_id)
        self._refresh_items()

    def _save_note(self) -> None:
        text = self._notes.toPlainText().strip()
        if not text:
            return
        title = f"Notas · {self._detail.task.title}"
        material_id = self._s.create_note.execute(
            title=title,
            body=self._notes.toHtml(),
            category_id=self._detail.task.category_id,
        )
        self._s.assign_material.execute(task_id=self._task_id, material_id=material_id)
        self._notes.clear()
        self._detail = self._s.task_detail.execute(task_id=self._task_id)
        self._refresh_items()

    def _toggle_focus_mode(self) -> None:
        self._focus_mode = not self._focus_mode
        self._left.setVisible(not self._focus_mode)
        self._right.setVisible(not self._focus_mode)

    # --- cierre ---------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: ANN001, N802 - API de Qt
        self._timer.stop()
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self._persist_position()
        self._teardown_viewer()
        seconds = 0
        if self._session_id:
            seconds = self._s.close_session.execute(session_id=self._session_id)
            self._session_id = None
        self.sessionFinished.emit(self._task_id, seconds)
        super().closeEvent(event)
