"""Piezas comunes a los casos de uso."""

from __future__ import annotations

from stou.application.ports.event_bus import EventBus
from stou.application.ports.unit_of_work import UnitOfWork
from stou.domain.entities.base import Entity
from stou.domain.events import DomainEvent


def commit_and_publish(uow: UnitOfWork, bus: EventBus, *entities: Entity | None) -> None:
    """Cierra la transacción y solo entonces publica los eventos acumulados.

    El orden importa: si se publicara antes del commit, un suscriptor podría leer
    un estado que después se revierte.
    """
    uow.commit()
    events: list[DomainEvent] = []
    for entity in entities:
        if entity is not None:
            events.extend(entity.pull_events())
    bus.publish_all(events)


class NotFound(Exception):
    """La entidad solicitada no existe."""


def require(entity: object | None, message: str) -> None:
    if entity is None:
        raise NotFound(message)
