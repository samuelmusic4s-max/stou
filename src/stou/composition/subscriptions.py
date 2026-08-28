"""Suscriptores de eventos.

Aquí se conecta el trabajo derivado: lo que debe pasar *como consecuencia* de un
hecho, sin que el caso de uso que lo provocó tenga que saberlo.
"""

from __future__ import annotations

import logging

from stou.application.ports.event_bus import EventBus
from stou.domain.events import (
    DomainEvent,
    ExamRecorded,
    MaterialImported,
    StudySessionClosed,
)

log = logging.getLogger("stou.events")


def register(bus: EventBus) -> None:
    bus.subscribe(MaterialImported, _log_import)
    bus.subscribe(StudySessionClosed, _log_session)
    bus.subscribe(ExamRecorded, _log_exam)


def _log_import(event: DomainEvent) -> None:
    assert isinstance(event, MaterialImported)
    log.info("Material importado: %s (%s)", event.title, event.kind)


def _log_session(event: DomainEvent) -> None:
    assert isinstance(event, StudySessionClosed)
    log.info(
        "Sesión cerrada de la tarea %s: %d s efectivos",
        event.task_id,
        event.effective_seconds,
    )


def _log_exam(event: DomainEvent) -> None:
    assert isinstance(event, ExamRecorded)
    log.info(
        "Examen %s registrado como %s; %d secciones archivadas",
        event.exam_id,
        event.result,
        len(event.archived_section_ids),
    )
