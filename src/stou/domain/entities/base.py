"""Base de entidades: identidad y registro de eventos."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from stou.domain.events import DomainEvent
from stou.shared.ids import EntityId


@dataclass(kw_only=True)
class Entity:
    id: EntityId
    created_at: datetime
    updated_at: datetime
    _events: list[DomainEvent] = field(default_factory=list, repr=False, compare=False)

    def record(self, event: DomainEvent, at: datetime | None = None) -> None:
        """Registra un hecho ocurrido. El caso de uso lo publicará tras el commit."""
        moment = at or self.updated_at
        if event.occurred_at is None:
            event = type(event)(
                **{**{f: getattr(event, f) for f in _fields_of(event)}, "occurred_at": moment}
            )
        self._events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        events, self._events = self._events, []
        return events

    def touch(self, at: datetime) -> None:
        self.updated_at = at

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Entity) and type(self) is type(other) and self.id == other.id

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.id))


def _fields_of(event: DomainEvent) -> tuple[str, ...]:
    from dataclasses import fields

    return tuple(f.name for f in fields(event))
