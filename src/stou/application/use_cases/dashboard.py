"""Dashboard: qué se hizo y qué viene.

Solo agrega sesiones registradas. Nunca estima tiempo que no se midió.
"""

from __future__ import annotations

from stou.application import metrics, periods
from stou.application.dto import DashboardData
from stou.application.mapping import CategoryIndex, exam_row, task_row
from stou.application.periods import Period
from stou.application.ports.unit_of_work import UnitOfWork
from stou.domain.values import TaskStatus
from stou.shared.clock import Clock


class GetDashboard:
    """El período se resuelve aquí, con el reloj inyectado.

    La vista pide «esta semana» por nombre y no calcula fechas: si lo hiciera con el
    reloj del sistema, la interfaz y las métricas podrían discrepar.
    """

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def period_for(self, key: str) -> Period:
        now = self._clock.now()
        builders = {
            "today": periods.today,
            "week": periods.current_week,
            "month": periods.current_month,
            "last30": lambda moment: periods.last_days(moment, 30),
        }
        return builders.get(key, periods.current_week)(now)

    def execute(
        self, *, period: Period | None = None, period_key: str | None = None
    ) -> DashboardData:
        now = self._clock.now()
        window = period or (
            self.period_for(period_key) if period_key else periods.current_week(now)
        )

        with self._uow as uow:
            index = CategoryIndex(uow.categories.list_all())
            sessions = uow.sessions.list_between(window.start, window.end)

            total = metrics.total_seconds(sessions)
            by_category = metrics.seconds_by_category(sessions, index)
            by_day = metrics.seconds_by_day(sessions, window)

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

            progress = metrics.category_progress(uow, index)
            streak = metrics.streak_days(uow, now)

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
