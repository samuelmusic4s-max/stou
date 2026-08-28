"""Casos de uso de la sesión de estudio y del tiempo dedicado."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from stou.application.dto import SessionRow
from stou.application.mapping import CategoryIndex, session_row
from stou.application.ports.event_bus import EventBus
from stou.application.ports.unit_of_work import UnitOfWork
from stou.application.use_cases._shared import commit_and_publish, require
from stou.domain.entities.study_session import (
    DEFAULT_IDLE_THRESHOLD_SECONDS,
    StudySession,
)
from stou.shared.clock import Clock
from stou.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class SessionState:
    session_id: EntityId
    effective_seconds: int
    paused: bool


class StartStudySession:
    """Abre la sesión y pone la tarea en progreso."""

    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(self, *, task_id: EntityId) -> EntityId:
        now = self._clock.now()
        with self._uow as uow:
            task = uow.tasks.get(task_id)
            require(task, "La tarea no existe")
            assert task is not None
            for open_session in uow.sessions.list_open():
                open_session.close(now)
                uow.sessions.update(open_session)

            task.begin(now)
            uow.tasks.update(task)
            session = StudySession.start(
                task_id=task_id, now=now, category_id=task.category_id
            )
            uow.sessions.add(session)
            commit_and_publish(uow, self._bus, session, task)
            return session.id


class TickStudySession:
    """Late cada pocos segundos desde la GUI: acumula o pausa el conteo."""

    def __init__(
        self,
        uow: UnitOfWork,
        bus: EventBus,
        clock: Clock,
        idle_threshold_seconds: int = DEFAULT_IDLE_THRESHOLD_SECONDS,
    ) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock
        self._idle = idle_threshold_seconds

    def execute(
        self,
        *,
        session_id: EntityId,
        had_activity: bool = False,
        media_playing: bool = False,
        material_id: EntityId | None = None,
    ) -> SessionState | None:
        now = self._clock.now()
        with self._uow as uow:
            session = uow.sessions.get(session_id)
            if session is None or not session.is_open:
                return None
            if had_activity:
                session.note_activity(now)
            if material_id is not None and material_id != session.material_id:
                session.focus_material(material_id, now)
            session.tick(now, media_playing=media_playing, idle_threshold_seconds=self._idle)
            uow.sessions.update(session)
            commit_and_publish(uow, self._bus, session)
            return SessionState(
                session_id=session.id,
                effective_seconds=session.effective_seconds,
                paused=session.paused,
            )


class CloseStudySession:
    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(self, *, session_id: EntityId) -> int:
        now = self._clock.now()
        with self._uow as uow:
            session = uow.sessions.get(session_id)
            if session is None:
                return 0
            session.close(now)
            uow.sessions.update(session)
            commit_and_publish(uow, self._bus, session)
            return session.effective_seconds


class CloseAbandonedSessions:
    """Al arrancar: cierra sesiones que quedaron abiertas por un cierre anormal."""

    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(self) -> int:
        with self._uow as uow:
            open_sessions = uow.sessions.list_open()
            for session in open_sessions:
                # Se cierra en su último tick conocido: no se inventa tiempo.
                session.close(session.last_tick_at)
                uow.sessions.update(session)
            commit_and_publish(uow, self._bus, *open_sessions)
            return len(open_sessions)


class AddManualSession:
    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(
        self, *, task_id: EntityId, started_at: datetime, minutes: int
    ) -> EntityId:
        now = self._clock.now()
        with self._uow as uow:
            task = uow.tasks.get(task_id)
            require(task, "La tarea no existe")
            assert task is not None
            session = StudySession.create_manual(
                task_id=task_id,
                started_at=started_at,
                seconds=minutes * 60,
                now=now,
                category_id=task.category_id,
            )
            uow.sessions.add(session)
            commit_and_publish(uow, self._bus, session)
            return session.id


class AdjustSession:
    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(self, *, session_id: EntityId, minutes: int) -> None:
        now = self._clock.now()
        with self._uow as uow:
            session = uow.sessions.get(session_id)
            require(session, "La sesión no existe")
            assert session is not None
            session.adjust(minutes * 60, now)
            uow.sessions.update(session)
            commit_and_publish(uow, self._bus, session)


class DeleteSession:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(self, *, session_id: EntityId) -> None:
        with self._uow as uow:
            uow.sessions.delete(session_id)
            uow.commit()


class ListSessions:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        task_id: EntityId | None = None,
    ) -> list[SessionRow]:
        with self._uow as uow:
            index = CategoryIndex(uow.categories.list_all())
            if task_id is not None:
                sessions = uow.sessions.list_by_task(task_id)
            else:
                if start is None or end is None:
                    raise ValueError("Se necesita un rango de fechas o una tarea")
                sessions = uow.sessions.list_between(start, end)
            rows = []
            for session in sessions:
                task = uow.tasks.get(session.task_id)
                rows.append(session_row(session, task, index))
            return rows
