"""Ventana de visor suelta, para consultar material sin abrir una tarea.

No cuenta tiempo: el tiempo solo se registra dentro de una sesión de estudio.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from stou.domain.values import MaterialKind
from stou.presentation.qt.worker import run_async
from stou.presentation.services import AppServices
from stou.presentation.widgets.viewers import BaseViewer, NoteViewer, build_viewer
from stou.shared.ids import EntityId


class ViewerWindow(QWidget):
    def __init__(
        self,
        services: AppServices,
        material_id: EntityId,
        position: float = 0.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._s = services
        self._material_id = material_id
        self._position = position

        source = services.resolve_source.execute(material_id=material_id)
        self.setWindowTitle(source.title)
        self.setMinimumSize(900, 640)

        epub_docs = None
        if source.kind is MaterialKind.EPUB:
            try:
                epub_docs = services.prepare_epub.execute(material_id=material_id)
            except Exception:
                epub_docs = []

        header = QLabel(source.title)
        header.setObjectName("Title")

        self._viewer: BaseViewer = build_viewer(
            source, epub_documents=epub_docs, parent=self
        )
        self._viewer.positionChanged.connect(self._on_position)
        if isinstance(self._viewer, NoteViewer):
            self._viewer.saveRequested.connect(
                lambda body: self._s.update_material.execute(
                    material_id=material_id, body=body
                )
            )

        layout = QVBoxLayout(self)
        layout.addWidget(header)
        layout.addWidget(self._viewer, 1)

        if position:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(400, lambda: self._viewer.go_to(position))

    def _on_position(self, position: float) -> None:
        self._position = position

    def closeEvent(self, event) -> None:  # noqa: ANN001, N802 - API de Qt
        self._viewer.shutdown()
        if self._position > 0:
            material_id = self._material_id
            position = self._position
            run_async(
                lambda: self._s.save_position.execute(
                    material_id=material_id, position=position
                )
            )
        super().closeEvent(event)
