"""Puente entre el bus de eventos y el hilo de la GUI.

Un suscriptor puede ser invocado desde un worker. Tocar widgets desde otro hilo
rompe Qt, así que todo evento se reenvía por una señal, que Qt entrega en el hilo
del receptor.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from stou.application.ports.event_bus import EventBus
from stou.domain.events import DomainEvent


class UiEvents(QObject):
    """Recibe todos los eventos de dominio y los reemite en el hilo de la GUI."""

    received = Signal(object)

    def __init__(self, bus: EventBus) -> None:
        super().__init__()
        self._bus = bus
        bus.subscribe_all(self._forward)

    def _forward(self, event: DomainEvent) -> None:
        self.received.emit(event)

    def on(
        self,
        event_types: type[DomainEvent] | tuple[type[DomainEvent], ...],
        callback: Callable[[DomainEvent], None],
    ) -> None:
        """Ejecuta ``callback`` solo para los tipos indicados."""
        types = event_types if isinstance(event_types, tuple) else (event_types,)

        def dispatch(event: object) -> None:
            if isinstance(event, types):
                callback(event)

        self.received.connect(dispatch)

    def on_any(self, callback: Callable[[DomainEvent], None]) -> None:
        self.received.connect(callback)
