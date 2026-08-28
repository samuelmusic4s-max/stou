"""Movimiento.

El movimiento no es decoración: explica de dónde viene lo que apareció y a dónde
fue lo que se fue. Reglas que sigue esta capa:

- Corto. Nada por encima de 360 ms: una interfaz lenta se siente pesada, no elegante.
- Una sola propiedad a la vez (opacidad o posición), con `OutCubic`.
- Nunca bloquea: si la animación no corre, la interfaz queda igual de usable.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QPoint,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    Qt,
    QTimer,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QStackedWidget, QWidget

from stou.presentation.qt.theme import MOTION

_EASE = QEasingCurve.Type.OutCubic
# Las animaciones se guardan aquí para que el recolector de basura no las mate a
# mitad de camino: es el error clásico con QPropertyAnimation en Python.
_ALIVE: set[QObject] = set()


def is_alive(widget: QWidget) -> bool:
    """¿El objeto C++ detrás del envoltorio de Python todavía existe?

    Qt borra widgets por su cuenta (deleteLater, cambio de padre). Una animación con
    retardo puede despertar cuando su widget ya no está, y tocarlo es un cierre
    abrupto de la aplicación, no una excepción normal.
    """
    try:
        from shiboken6 import isValid

        return bool(isValid(widget))
    except Exception:
        return True


def _keep(animation: QObject) -> None:
    _ALIVE.add(animation)
    animation.finished.connect(lambda: _ALIVE.discard(animation))  # type: ignore[attr-defined]


def fade_in(widget: QWidget, *, duration: int | None = None, start: float = 0.0) -> None:
    """Aparición por opacidad."""
    if not is_alive(widget):
        return
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(start)
    widget.setGraphicsEffect(effect)

    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration or MOTION["base"])
    animation.setStartValue(start)
    animation.setEndValue(1.0)
    animation.setEasingCurve(_EASE)
    # Al terminar se quita el efecto: dejarlo puesto cuesta repintados de más.
    animation.finished.connect(
        lambda: widget.setGraphicsEffect(None) if is_alive(widget) else None
    )
    _keep(animation)
    animation.start()


def rise_in(
    widget: QWidget,
    *,
    distance: int = 14,
    duration: int | None = None,
    delay: int = 0,
) -> None:
    """Entra desde abajo con desvanecido. Es el gesto de «esto acaba de llegar»."""

    def run() -> None:
        # La vista pudo refrescarse y borrar el widget mientras esperaba el retardo.
        if not is_alive(widget) or widget.isHidden():
            return
        target = widget.pos()
        widget.move(target + QPoint(0, distance))

        slide = QPropertyAnimation(widget, b"pos", widget)
        slide.setDuration(duration or MOTION["base"])
        slide.setStartValue(target + QPoint(0, distance))
        slide.setEndValue(target)
        slide.setEasingCurve(_EASE)
        _keep(slide)
        slide.start()
        fade_in(widget, duration=duration)

    if delay:
        # El temporizador se cuelga del widget: si el widget muere, muere con él y
        # nunca dispara sobre un objeto C++ ya destruido.
        timer = QTimer(widget)
        timer.setSingleShot(True)
        timer.timeout.connect(run)
        timer.start(delay)
    else:
        run()


def stagger(widgets: list[QWidget], *, step: int = 45, distance: int = 12) -> None:
    """Entrada en cascada. Da la sensación de que la pantalla se compone sola."""
    for index, widget in enumerate(widgets):
        rise_in(widget, distance=distance, delay=index * step)


def cross_fade(stack: QStackedWidget, index: int, *, duration: int | None = None) -> None:
    """Cambia de vista con un desvanecido en lugar de un corte seco."""
    if index == stack.currentIndex() or not 0 <= index < stack.count():
        stack.setCurrentIndex(index)
        return
    stack.setCurrentIndex(index)
    widget = stack.currentWidget()
    if widget is not None:
        fade_in(widget, duration=duration or MOTION["fast"], start=0.25)


def pulse(widget: QWidget, *, duration: int | None = None) -> None:
    """Latido corto para confirmar que algo pasó donde el usuario estaba mirando."""
    if not is_alive(widget):
        return
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(1.0)
    widget.setGraphicsEffect(effect)

    group = QSequentialAnimationGroup(widget)
    down = QPropertyAnimation(effect, b"opacity")
    down.setDuration((duration or MOTION["base"]) // 2)
    down.setStartValue(1.0)
    down.setEndValue(0.35)
    up = QPropertyAnimation(effect, b"opacity")
    up.setDuration((duration or MOTION["base"]) // 2)
    up.setStartValue(0.35)
    up.setEndValue(1.0)
    group.addAnimation(down)
    group.addAnimation(up)
    group.finished.connect(
        lambda: widget.setGraphicsEffect(None) if is_alive(widget) else None
    )
    _keep(group)
    group.start()


def count_up(
    label_setter: Callable[[int], None],
    *,
    target: int,
    duration: int | None = None,
    steps: int = 18,
) -> None:
    """Cuenta un número hacia arriba. Hace que una métrica se sienta viva."""
    if target <= 0:
        label_setter(target)
        return
    total = duration or MOTION["slow"]
    interval = max(16, total // steps)
    state = {"i": 0}

    timer = QTimer()
    timer.setInterval(interval)

    def tick() -> None:
        state["i"] += 1
        progress = min(1.0, state["i"] / steps)
        # Misma curva que el resto del movimiento, para que se sienta igual.
        eased = 1 - pow(1 - progress, 3)
        label_setter(int(round(target * eased)))
        if progress >= 1.0:
            timer.stop()
            _ALIVE.discard(timer)

    timer.timeout.connect(tick)
    _ALIVE.add(timer)
    timer.start()


def hover_lift(widget: QWidget, *, normal: str, hot: str) -> None:
    """Cambia el nombre de objeto al pasar el ratón, para que el QSS haga el resto."""

    def repolish(name: str) -> None:
        widget.setObjectName(name)
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)

    widget.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
    widget.enterEvent = lambda _event: repolish(hot)  # type: ignore[method-assign]
    widget.leaveEvent = lambda _event: repolish(normal)  # type: ignore[method-assign]
