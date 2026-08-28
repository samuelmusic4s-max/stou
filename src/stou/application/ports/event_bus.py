"""Bus de eventos: puerto de la capa de aplicación.

Los casos de uso publican; los suscriptores registrados en composition reaccionan.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Protocol, TypeVar

from stou.domain.events import DomainEvent

E = TypeVar("E", bound=DomainEvent)
Handler = Callable[[DomainEvent], None]


class EventBus(Protocol):
    def publish(self, event: DomainEvent) -> None: ...

    def publish_all(self, events: Iterable[DomainEvent]) -> None: ...

    def subscribe(self, event_type: type[DomainEvent], handler: Handler) -> None: ...

    def subscribe_all(self, handler: Handler) -> None:
        """Suscribe a todos los eventos. Lo usa el relay hacia la GUI."""
        ...
