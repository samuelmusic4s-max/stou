"""Biblioteca: el material y sus secciones.

Dos columnas y nada más: la materia a la izquierda, el material a la derecha, y
debajo las secciones del material elegido. Cada zona vacía dice para qué sirve, en
lugar de mostrar una lista en blanco.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from stou.application.dto import CategoryNode, MaterialRow, SectionRow
from stou.domain.events import (
    CategoryCreated,
    CategoryDeleted,
    CategoryMoved,
    CategoryRenamed,
    MaterialArchived,
    MaterialDeleted,
    MaterialImported,
    MaterialReactivated,
    MaterialUpdated,
    SectionArchived,
    SectionsCreated,
    SectionStudied,
)
from stou.domain.values import MaterialKind
from stou.presentation.qt import motion
from stou.presentation.qt.theme import SPACE, format_size
from stou.presentation.qt.worker import run_async
from stou.presentation.services import AppServices
from stou.presentation.widgets.components import (
    GLYPH,
    Card,
    EmptyState,
    SectionHeader,
    label,
)
from stou.presentation.widgets.dialogs import LinkDialog
from stou.shared.ids import EntityId

ROLE_ID = Qt.ItemDataRole.UserRole

KIND_LABEL = {
    MaterialKind.PDF: "PDF",
    MaterialKind.EPUB: "EPUB",
    MaterialKind.IMAGE: "Imagen",
    MaterialKind.VIDEO: "Video",
    MaterialKind.AUDIO: "Audio",
    MaterialKind.WEB: "Web",
    MaterialKind.YOUTUBE: "YouTube",
    MaterialKind.NOTE: "Nota",
    MaterialKind.OTHER: "Archivo",
}

IMPORT_FILTER = (
    "Material de estudio (*.pdf *.epub *.mp4 *.mkv *.webm *.mov *.mp3 *.m4a *.wav "
    "*.ogg *.flac *.png *.jpg *.jpeg *.webp *.gif *.md *.txt);;"
    "Todos los archivos (*)"
)


class LibraryView(QWidget):
    openMaterialRequested = Signal(str, float)  # material_id, posición

    def __init__(self, services: AppServices, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._s = services
        self._category: EntityId | None = None
        self._material: MaterialRow | None = None

        self._build_ui()
        self._connect_events()
        self.refresh()

    # --- construcción ---------------------------------------------------------

    def _build_ui(self) -> None:
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(label("TU MATERIAL", "Eyebrow"))
        titles.addWidget(label("Biblioteca", "H1"))

        self._import_btn = QPushButton(f"{GLYPH['import']}  Subir material")
        self._import_btn.setObjectName("Primary")
        self._import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._import_btn.clicked.connect(lambda: self.import_files())

        link_btn = QPushButton(f"{GLYPH['link']}  Enlace")
        link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        link_btn.clicked.connect(lambda: self.add_link())

        note_btn = QPushButton(f"{GLYPH['note']}  Nota")
        note_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        note_btn.clicked.connect(lambda: self.create_note())

        header = QHBoxLayout()
        header.setSpacing(SPACE["sm"])
        header.addLayout(titles, 1)
        for widget in (note_btn, link_btn, self._import_btn):
            header.addWidget(widget, 0, Qt.AlignmentFlag.AlignBottom)

        # --- Materias ---------------------------------------------------------
        self._tree = QTreeWidget()
        self._tree.setObjectName("Panel")
        self._tree.setHeaderHidden(True)
        self._tree.setFrameShape(QTreeWidget.Shape.NoFrame)
        self._tree.currentItemChanged.connect(self._on_category_selected)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._category_menu)

        add_category = QPushButton("＋  Nueva materia")
        add_category.setObjectName("Ghost")
        add_category.setCursor(Qt.CursorShape.PointingHandCursor)
        add_category.clicked.connect(lambda: self.create_category())

        categories = Card(padding=SPACE["lg"])
        categories.add(SectionHeader("Materias"))
        categories.add(self._tree, 1)
        categories.add(add_category)
        categories.setMinimumWidth(230)
        categories.setMaximumWidth(320)

        # --- Material ---------------------------------------------------------
        self._search = QLineEdit()
        self._search.setObjectName("Search")
        self._search.setPlaceholderText("Buscar en tu material…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(lambda _: self.refresh_materials())

        self._kind = QComboBox()
        self._kind.addItem("Todo tipo", None)
        for kind, text in KIND_LABEL.items():
            self._kind.addItem(text, kind)
        self._kind.currentIndexChanged.connect(lambda _: self.refresh_materials())

        self._archived = QCheckBox("Ver archivado")
        self._archived.setToolTip(
            "El material archivado salió del circuito activo al aprobar un examen, "
            "pero sigue consultable."
        )
        self._archived.stateChanged.connect(lambda _: self.refresh_materials())

        filters = QHBoxLayout()
        filters.setSpacing(SPACE["md"])
        filters.addWidget(self._search, 1)
        filters.addWidget(self._kind)
        filters.addWidget(self._archived)

        self._materials = QTreeWidget()
        self._materials.setHeaderLabels(["Material", "Tipo", "Materia", "Estudiado", "Tamaño"])
        self._materials.setRootIsDecorated(False)
        self._materials.setFrameShape(QTreeWidget.Shape.NoFrame)
        self._materials.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._materials.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._materials.setUniformRowHeights(True)
        self._materials.currentItemChanged.connect(self._on_material_selected)
        self._materials.itemDoubleClicked.connect(self._open_material_item)
        self._materials.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._materials.customContextMenuRequested.connect(self._material_menu)

        self._material_stack = QStackedWidget()
        self._material_stack.addWidget(self._materials)
        self._material_stack.addWidget(self._materials_empty())

        material_card = Card(padding=SPACE["lg"])
        self._material_header = SectionHeader(
            "Material", subtitle="Doble clic para abrirlo en el visor."
        )
        material_card.add(self._material_header)
        material_card.add(self._material_stack, 1)

        # --- Secciones --------------------------------------------------------
        self._sections = QTreeWidget()
        self._sections.setHeaderLabels(["Sección", "Rango", "Estado"])
        self._sections.setRootIsDecorated(False)
        self._sections.setFrameShape(QTreeWidget.Shape.NoFrame)
        self._sections.setUniformRowHeights(True)
        self._sections.itemDoubleClicked.connect(self._open_section_item)
        self._sections.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._sections.customContextMenuRequested.connect(self._section_menu)

        self._split_btn = QPushButton("Dividir en partes…")
        self._split_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._split_btn.clicked.connect(lambda: self.split_material())
        self._new_section_btn = QPushButton("Nueva sección…")
        self._new_section_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_section_btn.clicked.connect(lambda: self.create_section())

        self._sections_stack = QStackedWidget()
        self._sections_stack.addWidget(self._sections)
        self._sections_stack.addWidget(self._sections_empty())

        sections_card = Card(padding=SPACE["lg"])
        self._sections_header = SectionHeader(
            "Secciones",
            subtitle="Las secciones son lo que asignas a una tarea.",
        )
        sections_card.add(self._sections_header)
        sections_card.add(self._sections_stack, 1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self._new_section_btn)
        buttons.addWidget(self._split_btn)
        holder = QWidget()
        holder.setLayout(buttons)
        sections_card.add(holder)

        right = QSplitter(Qt.Orientation.Vertical)
        right.addWidget(material_card)
        right.addWidget(sections_card)
        right.setStretchFactor(0, 3)
        right.setStretchFactor(1, 2)
        right.setSizes([420, 300])

        right_column = QVBoxLayout()
        right_column.setContentsMargins(0, 0, 0, 0)
        right_column.setSpacing(SPACE["md"])
        right_column.addLayout(filters)
        right_column.addWidget(right, 1)
        right_holder = QWidget()
        right_holder.setLayout(right_column)

        body = QSplitter(Qt.Orientation.Horizontal)
        body.addWidget(categories)
        body.addWidget(right_holder)
        body.setStretchFactor(1, 1)
        body.setSizes([260, 900])

        column = QVBoxLayout(self)
        column.setContentsMargins(SPACE["xl"], SPACE["xl"], SPACE["xl"], SPACE["xl"])
        column.setSpacing(SPACE["lg"])
        column.addLayout(header)
        column.addWidget(body, 1)

    def _materials_empty(self) -> QWidget:
        return EmptyState(
            glyph=GLYPH["library"],
            title="Tu biblioteca está vacía",
            body="Sube un PDF, un EPUB o un video y STOU se queda con una copia propia. "
            "Si el libro tiene índice, lo parte en capítulos automáticamente.",
            action=f"{GLYPH['import']}  Subir material",
            on_action=lambda: self.import_files(),
            secondary="O pega un enlace de YouTube",
            on_secondary=lambda: self.add_link(),
        )

    def _sections_empty(self) -> QWidget:
        return EmptyState(
            glyph=GLYPH["empty"],
            title="Elige un material para ver sus secciones",
            body="Una sección es un tramo estudiable: un capítulo, unas páginas o un "
            "intervalo de video. Es lo que se asigna a una tarea y lo que un examen "
            "archiva al aprobarlo.",
        )

    def _connect_events(self) -> None:
        self._s.events.on(
            (CategoryCreated, CategoryRenamed, CategoryMoved, CategoryDeleted),
            lambda _e: self.refresh_categories(),
        )
        self._s.events.on(
            (
                MaterialImported,
                MaterialUpdated,
                MaterialDeleted,
                MaterialArchived,
                MaterialReactivated,
            ),
            lambda _e: self.refresh_materials(),
        )
        self._s.events.on(
            (SectionsCreated, SectionStudied, SectionArchived),
            lambda _e: self.refresh_sections(),
        )

    # --- datos ----------------------------------------------------------------

    def refresh(self) -> None:
        self.refresh_categories()
        self.refresh_materials()

    def refresh_categories(self) -> None:
        previous = self._category
        self._tree.blockSignals(True)
        self._tree.clear()

        root = QTreeWidgetItem([f"{GLYPH['library']}   Todo el material"])
        root.setData(0, ROLE_ID, None)
        self._tree.addTopLevelItem(root)

        def add(node: CategoryNode, parent: QTreeWidgetItem) -> QTreeWidgetItem | None:
            item = QTreeWidgetItem([node.name])
            item.setData(0, ROLE_ID, node.id)
            parent.addChild(item)
            for child in node.children:
                add(child, item)
            return item

        for node in self._s.category_tree.execute():
            add(node, root)

        self._tree.expandAll()
        self._tree.blockSignals(False)

        if previous is not None and self._select_category(previous):
            return
        self._tree.setCurrentItem(root)

    def _select_category(self, category_id: EntityId) -> bool:
        for item in self._tree.findItems(
            "", Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive, 0
        ):
            if item.data(0, ROLE_ID) == category_id:
                self._tree.setCurrentItem(item)
                return True
        return False

    def refresh_materials(self) -> None:
        rows = self._s.list_materials.execute(
            category_id=self._category,
            kinds=[self._kind.currentData()] if self._kind.currentData() else None,
            include_archived=self._archived.isChecked(),
            search=self._search.text().strip() or None,
        )
        self._materials.clear()
        for row in rows:
            item = QTreeWidgetItem(
                [
                    row.title,
                    KIND_LABEL.get(row.kind, str(row.kind)),
                    row.category_path,
                    f"{row.studied_sections}/{row.section_count}" if row.section_count else "—",
                    format_size(row.size_bytes) if row.size_bytes else "—",
                ]
            )
            if row.archived:
                item.setText(1, f"{item.text(1)} · archivado")
            item.setData(0, ROLE_ID, row)
            self._materials.addTopLevelItem(item)

        searching = bool(self._search.text().strip()) or self._kind.currentData() is not None
        self._material_stack.setCurrentIndex(0 if rows or searching else 1)
        if rows:
            motion.fade_in(self._materials, duration=140, start=0.5)

        total = len(rows)
        self._material_header.set_subtitle(
            f"{total} elemento(s) · doble clic para abrir en el visor"
            if total
            else "Ningún material coincide con el filtro"
        )
        self._material = None
        self.refresh_sections()

    def refresh_sections(self) -> None:
        material = self._material
        self._sections.clear()
        if material is None:
            self._sections_stack.setCurrentIndex(1)
            self._sections_header.set_subtitle(
                "Las secciones son lo que asignas a una tarea."
            )
            self._split_btn.setEnabled(False)
            self._new_section_btn.setEnabled(False)
            return

        self._split_btn.setEnabled(True)
        self._new_section_btn.setEnabled(True)
        rows = self._s.list_sections.execute(material_id=material.id, include_archived=True)
        for row in rows:
            item = QTreeWidgetItem(
                [
                    "     " * row.level + row.title,
                    row.range_label or "—",
                    "archivada" if row.archived else ("estudiada" if row.studied else "activa"),
                ]
            )
            item.setData(0, ROLE_ID, row)
            self._sections.addTopLevelItem(item)

        if rows:
            self._sections_stack.setCurrentIndex(0)
            studied = sum(1 for r in rows if r.studied)
            self._sections_header.set_subtitle(
                f"«{material.title}» · {len(rows)} secciones · {studied} estudiadas"
            )
        else:
            self._sections_stack.setCurrentIndex(1)
            self._sections_header.set_subtitle(
                f"«{material.title}» no tiene secciones. Divídelo en partes para poder "
                "asignarlo a una tarea."
            )

    # --- selección ------------------------------------------------------------

    def _on_category_selected(self, current: QTreeWidgetItem | None, _previous) -> None:
        self._category = current.data(0, ROLE_ID) if current else None
        self.refresh_materials()

    def _on_material_selected(self, current: QTreeWidgetItem | None, _previous) -> None:
        self._material = current.data(0, ROLE_ID) if current else None
        self.refresh_sections()

    def selected_material(self) -> MaterialRow | None:
        return self._material

    def focus_search(self) -> None:
        self._search.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def material_titles(self) -> list[str]:
        return [
            self._materials.topLevelItem(i).data(0, ROLE_ID).title
            for i in range(self._materials.topLevelItemCount())
        ]

    # --- acciones -------------------------------------------------------------

    def create_category(self) -> EntityId | None:
        name, ok = QInputDialog.getText(
            self,
            "Nueva materia",
            "Nombre de la materia:\n(puedes anidarla luego arrastrando o desde su menú)",
        )
        if not ok or not name.strip():
            return None
        try:
            return self._s.create_category.execute(name=name, parent_id=self._category)
        except Exception as exc:
            QMessageBox.warning(self, "No se pudo crear la materia", str(exc))
            return None

    def import_files(self) -> None:
        paths, _filter = QFileDialog.getOpenFileNames(
            self, "Subir material a la biblioteca", str(Path.home()), IMPORT_FILTER
        )
        if not paths:
            return
        files = [Path(p) for p in paths]
        category_id = self._category
        self._material_header.set_subtitle(
            f"Copiando {len(files)} archivo(s) y leyendo su índice…"
        )
        run_async(
            lambda: self._s.import_files.execute(paths=files, category_id=category_id),
            on_done=self._on_import_done,
            on_error=lambda message: QMessageBox.warning(
                self, "Falló la importación", message
            ),
        )

    def _on_import_done(self, outcome) -> None:  # noqa: ANN001
        self.refresh_materials()
        if outcome.failed:
            detail = "\n".join(f"· {name}: {reason}" for name, reason in outcome.failed)
            QMessageBox.warning(
                self,
                "Algunos archivos no entraron",
                f"{len(outcome.failed)} de {len(outcome.failed) + len(outcome.imported)} "
                f"archivos fallaron:\n\n{detail}",
            )
        elif outcome.duplicates and not outcome.imported:
            QMessageBox.information(
                self,
                "Ya estaba en la biblioteca",
                "Ese material ya existe: STOU reconoce los archivos por su contenido, "
                "aunque el nombre sea distinto.",
            )

    def add_link(self) -> None:
        dialog = LinkDialog(parent=self)
        if dialog.exec() != LinkDialog.DialogCode.Accepted:
            return
        url = dialog.url()
        if not url:
            return
        try:
            self._s.add_link.execute(
                url=url, title=dialog.title(), category_id=self._category
            )
        except Exception as exc:
            QMessageBox.warning(self, "No se pudo agregar el enlace", str(exc))

    def create_note(self) -> None:
        title, ok = QInputDialog.getText(self, "Nueva nota", "Título de la nota:")
        if not ok or not title.strip():
            return
        material_id = self._s.create_note.execute(title=title, category_id=self._category)
        self.openMaterialRequested.emit(material_id, 0.0)

    def split_material(self) -> None:
        material = self._material
        if material is None:
            QMessageBox.information(
                self, "Dividir material", "Elige primero un material de la lista."
            )
            return
        parts, ok = QInputDialog.getInt(
            self,
            "Dividir material",
            "¿En cuántas partes iguales?\nSe reemplazan las secciones actuales.",
            10,
            1,
            500,
        )
        if not ok:
            return
        try:
            self._s.split_material.execute(material_id=material.id, parts=parts)
        except Exception as exc:
            QMessageBox.warning(self, "No se pudo dividir", str(exc))
            return
        self.refresh_sections()

    def create_section(self) -> None:
        material = self._material
        if material is None:
            QMessageBox.information(
                self, "Nueva sección", "Elige primero un material de la lista."
            )
            return
        title, ok = QInputDialog.getText(self, "Nueva sección", "Título:")
        if not ok or not title.strip():
            return
        start, ok = QInputDialog.getDouble(
            self, "Nueva sección", "Empieza en (página o segundo):", 1, 0, 1e9, 2
        )
        if not ok:
            return
        end, ok = QInputDialog.getDouble(
            self, "Nueva sección", "Termina en (0 = hasta el final):", 0, 0, 1e9, 2
        )
        if not ok:
            return
        try:
            self._s.create_section.execute(
                material_id=material.id, title=title, start=start, end=end or None
            )
        except Exception as exc:
            QMessageBox.warning(self, "No se pudo crear la sección", str(exc))
            return
        self.refresh_sections()

    # --- menús contextuales ---------------------------------------------------

    def _category_menu(self, position) -> None:  # noqa: ANN001
        item = self._tree.itemAt(position)
        if item is None or item.data(0, ROLE_ID) is None:
            return
        category_id = item.data(0, ROLE_ID)

        menu = QMenu(self)
        rename = menu.addAction("Renombrar…")
        sub = menu.addAction("Nueva submateria…")
        menu.addSeparator()
        delete = menu.addAction("Eliminar")

        chosen = menu.exec(self._tree.viewport().mapToGlobal(position))
        if chosen is None:
            return
        if chosen == rename:
            name, ok = QInputDialog.getText(
                self, "Renombrar materia", "Nombre:", text=item.text(0)
            )
            if ok and name.strip():
                self._s.rename_category.execute(category_id=category_id, name=name)
        elif chosen == sub:
            name, ok = QInputDialog.getText(self, "Nueva submateria", "Nombre:")
            if ok and name.strip():
                self._s.create_category.execute(name=name, parent_id=category_id)
        elif chosen == delete:
            try:
                self._s.delete_category.execute(category_id=category_id)
            except Exception as exc:
                QMessageBox.warning(self, "No se pudo eliminar", str(exc))

    def _material_menu(self, position) -> None:  # noqa: ANN001
        item = self._materials.itemAt(position)
        if item is None:
            return
        row: MaterialRow = item.data(0, ROLE_ID)

        menu = QMenu(self)
        open_action = menu.addAction("Abrir en el visor")
        rename = menu.addAction("Renombrar…")
        menu.addSeparator()
        archive = menu.addAction("Reactivar" if row.archived else "Archivar")
        delete = menu.addAction("Eliminar de la biblioteca")

        chosen = menu.exec(self._materials.viewport().mapToGlobal(position))
        if chosen is None:
            return
        if chosen == open_action:
            self.openMaterialRequested.emit(row.id, 0.0)
        elif chosen == rename:
            title, ok = QInputDialog.getText(
                self, "Renombrar material", "Título:", text=row.title
            )
            if ok and title.strip():
                self._s.update_material.execute(material_id=row.id, title=title)
        elif chosen == archive:
            self._s.set_material_state.execute(material_id=row.id, archived=not row.archived)
        elif chosen == delete:
            confirm = QMessageBox.question(
                self,
                "Eliminar material",
                f"¿Eliminar «{row.title}» y su copia interna?\n\nSe quitará también de las "
                "tareas que lo tengan asignado. Esta acción no se puede deshacer.",
            )
            if confirm == QMessageBox.StandardButton.Yes:
                self._s.delete_material.execute(material_id=row.id)

    def _section_menu(self, position) -> None:  # noqa: ANN001
        item = self._sections.itemAt(position)
        if item is None:
            return
        row: SectionRow = item.data(0, ROLE_ID)

        menu = QMenu(self)
        open_action = menu.addAction("Abrir en el visor")
        rename = menu.addAction("Renombrar…")
        studied = menu.addAction(
            "Marcar como no estudiada" if row.studied else "Marcar estudiada"
        )
        menu.addSeparator()
        delete = menu.addAction("Eliminar sección")

        chosen = menu.exec(self._sections.viewport().mapToGlobal(position))
        if chosen is None:
            return
        if chosen == open_action:
            self.openMaterialRequested.emit(row.material_id, row.start)
        elif chosen == rename:
            title, ok = QInputDialog.getText(
                self, "Renombrar sección", "Título:", text=row.title
            )
            if ok and title.strip():
                self._s.update_section.execute(section_id=row.id, title=title)
                self.refresh_sections()
        elif chosen == studied:
            self._s.mark_studied.execute(section_id=row.id, studied=not row.studied)
        elif chosen == delete:
            self._s.delete_section.execute(section_id=row.id)
            self.refresh_sections()

    # --- apertura -------------------------------------------------------------

    def _open_material_item(self, item: QTreeWidgetItem, _column: int) -> None:
        row: MaterialRow = item.data(0, ROLE_ID)
        self.openMaterialRequested.emit(row.id, 0.0)

    def _open_section_item(self, item: QTreeWidgetItem, _column: int) -> None:
        row: SectionRow = item.data(0, ROLE_ID)
        self.openMaterialRequested.emit(row.material_id, row.start)
