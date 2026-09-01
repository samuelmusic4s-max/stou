"""Componentes de interfaz reutilizables.

El objetivo de estos componentes es que ninguna pantalla tenga que explicar dos
veces cómo se ve una acción, una métrica o un estado vacío.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from stou.presentation.qt import motion
from stou.presentation.qt.theme import SPACE

# Glifos monocromos en vez de emoji: se ven dibujados, no pegados.
GLYPH = {
    "home": "◈",
    "study": "▶",
    "library": "▤",
    "tasks": "◎",
    "calendar": "▦",
    "dashboard": "◔",
    "import": "↥",
    "link": "⚯",
    "note": "✎",
    "category": "⌂",
    "exam": "★",
    "time": "◴",
    "streak": "⟡",
    "empty": "○",
    "arrow": "→",
    "check": "✓",
}


def label(
    text: str,
    role: str = "",
    *,
    wrap: bool = False,
    align: Qt.AlignmentFlag | None = None,
) -> QLabel:
    """Etiqueta con un rol tipográfico del tema."""
    widget = QLabel(text)
    if role:
        widget.setObjectName(role)
    widget.setWordWrap(wrap)
    if align is not None:
        widget.setAlignment(align)
    return widget


def pill(text: str, tone: str = "") -> QLabel:
    """Etiqueta de estado. Tonos: '', 'Accent', 'Ok', 'Warn', 'Danger'."""
    widget = QLabel(text)
    widget.setObjectName(f"Pill{tone}")
    widget.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
    return widget


def divider() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFixedHeight(1)
    return line


def spacer(height: int = 0) -> QWidget:
    widget = QWidget()
    if height:
        widget.setFixedHeight(height)
    else:
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    return widget


class Card(QFrame):
    """Superficie con aire. Sin borde: la separación la da el fondo."""

    def __init__(
        self,
        *,
        padding: int = SPACE["xl"],
        variant: str = "Card",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(variant)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(padding, padding, padding, padding)
        self.body.setSpacing(SPACE["md"])

    def add(self, widget: QWidget, stretch: int = 0) -> QWidget:
        self.body.addWidget(widget, stretch)
        return widget


class SectionHeader(QWidget):
    """Título de sección con una acción opcional a la derecha."""

    def __init__(
        self,
        title: str,
        *,
        subtitle: str = "",
        action: str = "",
        on_action: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(SPACE["md"])

        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(label(title, "H2"))
        if subtitle:
            self.subtitle = label(subtitle, "Dim", wrap=True)
            titles.addWidget(self.subtitle)
        else:
            self.subtitle = None
        row.addLayout(titles, 1)

        if action:
            button = QPushButton(action)
            button.setObjectName("Link")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            if on_action is not None:
                button.clicked.connect(lambda: on_action())
            row.addWidget(button, 0, Qt.AlignmentFlag.AlignBottom)
            self.action_button = button
        else:
            self.action_button = None

    def set_subtitle(self, text: str) -> None:
        if self.subtitle is not None:
            self.subtitle.setText(text)


class ActionCard(QFrame):
    """Tarjeta clicable: la unidad de «qué puedo hacer aquí».

    Es un solo objetivo de clic con un glifo, un título y una frase que explica el
    resultado de pulsarla. Que sea la tarjeta entera y no un botón pequeño es
    deliberado: reduce la puntería necesaria y hace obvio que es accionable.

    Con ``compact=True`` se dispone en una sola fila. La versión alta tenía sentido en
    una rejilla de tres, pero como banda de ancho completo dejaba un hueco enorme entre
    el glifo y el título: mucho aire y poca información.
    """

    clicked = Signal()

    def __init__(
        self,
        *,
        glyph: str,
        title: str,
        description: str,
        hint: str = "",
        primary: bool = False,
        compact: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._variant = "CardAccent" if primary else "ActionCard"
        self._variant_hot = "CardAccent" if primary else "ActionCardHot"
        self.setObjectName(self._variant)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        if compact:
            self._build_compact(glyph=glyph, title=title, description=description, hint=hint)
        else:
            self._build_tall(
                glyph=glyph, title=title, description=description, hint=hint, primary=primary
            )

        motion.hover_lift(self, normal=self._variant, hot=self._variant_hot)

    def _build_compact(self, *, glyph: str, title: str, description: str, hint: str) -> None:
        self.setMinimumHeight(88)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        row = QHBoxLayout(self)
        row.setContentsMargins(SPACE["xl"], SPACE["lg"], SPACE["xl"], SPACE["lg"])
        row.setSpacing(SPACE["lg"])

        mark = label(glyph, "Glyph")
        mark.setFixedWidth(28)
        row.addWidget(mark)

        texts = QVBoxLayout()
        texts.setSpacing(2)
        texts.addWidget(label(title, "H2", wrap=True))
        self._description = label(description, "Dim", wrap=True)
        texts.addWidget(self._description)
        row.addLayout(texts, 1)

        if hint:
            row.addWidget(pill(hint, "Accent"))

    def _build_tall(
        self, *, glyph: str, title: str, description: str, hint: str, primary: bool
    ) -> None:
        self.setMinimumHeight(132)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        column = QVBoxLayout(self)
        column.setContentsMargins(SPACE["xl"], SPACE["lg"], SPACE["xl"], SPACE["lg"])
        column.setSpacing(SPACE["sm"])

        top = QHBoxLayout()
        top.setSpacing(SPACE["md"])
        top.addWidget(label(glyph, "Glyph"))
        top.addStretch(1)
        if hint:
            top.addWidget(pill(hint, "Accent" if primary else ""))
        column.addLayout(top)

        column.addStretch(1)
        column.addWidget(label(title, "H2", wrap=True))
        self._description = label(description, "Dim", wrap=True)
        column.addWidget(self._description)

    def set_description(self, text: str) -> None:
        self._description.setText(text)

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001, N802 - API de Qt
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class MetricTile(QFrame):
    """Una cifra con su nombre. Nada más: la comparación la hace la vista."""

    def __init__(
        self,
        caption: str,
        *,
        glyph: str = "",
        big: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        column = QVBoxLayout(self)
        column.setContentsMargins(SPACE["lg"], SPACE["lg"], SPACE["lg"], SPACE["lg"])
        column.setSpacing(SPACE["xs"])

        top = QHBoxLayout()
        top.setSpacing(SPACE["sm"])
        top.addWidget(label(caption.upper(), "Eyebrow"))
        top.addStretch(1)
        if glyph:
            top.addWidget(label(glyph, "Faint"))
        column.addLayout(top)

        self._value = label("—", "MetricBig" if big else "MetricMedium")
        column.addWidget(self._value)
        self._note = label("", "Faint", wrap=True)
        column.addWidget(self._note)

    def set_value(self, value: str) -> None:
        self._value.setText(value)

    def set_note(self, note: str) -> None:
        self._note.setText(note)

    @property
    def value_label(self) -> QLabel:
        return self._value


class EmptyState(QWidget):
    """Lo que se ve cuando no hay nada.

    Un vacío no es un error: es el momento en que el usuario más necesita que le
    digan qué hacer. Por eso lleva glifo, una frase que explica para qué sirve
    esta pantalla, y un botón que ejecuta la acción de la que habla.
    """

    def __init__(
        self,
        *,
        glyph: str,
        title: str,
        body: str,
        action: str = "",
        on_action: Callable[[], None] | None = None,
        secondary: str = "",
        on_secondary: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        column = QVBoxLayout(self)
        column.setContentsMargins(SPACE["xl"], SPACE["2xl"], SPACE["xl"], SPACE["2xl"])
        column.setSpacing(SPACE["sm"])
        column.setAlignment(Qt.AlignmentFlag.AlignCenter)

        center = Qt.AlignmentFlag.AlignHCenter
        column.addStretch(1)
        column.addWidget(label(glyph, "GlyphLarge", align=center))
        column.addSpacing(SPACE["sm"])
        column.addWidget(label(title, "H2", align=center))

        message = label(body, "Dim", wrap=True, align=center)
        message.setMaximumWidth(460)
        column.addWidget(message, 0, center)

        if action:
            column.addSpacing(SPACE["lg"])
            button = QPushButton(action)
            button.setObjectName("Primary")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            if on_action is not None:
                button.clicked.connect(lambda: on_action())
            column.addWidget(button, 0, center)
            self.action_button = button
        else:
            self.action_button = None

        if secondary:
            link = QPushButton(secondary)
            link.setObjectName("Link")
            link.setCursor(Qt.CursorShape.PointingHandCursor)
            if on_secondary is not None:
                link.clicked.connect(lambda: on_secondary())
            column.addWidget(link, 0, center)
            self.secondary_button = link
        else:
            self.secondary_button = None

        column.addStretch(1)


class StepRow(QWidget):
    """Un paso de la puesta en marcha: hecho, actual o por venir.

    Solo el paso actual muestra su botón. Tres botones a la vez no son una guía,
    son otra decisión que tomar.
    """

    action = Signal()

    def __init__(
        self,
        *,
        number: int,
        title: str,
        description: str,
        action_text: str,
        state: str = "todo",  # done | current | todo
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, SPACE["sm"], 0, SPACE["sm"])
        row.setSpacing(SPACE["lg"])

        done = state == "done"
        badge = label(GLYPH["check"] if done else str(number), "H3")
        badge.setFixedSize(30, 30)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setObjectName("PillOk" if done else ("PillAccent" if state == "current" else "Pill"))
        row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)

        texts = QVBoxLayout()
        texts.setSpacing(2)
        title_label = label(title, "H3")
        if done:
            title_label.setObjectName("Dim")
        texts.addWidget(title_label)
        texts.addWidget(label(description, "Faint", wrap=True))
        row.addLayout(texts, 1)

        if state == "current":
            button = QPushButton(action_text)
            button.setObjectName("Primary")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda: self.action.emit())
            row.addWidget(button, 0, Qt.AlignmentFlag.AlignVCenter)
            self.action_button = button
        else:
            self.action_button = None
            row.addWidget(pill("listo" if done else "pendiente", "Ok" if done else ""))


class ListRow(QWidget):
    """Fila de lista con aire: glifo, título, subtítulo y una píldora al final."""

    def __init__(
        self,
        *,
        glyph: str,
        title: str,
        subtitle: str = "",
        tag: str = "",
        tone: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(SPACE["md"], SPACE["sm"], SPACE["md"], SPACE["sm"])
        row.setSpacing(SPACE["md"])

        mark = label(glyph, "Dim")
        mark.setFixedWidth(20)
        row.addWidget(mark)

        texts = QVBoxLayout()
        texts.setSpacing(1)
        texts.addWidget(label(title, "H3"))
        if subtitle:
            texts.addWidget(label(subtitle, "Faint"))
        row.addLayout(texts, 1)

        if tag:
            row.addWidget(pill(tag, tone))
