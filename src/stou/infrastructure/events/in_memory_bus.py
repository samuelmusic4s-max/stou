"""Bus de eventos en memoria.

Síncrono y con errores aislados: un suscriptor que falla no puede tumbar la
operación que publicó el evento.
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from collections.abc import Iterable

from stou.application.ports.event_bus import Handler
from stou.domain.events import DomainEvent

log = logging.getLogger(__name__)


class InMemoryEventBus:
    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[Handler]] = defaultdict(list)
        self._catch_all: list[Handler] = []
        self._lock = threading.RLock()
        self._history: list[DomainEvent] = []
        self._keep_history = False

    # --- suscripción ----------------------------------------------------------

    def subscribe(self, event_type: type[DomainEvent], handler: Handler) -> None:
        with self._lock:
            self._handlers[event_type].append(handler)

    def subscribe_all(self, handler: Handler) -> None:
        with self._lock:
            self._catch_all.append(handler)

    def unsubscribe(self, handler: Handler) -> None:
        with self._lock:
            for handlers in self._handlers.values():
                if handler in handlers:
                    handlers.remove(handler)
            if handler in self._catch_all:
                self._catch_all.remove(handler)

    # --- publicación ----------------------------------------------------------

    def publish(self, event: DomainEvent) -> None:
        with self._lock:
            specific = list(self._handlers.get(type(event), ()))
            catch_all = list(self._catch_all)
            if self._keep_history:
                self._history.append(event)

        for handler in (*specific, *catch_all):
            try:
                handler(event)
            except Exception:
                log.exception("Falló un suscriptor de %s", event.event_name)

    def publish_all(self, events: Iterable[DomainEvent]) -> None:
        for event in events:
            self.publish(event)

    # --- ayuda para tests -----------------------------------------------------

    def record_history(self, enabled: bool = True) -> None:
        with self._lock:
            self._keep_history = enabled
            if not enabled:
                self._history.clear()

    @property
    def history(self) -> tuple[DomainEvent, ...]:
        with self._lock:
            return tuple(self._history)
