"""Casos de uso de tareas."""

from __future__ import annotations

from contextlib import suppress
from datetime import datetime

from stou.application.dto import SectionRow, TaskDetail, TaskItemRow, TaskRow
from stou.application.mapping import CategoryIndex, section_row, task_item_row, task_row
from stou.application.ports.event_bus import EventBus
from stou.application.ports.unit_of_work import UnitOfWork
from stou.application.use_cases._shared import commit_and_publish, require
from stou.domain.entities.task import Task
from stou.domain.events import TaskDeleted
from stou.domain.values import Priority, TaskStatus
from stou.shared.clock import Clock
from stou.shared.ids import EntityId


class CreateTask:
    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(
        self,
        *,
        title: str,
        description: str = "",
        category_id: EntityId | None = None,
        parent_id: EntityId | None = None,
        priority: Priority = Priority.NORMAL,
        start_at: datetime | None = None,
        due_at: datetime | None = None,
        estimated_minutes: int | None = None,
        section_ids: list[EntityId] | None = None,
    ) -> EntityId:
        now = self._clock.now()
        with self._uow as uow:
            if category_id is not None:
                require(uow.categories.get(category_id), "La categoría no existe")
            task = Task.create(
                title=title,
                now=now,
                description=description,
                category_id=category_id,
                parent_id=parent_id,
                priority=priority,
                start_at=start_at,
                due_at=due_at,
                estimated_minutes=estimated_minutes,
            )
            for section_id in section_ids or []:
                section = uow.sections.get(section_id)
                require(section, "La sección asignada no existe")
                assert section is not None
                task.assign(material_id=section.material_id, section_id=section.id, now=now)
            uow.tasks.add(task)
            commit_and_publish(uow, self._bus, task)
            return task.id


class UpdateTask:
    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(
        self,
        *,
        task_id: EntityId,
        title: str | None = None,
        description: str | None = None,
        category_id: EntityId | None = None,
        priority: Priority | None = None,
        estimated_minutes: int | None = None,
    ) -> None:
        now = self._clock.now()
        with self._uow as uow:
            task = uow.tasks.get(task_id)
            require(task, "La tarea no existe")
            assert task is not None
            task.edit(
                now,
                title=title,
                description=description,
                category_id=category_id,
                priority=priority,
                estimated_minutes=estimated_minutes,
            )
            uow.tasks.update(task)
            commit_and_publish(uow, self._bus, task)


class RescheduleTask:
    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(
        self,
        *,
        task_id: EntityId,
        start_at: datetime | None = None,
        due_at: datetime | None = None,
    ) -> None:
        now = self._clock.now()
        with self._uow as uow:
            task = uow.tasks.get(task_id)
            require(task, "La tarea no existe")
            assert task is not None
            task.reschedule(now, start_at=start_at, due_at=due_at)
            uow.tasks.update(task)
            commit_and_publish(uow, self._bus, task)


class ChangeTaskStatus:
    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(self, *, task_id: EntityId, status: TaskStatus) -> None:
        now = self._clock.now()
        with self._uow as uow:
            task = uow.tasks.get(task_id)
            require(task, "La tarea no existe")
            assert task is not None
            if status is TaskStatus.DONE:
                task.complete(now)
            elif status is TaskStatus.PENDING:
                task.reopen(now)
            elif status is TaskStatus.IN_PROGRESS:
                task.begin(now)
            else:
                task.cancel(now)
            uow.tasks.update(task)
            commit_and_publish(uow, self._bus, task)


class DeleteTask:
    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(self, *, task_id: EntityId) -> None:
        now = self._clock.now()
        with self._uow as uow:
            uow.tasks.delete(task_id)
            uow.commit()
        self._bus.publish(TaskDeleted(task_id=task_id, occurred_at=now))


class ListTasks:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(
        self,
        *,
        category_id: EntityId | None = None,
        include_subcategories: bool = True,
        statuses: list[TaskStatus] | None = None,
        due_from: datetime | None = None,
        due_to: datetime | None = None,
        search: str | None = None,
    ) -> list[TaskRow]:
        now = self._clock.now()
        with self._uow as uow:
            index = CategoryIndex(uow.categories.list_all())
            category_ids = (
                index.with_descendants(category_id)
                if category_id and include_subcategories
                else ([category_id] if category_id else None)
            )
            tasks = uow.tasks.list_all(
                category_ids=category_ids,
                statuses=statuses,
                due_from=due_from,
                due_to=due_to,
                search=search,
            )
            return [_row_with_progress(uow, task, index, now) for task in tasks]


class GetTaskDetail:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self, *, task_id: EntityId) -> TaskDetail:
        now = self._clock.now()
        with self._uow as uow:
            task = uow.tasks.get(task_id)
            require(task, "La tarea no existe")
            assert task is not None
            index = CategoryIndex(uow.categories.list_all())
            items: list[TaskItemRow] = []
            for item in sorted(task.items, key=lambda i: i.position):
                material = uow.materials.get(item.material_id)
                if material is None:
                    continue
                section = uow.sections.get(item.section_id) if item.section_id else None
                items.append(task_item_row(item.id, material, section, item.position))
            return TaskDetail(
                task=_row_with_progress(uow, task, index, now),
                description=task.description,
                items=tuple(items),
            )


class AssignMaterialToTask:
    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(
        self,
        *,
        task_id: EntityId,
        material_id: EntityId | None = None,
        section_ids: list[EntityId] | None = None,
    ) -> None:
        now = self._clock.now()
        with self._uow as uow:
            task = uow.tasks.get(task_id)
            require(task, "La tarea no existe")
            assert task is not None

            for section_id in section_ids or []:
                section = uow.sections.get(section_id)
                require(section, "La sección no existe")
                assert section is not None
                try:
                    task.assign(material_id=section.material_id, section_id=section.id, now=now)
                except ValueError:
                    continue

            if material_id is not None:
                require(uow.materials.get(material_id), "El material no existe")
                with suppress(ValueError):  # ya estaba asignado
                    task.assign(material_id=material_id, section_id=None, now=now)

            uow.tasks.update(task)
            commit_and_publish(uow, self._bus, task)


class UnassignTaskItem:
    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(self, *, task_id: EntityId, item_id: EntityId) -> None:
        now = self._clock.now()
        with self._uow as uow:
            task = uow.tasks.get(task_id)
            require(task, "La tarea no existe")
            assert task is not None
            task.unassign(item_id, now)
            uow.tasks.update(task)
            commit_and_publish(uow, self._bus, task)


class ReorderTaskItems:
    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(self, *, task_id: EntityId, item_ids: list[EntityId]) -> None:
        now = self._clock.now()
        with self._uow as uow:
            task = uow.tasks.get(task_id)
            require(task, "La tarea no existe")
            assert task is not None
            task.reorder(item_ids, now)
            uow.tasks.update(task)
            commit_and_publish(uow, self._bus, task)


class SuggestSections:
    """Secciones activas y no estudiadas de una categoría, para asignar a una tarea."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(
        self, *, category_id: EntityId | None, limit: int = 200
    ) -> list[SectionRow]:
        with self._uow as uow:
            index = CategoryIndex(uow.categories.list_all())
            category_ids = index.with_descendants(category_id) if category_id else []
            if not category_ids:
                materials = uow.materials.list_all(include_archived=False)
            else:
                materials = uow.materials.list_all(
                    category_ids=category_ids, include_archived=False
                )
            rows: list[SectionRow] = []
            for material in materials:
                for section in uow.sections.list_by_material(
                    material.id, include_archived=False
                ):
                    if section.is_studied:
                        continue
                    rows.append(section_row(section, material))
                    if len(rows) >= limit:
                        return rows
            return rows


def _row_with_progress(
    uow: UnitOfWork, task: Task, index: CategoryIndex, now: datetime
) -> TaskRow:
    spent = sum(s.effective_seconds for s in uow.sessions.list_by_task(task.id))
    studied = 0
    for item in task.items:
        if item.section_id:
            section = uow.sections.get(item.section_id)
            if section and section.is_studied:
                studied += 1
    return task_row(task, index, now=now, spent_seconds=spent, studied_items=studied)
