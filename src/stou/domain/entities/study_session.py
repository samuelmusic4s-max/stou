"""Sesión de estudio: el tiempo que realmente se dedicó a una tarea.

El conteo tiene dos condiciones para seguir corriendo: que haya habido
interacción reciente, o que un medio esté reproduciéndose. Sin la segunda, ver un
video de 40 minutos sin tocar el teclado se registraría como unos pocos minutos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from stou.domain.entities.base import Entity
from stou.domain.events import (
    StudySessionClosed,
    StudySessionPaused,
    StudySessionResumed,
    StudySessionStarted,
)
from stou.shared.ids import EntityId, new_id

DEFAULT_IDLE_THRESHOLD_SECONDS = 300


@dataclass(kw_only=True)
class StudySession(Entity):
    task_id: EntityId
    category_id: EntityId | None = None
    started_at: datetime
    ended_at: datetime | None = None
    last_activity_at: datetime
    last_tick_at: datetime
    accumulated_seconds: float = 0.0
    paused: bool = False
    material_id: EntityId | None = None
    manual: bool = False

    @classmethod
    def start(
        cls,
        *,
        task_id: EntityId,
        now: datetime,
        category_id: EntityId | None = None,
        material_id: EntityId | None = None,
    ) -> StudySession:
        session = cls(
            id=new_id(),
            created_at=now,
            updated_at=now,
            task_id=task_id,
            category_id=category_id,
            started_at=now,
            last_activity_at=now,
            last_tick_at=now,
            material_id=material_id,
        )
        session.record(StudySessionStarted(session_id=session.id, task_id=task_id), at=now)
        return session

    @classmethod
    def create_manual(
        cls,
        *,
        task_id: EntityId,
        started_at: datetime,
        seconds: int,
        now: datetime,
        category_id: EntityId | None = None,
    ) -> StudySession:
        if seconds <= 0:
            raise ValueError("Una sesión manual necesita una duración positiva")
        ended_at = started_at + timedelta(seconds=seconds)
        session = cls(
            id=new_id(),
            created_at=now,
            updated_at=now,
            task_id=task_id,
            category_id=category_id,
            started_at=started_at,
            ended_at=ended_at,
            last_activity_at=ended_at,
            last_tick_at=ended_at,
            accumulated_seconds=float(seconds),
            manual=True,
        )
        session.record(StudySessionStarted(session_id=session.id, task_id=task_id), at=now)
        session.record(
            StudySessionClosed(
                session_id=session.id, task_id=task_id, effective_seconds=seconds
            ),
            at=now,
        )
        return session

    # --- conteo ---------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return self.ended_at is None

    @property
    def effective_seconds(self) -> int:
        return int(self.accumulated_seconds)

    def note_activity(self, now: datetime) -> None:
        """Registra interacción del usuario."""
        if not self.is_open:
            return
        if now > self.last_activity_at:
            self.last_activity_at = now

    def focus_material(self, material_id: EntityId | None, now: datetime) -> None:
        self.material_id = material_id
        self.note_activity(now)
        self.touch(now)

    def tick(
        self,
        now: datetime,
        *,
        media_playing: bool = False,
        idle_threshold_seconds: int = DEFAULT_IDLE_THRESHOLD_SECONDS,
    ) -> None:
        """Acumula el tiempo transcurrido desde el tick anterior que cuenta como trabajo."""
        if not self.is_open:
            return
        if now <= self.last_tick_at:
            return

        # Si veníamos en pausa, el tramo anterior a la primera interacción no cuenta:
        # el usuario no estaba trabajando aunque la ventana siguiera abierta.
        window_start = self.last_tick_at
        if self.paused:
            window_start = max(window_start, min(self.last_activity_at, now))

        if media_playing:
            countable_until = now
            self.last_activity_at = now
        else:
            countable_until = min(
                now, self.last_activity_at + timedelta(seconds=idle_threshold_seconds)
            )

        if countable_until > window_start:
            self.accumulated_seconds += (countable_until - window_start).total_seconds()
            if self.paused:
                self.paused = False
                self.record(StudySessionResumed(session_id=self.id), at=now)

        should_pause = countable_until < now
        if should_pause and not self.paused:
            self.paused = True
            self.record(StudySessionPaused(session_id=self.id, reason="inactividad"), at=now)

        self.last_tick_at = now
        self.touch(now)

    def close(self, now: datetime) -> None:
        if not self.is_open:
            return
        self.tick(now)
        self.ended_at = now
        self.paused = False
        self.touch(now)
        self.record(
            StudySessionClosed(
                session_id=self.id,
                task_id=self.task_id,
                effective_seconds=self.effective_seconds,
            ),
            at=now,
        )

    def adjust(self, seconds: int, now: datetime) -> None:
        """Corrección manual del tiempo registrado."""
        if seconds < 0:
            raise ValueError("El tiempo registrado no puede ser negativo")
        self.accumulated_seconds = float(seconds)
        self.touch(now)
