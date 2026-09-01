"""Pantalla de inicio: «qué hago ahora» y «cómo voy».

La pantalla se apoya en tres cosas, en este orden:

1. **Lo pendiente**, ordenado por urgencia. Es lo que gobierna la pantalla.
2. **Lo hecho** en las últimas dos semanas, para ver la constancia sin abrir el
   historial.
3. **El reparto por materia**, porque estudiar mucho no sirve si es siempre lo mismo.

La guía de puesta en marcha solo aparece cuando el sistema está de verdad vacío. En
cuanto hay tareas, la pantalla muestra el trabajo y deja de dar instrucciones.

La regla para elegir la tarea destacada, en orden: la que está en progreso, la más
urgente con fecha, y si no hay fechas, la abierta más antigua.
"""

from __future__ import annotations

from datetime import datetime

from stou.application import metrics, periods
from stou.application.dto import HomeOverview
from stou.application.mapping import CategoryIndex, exam_row, task_row
from stou.application.ports.unit_of_work import UnitOfWork
from stou.domain.entities.task import Task
from stou.domain.values import TaskStatus
from stou.shared.clock import Clock

RECENT_LIMIT = 4
PENDING_LIMIT = 8
# Dos semanas: suficiente para ver un hábito, corto para que un mal día no se pierda.
RECENT_WINDOW_DAYS = 14


class GetHomeOverview:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self) -> HomeOverview:
        now = self._clock.now()
        today = periods.today(now)
        week = periods.current_week(now)
        recent = periods.last_days(now, RECENT_WINDOW_DAYS)

        with self._uow as uow:
            categories = uow.categories.list_all()
            index = CategoryIndex(categories)
            material_count = uow.materials.count()
            open_tasks = uow.tasks.list_all(
                statuses=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS]
            )
            any_task = bool(open_tasks) or bool(uow.tasks.list_all(limit=1))

            step = 0
            if not categories:
                step = 1
            elif material_count == 0:
                step = 2
            elif not any_task:
                step = 3

            spent_by_task = {
                task.id: sum(s.effective_seconds for s in uow.sessions.list_by_task(task.id))
                for task in open_tasks
            }

            chosen = _pick_next(open_tasks, now)
            next_task = (
                task_row(chosen, index, now=now, spent_seconds=spent_by_task.get(chosen.id, 0))
                if chosen
                else None
            )

            pending = tuple(
                task_row(task, index, now=now, spent_seconds=spent_by_task.get(task.id, 0))
                for task in sorted(open_tasks, key=lambda t: _urgency(t, now))[:PENDING_LIMIT]
            )
            recent_tasks = tuple(
                task_row(task, index, now=now)
                for task in sorted(open_tasks, key=lambda t: t.updated_at, reverse=True)[
                    :RECENT_LIMIT
                ]
            )

            today_seconds = metrics.total_seconds(
                uow.sessions.list_between(today.start, today.end)
            )
            week_seconds = metrics.total_seconds(
                uow.sessions.list_between(week.start, week.end)
            )

            recent_sessions = uow.sessions.list_between(recent.start, recent.end)
            recent_days = metrics.seconds_by_day(recent_sessions, recent)
            recent_by_category = metrics.seconds_by_category(recent_sessions, index)
            progress = metrics.category_progress(uow, index)

            unstudied = sum(
                1
                for row in progress
                for _ in range(row.total_sections - row.studied_sections - row.archived_sections)
            )

            exams = uow.exams.list_all(scheduled_from=now, pending_only=True)
            soonest = min(exams, key=lambda e: e.scheduled_at or now) if exams else None
            next_exam = exam_row(soonest, index) if soonest else None
            days_to_exam = (
                (periods.to_local_date(soonest.scheduled_at) - periods.to_local_date(now)).days
                if soonest and soonest.scheduled_at
                else None
            )

            streak = metrics.streak_days(uow, now)

        return HomeOverview(
            onboarding_step=step,
            has_categories=bool(categories),
            has_material=material_count > 0,
            has_tasks=any_task,
            next_task=next_task,
            in_progress=bool(chosen and chosen.status is TaskStatus.IN_PROGRESS),
            recent_tasks=recent_tasks,
            pending_tasks=pending,
            today_seconds=today_seconds,
            week_seconds=week_seconds,
            streak_days=streak,
            open_tasks=len(open_tasks),
            overdue_tasks=sum(1 for t in open_tasks if t.due_at and t.due_at < now),
            material_count=material_count,
            unstudied_sections=max(0, unstudied),
            next_exam=next_exam,
            days_to_exam=days_to_exam,
            recent_days=recent_days,
            recent_by_category=recent_by_category,
            progress=progress,
            recent_window_days=RECENT_WINDOW_DAYS,
            recent_total_seconds=metrics.total_seconds(recent_sessions),
        )


def _urgency(task: Task, now: datetime) -> tuple[int, float]:
    """Orden de lo pendiente: primero lo atrasado, luego por fecha, al final sin fecha."""
    if task.due_at is None:
        return (2, task.created_at.timestamp())
    overdue = task.due_at < now
    return (0 if overdue else 1, task.due_at.timestamp())


def _pick_next(open_tasks: list[Task], now: datetime) -> Task | None:
    if not open_tasks:
        return None

    in_progress = [t for t in open_tasks if t.status is TaskStatus.IN_PROGRESS]
    if in_progress:
        return max(in_progress, key=lambda t: t.updated_at)

    with_due = [t for t in open_tasks if t.due_at is not None]
    if with_due:
        return min(with_due, key=lambda t: t.due_at)  # type: ignore[arg-type,return-value]

    return min(open_tasks, key=lambda t: t.created_at)
