"""Dashboard: qué se hizo y qué viene.

Solo agrega sesiones registradas. Nunca estima tiempo que no se midió.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from stou.application import periods
from stou.application.dto import (
    CategoryProgress,
    CategoryTime,
    DashboardData,
    DayTime,
)
from stou.application.mapping import CategoryIndex, exam_row, task_row
from stou.application.periods import Period
from stou.application.ports.unit_of_work import UnitOfWork
from stou.domain.values import MaterialState, TaskStatus
from stou.shared.clock import Clock
from stou.shared.ids import EntityId

STREAK_LOOKBACK_DAYS = 400


class GetDashboard:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self, *, period: Period | None = None) -> DashboardData:
        now = self._clock.now()
        window = period or periods.current_week(now)

        with self._uow as uow:
            index = CategoryIndex(uow.categories.list_all())
            sessions = uow.sessions.list_between(window.start, window.end)

            seconds_by_category: dict[EntityId | None, int] = defaultdict(int)
            seconds_by_day: dict[object, int] = defaultdict(int)
            total = 0
            for session in sessions:
                secs = session.effective_seconds
                if secs <= 0:
                    continue
                total += secs
                seconds_by_category[session.category_id] += secs
                seconds_by_day[periods.to_local_date(session.started_at)] += secs

            by_category = tuple(
                sorted(
                    (
                        CategoryTime(
                            category_id=cid,
                            category_path=index.path(cid),
                            color=index.color(cid),
                            seconds=secs,
                        )
                        for cid, secs in seconds_by_category.items()
                    ),
                    key=lambda c: c.seconds,
                    reverse=True,
                )
            )
            by_day = tuple(
                DayTime(day=day, seconds=seconds_by_day.get(day, 0)) for day in window.days()
            )

            completed = [
                task
                for task in uow.tasks.list_all(statuses=[TaskStatus.DONE])
                if task.completed_at and window.start <= task.completed_at < window.end
            ]
            open_tasks = uow.tasks.list_all(
                statuses=[TaskStatus.PENDING, TaskStatus.IN_PROGRESS]
            )

            overdue = tuple(
                task_row(task, index, now=now)
                for task in sorted(
                    (t for t in open_tasks if t.due_at and t.due_at < now),
                    key=lambda t: t.due_at or now,
                )
            )
            upcoming = tuple(
                task_row(task, index, now=now)
                for task in sorted(
                    (t for t in open_tasks if t.due_at and t.due_at >= now),
                    key=lambda t: t.due_at or now,
                )[:10]
            )

            week = periods.current_week(now)
            week_plan = tuple(
                task_row(task, index, now=now)
                for task in sorted(
                    (
                        t
                        for t in open_tasks
                        if t.due_at and week.start <= t.due_at < week.end
                    ),
                    key=lambda t: t.due_at or now,
                )
            )

            exams = uow.exams.list_all(scheduled_from=now, pending_only=True)
            upcoming_exams = tuple(
                exam_row(exam, index)
                for exam in sorted(exams, key=lambda e: e.scheduled_at or now)[:10]
            )

            progress = _category_progress(uow, index)
            streak = _streak_days(uow, now)

        return DashboardData(
            period_label=window.label,
            total_seconds=total,
            by_category=by_category,
            by_day=by_day,
            completed_tasks=len(completed),
            open_tasks=len(open_tasks),
            overdue=overdue,
            upcoming_tasks=upcoming,
            upcoming_exams=upcoming_exams,
            week_plan=week_plan,
            streak_days=streak,
            progress=progress,
        )


def _category_progress(uow: UnitOfWork, index: CategoryIndex) -> tuple[CategoryProgress, ...]:
    totals: dict[EntityId, list[int]] = defaultdict(lambda: [0, 0, 0])
    for material in uow.materials.list_all(include_archived=True):
        if material.category_id is None:
            continue
        sections = uow.sections.list_by_material(material.id)
        bucket = totals[material.category_id]
        for section in sections:
            bucket[0] += 1
            if section.is_studied:
                bucket[1] += 1
            if section.state is MaterialState.ARCHIVED:
                bucket[2] += 1
    return tuple(
        sorted(
            (
                CategoryProgress(
                    category_id=cid,
                    category_path=index.path(cid),
                    total_sections=vals[0],
                    studied_sections=vals[1],
                    archived_sections=vals[2],
                )
                for cid, vals in totals.items()
            ),
            key=lambda p: p.category_path,
        )
    )


def _streak_days(uow: UnitOfWork, now) -> int:
    lookback = periods.last_days(now, STREAK_LOOKBACK_DAYS)
    sessions = uow.sessions.list_between(lookback.start, lookback.end)
    active_days = {
        periods.to_local_date(s.started_at) for s in sessions if s.effective_seconds > 0
    }
    if not active_days:
        return 0
    today_local = periods.to_local_date(now)
    cursor = today_local if today_local in active_days else today_local - timedelta(days=1)
    if cursor not in active_days:
        return 0
    streak = 0
    while cursor in active_days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak
