"""Calendario: tareas con fecha y exámenes, agrupados por día local."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from stou.application import periods
from stou.application.dto import CalendarEntry
from stou.application.mapping import CategoryIndex, exam_row, task_row
from stou.application.ports.unit_of_work import UnitOfWork
from stou.shared.clock import Clock
from stou.shared.ids import EntityId


class GetCalendarMonth:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(
        self, *, year: int, month: int, category_id: EntityId | None = None
    ) -> dict[date, list[CalendarEntry]]:
        now = self._clock.now()
        window = periods.month_bounds(year, month)

        with self._uow as uow:
            index = CategoryIndex(uow.categories.list_all())
            category_ids = index.with_descendants(category_id) if category_id else None

            entries: dict[date, list[CalendarEntry]] = defaultdict(list)

            for task in uow.tasks.list_all(
                category_ids=category_ids, due_from=window.start, due_to=window.end
            ):
                if task.due_at is None:
                    continue
                day = periods.to_local_date(task.due_at)
                entries[day].append(
                    CalendarEntry(day=day, task=task_row(task, index, now=now))
                )

            for exam in uow.exams.list_all(
                category_ids=category_ids,
                scheduled_from=window.start,
                scheduled_to=window.end,
            ):
                if exam.scheduled_at is None:
                    continue
                day = periods.to_local_date(exam.scheduled_at)
                entries[day].append(CalendarEntry(day=day, exam=exam_row(exam, index)))

        return dict(entries)
