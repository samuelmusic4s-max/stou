"""Pantalla de inicio: la única pregunta que responde es «qué hago ahora».

La regla de decisión, en orden:

1. Si falta poner en marcha el sistema (categoría, material, tarea), lo que toca es
   el siguiente paso de la puesta en marcha.
2. Si hay una tarea en progreso, lo que toca es retomarla.
3. Si hay tareas atrasadas o con fecha próxima, lo que toca es la más urgente.
4. Si no, la tarea abierta más antigua.
"""

from __future__ import annotations

from stou.application import periods
from stou.application.dto import HomeOverview
from stou.application.mapping import CategoryIndex, exam_row, task_row
from stou.application.ports.unit_of_work import UnitOfWork
from stou.domain.entities.task import Task
from stou.domain.values import TaskStatus
from stou.shared.clock import Clock

RECENT_LIMIT = 4


class GetHomeOverview:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self) -> HomeOverview:
        now = self._clock.now()
        today = periods.today(now)
        week = periods.current_week(now)

        with self._uow as uow:
            index = CategoryIndex(uow.categories.list_all())
            has_categories = bool(uow.categories.list_all())
            material_count = uow.materials.count()
            open_tasks = uow.tasks.list_all(
                statuses=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS]
            )
            any_task = bool(open_tasks) or bool(uow.tasks.list_all(limit=1))

            step = 0
            if not has_categories:
                step = 1
            elif material_count == 0:
                step = 2
            elif not any_task:
                step = 3

            chosen = _pick_next(open_tasks, now)
            spent = (
                sum(s.effective_seconds for s in uow.sessions.list_by_task(chosen.id))
                if chosen
                else 0
            )
            next_task = (
                task_row(chosen, index, now=now, spent_seconds=spent) if chosen else None
            )

            recent = tuple(
                task_row(task, index, now=now)
                for task in sorted(
                    open_tasks, key=lambda t: t.updated_at, reverse=True
                )[:RECENT_LIMIT]
            )

            today_seconds = sum(
                s.effective_seconds for s in uow.sessions.list_between(today.start, today.end)
            )
            week_seconds = sum(
                s.effective_seconds for s in uow.sessions.list_between(week.start, week.end)
            )

            unstudied = 0
            for material in uow.materials.list_all():
                for section in uow.sections.list_by_material(
                    material.id, include_archived=False
                ):
                    if not section.is_studied:
                        unstudied += 1

            exams = uow.exams.list_all(scheduled_from=now, pending_only=True)
            soonest = min(exams, key=lambda e: e.scheduled_at or now) if exams else None
            next_exam = exam_row(soonest, index) if soonest else None
            days_to_exam = (
                (periods.to_local_date(soonest.scheduled_at) - periods.to_local_date(now)).days
                if soonest and soonest.scheduled_at
                else None
            )

            streak = _streak(uow, now)

        return HomeOverview(
            onboarding_step=step,
            has_categories=has_categories,
            has_material=material_count > 0,
            has_tasks=any_task,
            next_task=next_task,
            in_progress=bool(chosen and chosen.status is TaskStatus.IN_PROGRESS),
            recent_tasks=recent,
            today_seconds=today_seconds,
            week_seconds=week_seconds,
            streak_days=streak,
            open_tasks=len(open_tasks),
            overdue_tasks=sum(1 for t in open_tasks if t.due_at and t.due_at < now),
            material_count=material_count,
            unstudied_sections=unstudied,
            next_exam=next_exam,
            days_to_exam=days_to_exam,
        )


def _pick_next(open_tasks: list[Task], now) -> Task | None:  # noqa: ANN001
    if not open_tasks:
        return None

    in_progress = [t for t in open_tasks if t.status is TaskStatus.IN_PROGRESS]
    if in_progress:
        return max(in_progress, key=lambda t: t.updated_at)

    with_due = [t for t in open_tasks if t.due_at is not None]
    if with_due:
        return min(with_due, key=lambda t: t.due_at)  # type: ignore[arg-type,return-value]

    return min(open_tasks, key=lambda t: t.created_at)


def _streak(uow: UnitOfWork, now) -> int:  # noqa: ANN001
    from datetime import timedelta

    window = periods.last_days(now, 400)
    sessions = uow.sessions.list_between(window.start, window.end)
    days = {periods.to_local_date(s.started_at) for s in sessions if s.effective_seconds > 0}
    if not days:
        return 0
    today = periods.to_local_date(now)
    cursor = today if today in days else today - timedelta(days=1)
    if cursor not in days:
        return 0
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak
