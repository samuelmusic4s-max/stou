"""Modo estudio: la tarea abierta con todo su material servido.

La ventana está construida alrededor de una sola idea: cuando el usuario se sienta,
lo único que debe ver es su material. El cronómetro es la segunda pieza más visible
porque es la prueba de que el trabajo quedó registrado; todo lo demás se puede
esconder con F11.

Aquí ocurre el conteo de tiempo: un tick cada pocos segundos que la capa de
aplicación convierte en tiempo efectivo o en pausa por inactividad.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from stou.application.dto import TaskDetail, TaskItemRow
from stou.domain.values import MaterialKind
from stou.presentation.qt import motion
from stou.presentation.qt.theme import COLORS, SPACE, format_clock
from stou.presentation.qt.worker import run_async
from stou.presentation.services import AppServices
from stou.presentation.widgets.components import (
    GLYPH,
    Card,
    EmptyState,
    label,
    pill,
)
from stou.presentation.widgets.dialogs import AssignSectionsDialog
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
        self._closing = False
        self._showing_solution = False

        self._detail: TaskDetail = self._s.task_detail.execute(task_id=task_id)

        self.setWindowTitle(f"Estudiando · {self._detail.task.title}")
        self.resize(1280, 820)
        self.setMinimumSize(920, 600)

        self._build_ui()

        self._session_id = self._s.start_session.execute(task_id=task_id)

        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        QShortcut(QKeySequence("F11"), self, self._toggle_focus_mode)
        QShortcut(QKeySequence("Ctrl+Return"), self, self._mark_current_studied)
        QShortcut(QKeySequence("Ctrl+W"), self, self.close)

        if self._detail.material:
            self._items.setCurrentRow(0)
        else:
            self._show_no_material()

    # --- construcción ---------------------------------------------------------

    def _build_ui(self) -> None:
        task = self._detail.task

        titles = QVBoxLayout()
        titles.setSpacing(3)
        titles.addWidget(label("MODO ESTUDIO", "Eyebrow"))
        titles.addWidget(label(task.title, "H1"))

        badges = QHBoxLayout()
        badges.setSpacing(SPACE["sm"])
        badges.addWidget(pill(task.category_path or "Sin materia"))
        self._progress_pill = pill(
            f"{task.studied_items}/{task.item_count} estudiado"
            if task.item_count
            else "sin material"
        )
        badges.addWidget(self._progress_pill)
        badges.addStretch(1)
        titles.addLayout(badges)

        self._clock = label("00:00:00", "MetricBig")
        self._clock_state = label("contando", "Faint")

        clock_box = QVBoxLayout()
        clock_box.setSpacing(0)
        clock_box.addWidget(self._clock, 0, Qt.AlignmentFlag.AlignRight)
        clock_box.addWidget(self._clock_state, 0, Qt.AlignmentFlag.AlignRight)

        self._studied_btn = QPushButton(f"{GLYPH['check']}  Marcar estudiada")
        self._studied_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._studied_btn.setToolTip("Ctrl+Intro")
        self._studied_btn.clicked.connect(lambda: self._mark_current_studied())

        focus_btn = QPushButton("Sin distracciones")
        focus_btn.setObjectName("Ghost")
        focus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        focus_btn.setToolTip("F11")
        focus_btn.clicked.connect(lambda: self._toggle_focus_mode())

        finish_btn = QPushButton("Terminar sesión")
        finish_btn.setObjectName("Primary")
        finish_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        finish_btn.clicked.connect(lambda: self.close())

        header = QHBoxLayout()
        header.setSpacing(SPACE["lg"])
        header.addLayout(titles, 1)
        header.addLayout(clock_box)
        header.addWidget(self._studied_btn)
        header.addWidget(focus_btn)
        header.addWidget(finish_btn)

        self._header_holder = QWidget()
        self._header_holder.setLayout(header)

        # --- material de la tarea --------------------------------------------
        self._items = QListWidget()
        self._items.setObjectName("Panel")
        self._items.setFrameShape(QListWidget.Shape.NoFrame)
        self._items.setWordWrap(True)
        self._items.setSpacing(2)
        self._items.currentItemChanged.connect(self._on_item_selected)
        self._refresh_items()

        assign_btn = QPushButton("Asignar más material…")
        assign_btn.setObjectName("Ghost")
        assign_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        assign_btn.clicked.connect(lambda: self._assign_more())

        # La solución se guarda aparte y no se abre sola: verla antes de intentarlo es
        # la forma más rápida de creer que entendiste algo que no entendiste.
        self._solution_btn = QPushButton(f"{GLYPH['check']}  Ver solución")
        self._solution_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._solution_btn.clicked.connect(lambda: self._toggle_solution())
        self._solution_note = label("", "Faint", wrap=True)

        self._left = Card(padding=SPACE["md"])
        self._left.add(label("EN ESTA TAREA", "Eyebrow"))
        self._left.add(self._items, 1)
        self._left.add(assign_btn)
        self._left.add(self._solution_btn)
        self._left.add(self._solution_note)
        self._left.setMinimumWidth(250)
        self._left.setMaximumWidth(340)
        self._refresh_solution_button()

        # --- visor ------------------------------------------------------------
        self._section_title = label("", "H3")
        self._section_range = pill("")
        self._section_range.hide()

        section_row = QHBoxLayout()
        section_row.setSpacing(SPACE["sm"])
        section_row.addWidget(self._section_title)
        section_row.addWidget(self._section_range)
        section_row.addStretch(1)
        self._section_bar = QWidget()
        self._section_bar.setLayout(section_row)

        self._viewer_area = QWidget()
        self._viewer_layout = QVBoxLayout(self._viewer_area)
        self._viewer_layout.setContentsMargins(0, 0, 0, 0)

        self._viewer_stack = QStackedWidget()
        self._viewer_stack.addWidget(self._viewer_area)
        self._viewer_stack.addWidget(self._no_material_state())
        self._viewer_stack.addWidget(
            EmptyState(
                glyph=GLYPH["library"],
                title="Elige algo de la lista",
                body="A la izquierda está el material de esta tarea, en el orden en que "
                "decidiste estudiarlo.",
            )
        )

        center = Card(padding=SPACE["lg"])
        center.add(self._section_bar)
        center.add(self._viewer_stack, 1)

        # --- notas ------------------------------------------------------------
        description = label(self._detail.description or "Sin descripción", "Faint", wrap=True)
        self._notes = QTextEdit()
        self._notes.setPlaceholderText(
            "Escribe aquí lo que vas entendiendo…\n\nAl guardar, queda como una nota "
            "asignada a esta tarea."
        )
        save_note = QPushButton("Guardar como nota")
        save_note.setCursor(Qt.CursorShape.PointingHandCursor)
        save_note.clicked.connect(lambda: self._save_note())

        self._right = Card(padding=SPACE["md"])
        self._right.add(label("OBJETIVO", "Eyebrow"))
        self._right.add(description)
        self._right.add(label("NOTAS", "Eyebrow"))
        self._right.add(self._notes, 1)
        self._right.add(save_note)
        self._right.setMaximumWidth(330)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._left)
        self._splitter.addWidget(center)
        self._splitter.addWidget(self._right)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([270, 780, 320])

        column = QVBoxLayout(self)
        column.setContentsMargins(SPACE["xl"], SPACE["lg"], SPACE["xl"], SPACE["lg"])
        column.setSpacing(SPACE["lg"])
        column.addWidget(self._header_holder)
        column.addWidget(self._splitter, 1)

        self._viewer_stack.setCurrentIndex(2)

    def _no_material_state(self) -> QWidget:
        return EmptyState(
            glyph=GLYPH["import"],
            title="Esta tarea no tiene material asignado",
            body="En STOU una tarea apunta a capítulos concretos. Asígnale secciones y al "
            "abrirla las tendrás aquí mismo, sin buscar archivos. El tiempo se cuenta "
            "igual mientras la ventana esté activa.",
            action="Asignar material ahora",
            on_action=lambda: self._assign_more(),
        )

    def _refresh_items(self) -> None:
        current_id = self._current_item.item_id if self._current_item else None
        self._items.blockSignals(True)
        self._items.clear()
        # Solo el enunciado. La solución vive detrás de su botón.
        visible = self._detail.solutions if self._showing_solution else self._detail.material
        for item in visible:
            mark = GLYPH["check"] if item.studied else "·"
            text = f"{mark}  {item.title}"
            if item.range_label:
                text += f"\n     {item.range_label}"
            entry = QListWidgetItem(text)
            entry.setData(ROLE_ITEM, item)
            if item.studied:
                entry.setForeground(Qt.GlobalColor.gray)
            self._items.addItem(entry)
        self._items.blockSignals(False)

        if current_id:
            for index in range(self._items.count()):
                data: TaskItemRow = self._items.item(index).data(ROLE_ITEM)
                if data.item_id == current_id:
                    self._items.setCurrentRow(index)
                    break

    def _refresh_solution_button(self) -> None:
        """El botón dice la verdad sobre lo que hay: no promete una solución que falta."""
        solutions = self._detail.solutions
        if not solutions:
            self._solution_btn.setEnabled(False)
            self._solution_btn.setText(f"{GLYPH['check']}  Ver solución")
            self._solution_note.setText(
                "Esta tarea no tiene solución guardada. Puedes añadirla desde el menú "
                "de la tarea, en «Añadir solución»."
            )
            return
        self._solution_btn.setEnabled(True)
        if self._showing_solution:
            self._solution_btn.setText(f"{GLYPH['arrow']}  Volver al enunciado")
            self._solution_note.setText("Estás viendo la solución.")
        else:
            self._solution_btn.setText(f"{GLYPH['check']}  Ver solución")
            plural = "" if len(solutions) == 1 else "es"
            self._solution_note.setText(
                f"{len(solutions)} solución{plural} guardada{plural}. Inténtalo antes de abrirla."
            )

    def _toggle_solution(self) -> None:
        if not self._detail.solutions:
            return
        self._showing_solution = not self._showing_solution
        self._refresh_items()
        self._refresh_solution_button()
        if self._items.count():
            self._items.setCurrentRow(0)
        else:
            self._show_no_material()

    def _show_no_material(self) -> None:
        self._viewer_stack.setCurrentIndex(1)
        self._section_title.setText("")
        self._section_range.hide()
        self._studied_btn.setEnabled(False)

    # --- material -------------------------------------------------------------

    def _on_item_selected(self, current: QListWidgetItem | None, _previous) -> None:
        if current is None:
            return
        self._open_item(current.data(ROLE_ITEM))

    def _open_item(self, item: TaskItemRow) -> None:
        self._persist_position()
        self._teardown_viewer()

        self._current_item = item
        self._current_position = 0.0
        source = self._s.resolve_source.execute(material_id=item.material_id)

        epub_documents = None
        if source.kind is MaterialKind.EPUB:
            try:
                epub_documents = self._s.prepare_epub.execute(material_id=item.material_id)
            except Exception:
                epub_documents = []

        viewer = build_viewer(source, epub_documents=epub_documents, parent=self._viewer_area)
        viewer.positionChanged.connect(self._on_position_changed)
        if isinstance(viewer, NoteViewer):
            viewer.saveRequested.connect(
                lambda body, material_id=item.material_id: self._s.update_material.execute(
                    material_id=material_id, body=body
                )
            )

        self._viewer = viewer
        self._viewer_layout.addWidget(viewer, 1)
        self._viewer_stack.setCurrentIndex(0)
        motion.fade_in(viewer, duration=160, start=0.3)

        self._section_title.setText(item.title)
        if item.range_label:
            self._section_range.setText(item.range_label)
            self._section_range.show()
        else:
            self._section_range.hide()

        self._studied_btn.setEnabled(item.section_id is not None)
        self._studied_btn.setText(
            f"{GLYPH['check']}  Ya estudiada"
            if item.studied
            else f"{GLYPH['check']}  Marcar estudiada"
        )

        if item.section_id:
            start = self._section_start(item)
            if start:
                QTimer.singleShot(400, lambda: self._safe_go_to(viewer, start))

        self._had_activity = True

    def _safe_go_to(self, viewer: BaseViewer, position: float) -> None:
        if viewer is self._viewer and motion.is_alive(viewer):
            viewer.go_to(position)

    def _section_start(self, item: TaskItemRow) -> float | None:
        if not item.section_id:
            return None
        for row in self._s.list_sections.execute(material_id=item.material_id):
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
        if self._current_item is None or self._current_position <= 0:
            return
        material_id = self._current_item.material_id
        position = self._current_position
        run_async(
            lambda: self._s.save_position.execute(material_id=material_id, position=position)
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
        media_playing = bool(self._viewer and self._viewer.media_playing)
        had_activity = self._had_activity
        self._had_activity = False

        state = self._s.tick_session.execute(
            session_id=self._session_id,
            had_activity=had_activity,
            media_playing=media_playing,
            material_id=self._current_item.material_id if self._current_item else None,
        )
        if state is None:
            return

        self._clock.setText(format_clock(state.effective_seconds))
        if state.paused:
            self._clock_state.setText("en pausa · sin actividad")
            self._clock.setStyleSheet(f"color: {COLORS['text_faint']};")
        else:
            self._clock_state.setText("contando" + (" · video" if media_playing else ""))
            self._clock.setStyleSheet("")

    # --- acciones -------------------------------------------------------------

    def _mark_current_studied(self) -> None:
        item = self._current_item
        if item is None or not item.section_id:
            QMessageBox.information(
                self,
                "Marcar estudiada",
                "Solo las secciones se marcan como estudiadas. Este material está asignado "
                "completo, sin dividir en capítulos.",
            )
            return
        self._s.mark_studied.execute(section_id=item.section_id, studied=not item.studied)
        self._reload_detail()

    def _assign_more(self) -> None:
        sections = self._s.suggest_sections.execute(
            category_id=self._detail.task.category_id
        )
        if not sections:
            QMessageBox.information(
                self,
                "Nada que asignar",
                "No quedan secciones activas sin estudiar en esta materia. Sube material a "
                "la biblioteca o divide lo que ya tienes en capítulos.",
            )
            return
        dialog = AssignSectionsDialog(sections, parent=self)
        if dialog.exec() != AssignSectionsDialog.DialogCode.Accepted:
            return
        ids = dialog.selected_ids()
        if not ids:
            return
        self._s.assign_material.execute(task_id=self._task_id, section_ids=ids)
        self._reload_detail()
        if self._items.count() and self._current_item is None:
            self._items.setCurrentRow(0)

    def _save_note(self) -> None:
        if not self._notes.toPlainText().strip():
            return
        material_id = self._s.create_note.execute(
            title=f"Notas · {self._detail.task.title}",
            body=self._notes.toHtml(),
            category_id=self._detail.task.category_id,
        )
        self._s.assign_material.execute(task_id=self._task_id, material_id=material_id)
        self._notes.clear()
        self._reload_detail()

    def _reload_detail(self) -> None:
        self._detail = self._s.task_detail.execute(task_id=self._task_id)
        task = self._detail.task
        self._progress_pill.setText(
            f"{task.studied_items}/{task.item_count} estudiado"
            if task.item_count
            else "sin material"
        )
        self._refresh_items()
        self._refresh_solution_button()
        if self._detail.items and self._viewer_stack.currentIndex() == 1:
            self._viewer_stack.setCurrentIndex(2)
            self._studied_btn.setEnabled(True)

    def _toggle_focus_mode(self) -> None:
        self._focus_mode = not self._focus_mode
        self._left.setVisible(not self._focus_mode)
        self._right.setVisible(not self._focus_mode)
        self._header_holder.setVisible(not self._focus_mode)

    # --- cierre ---------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: ANN001, N802 - API de Qt
        if self._closing:
            super().closeEvent(event)
            return
        self._closing = True

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
