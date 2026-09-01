"""Agregación de métricas. Funciones puras sobre entidades ya cargadas.

Vive aquí porque Inicio y el Historial responden preguntas distintas con los mismos
cálculos: cuánto tiempo por día, cuánto por materia, cuántos días de racha. Tenerlo
duplicado en los dos casos de uso era la vía rápida para que un día dejaran de
coincidir y el usuario viera dos cifras distintas de lo mismo.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from stou.application import periods
from stou.application.dto import CategoryProgress, CategoryTime, DayTime
from stou.application.mapping import CategoryIndex
from stou.application.periods import Period
from stou.application.ports.unit_of_work import UnitOfWork
from stou.domain.entities.study_session import StudySession
from stou.domain.values import MaterialState
from stou.shared.ids import EntityId

STREAK_LOOKBACK_DAYS = 400


def total_seconds(sessions: list[StudySession]) -> int:
    return sum(s.effective_seconds for s in sessions if s.effective_seconds > 0)


def seconds_by_day(sessions: list[StudySession], window: Period) -> tuple[DayTime, ...]:
    """Tiempo por día local del período, incluidos los días en cero.

    Los días vacíos importan: un gráfico que solo trae los días con actividad miente
    sobre la constancia.
    """
    buckets: dict[date, int] = defaultdict(int)
    for session in sessions:
        if session.effective_seconds > 0:
            buckets[periods.to_local_date(session.started_at)] += session.effective_seconds
    return tuple(DayTime(day=day, seconds=buckets.get(day, 0)) for day in window.days())


def seconds_by_category(
    sessions: list[StudySession], index: CategoryIndex
) -> tuple[CategoryTime, ...]:
    """Tiempo por materia, de más a menos.

    Se atribuye a la categoría que la sesión guardó al nacer, no a la actual de la
    tarea: mover una tarea de materia no reescribe el pasado.
    """
    buckets: dict[EntityId | None, int] = defaultdict(int)
    for session in sessions:
        if session.effective_seconds > 0:
            buckets[session.category_id] += session.effective_seconds
    return tuple(
        sorted(
            (
                CategoryTime(
                    category_id=category_id,
                    category_path=index.path(category_id),
                    color=index.color(category_id),
                    seconds=seconds,
                )
                for category_id, seconds in buckets.items()
            ),
            key=lambda item: item.seconds,
            reverse=True,
        )
    )


def category_progress(uow: UnitOfWork, index: CategoryIndex) -> tuple[CategoryProgress, ...]:
    """Avance del material por materia: cuántas secciones hay, cuántas estudiadas."""
    totals: dict[EntityId, list[int]] = defaultdict(lambda: [0, 0, 0])
    for material in uow.materials.list_all(include_archived=True):
        if material.category_id is None:
            continue
        bucket = totals[material.category_id]
        for section in uow.sections.list_by_material(material.id):
            bucket[0] += 1
            if section.is_studied:
                bucket[1] += 1
            if section.state is MaterialState.ARCHIVED:
                bucket[2] += 1
    return tuple(
        sorted(
            (
                CategoryProgress(
                    category_id=category_id,
                    category_path=index.path(category_id),
                    total_sections=values[0],
                    studied_sections=values[1],
                    archived_sections=values[2],
                )
                for category_id, values in totals.items()
            ),
            key=lambda item: item.category_path,
        )
    )


def streak_days(uow: UnitOfWork, now: datetime) -> int:
    """Días locales seguidos con al menos un segundo efectivo.

    Empieza en hoy si hoy hubo actividad; si no, en ayer. Así la racha no se rompe a
    las nueve de la mañana, antes de que el usuario haya tenido ocasión de estudiar.
    """
    lookback = periods.last_days(now, STREAK_LOOKBACK_DAYS)
    sessions = uow.sessions.list_between(lookback.start, lookback.end)
    active = {
        periods.to_local_date(s.started_at) for s in sessions if s.effective_seconds > 0
    }
    if not active:
        return 0
    today = periods.to_local_date(now)
    cursor = today if today in active else today - timedelta(days=1)
    if cursor not in active:
        return 0
    streak = 0
    while cursor in active:
        streak += 1
        cursor -= timedelta(days=1)
    return streak
