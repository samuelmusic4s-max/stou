"""Tarea de estudio y el material que lleva asignado."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from stou.domain.entities.base import Entity
from stou.domain.events import (
    TaskCompleted,
    TaskCreated,
    TaskMaterialAssigned,
    TaskMaterialUnassigned,
    TaskScheduled,
    TaskStatusChanged,
    TaskUpdated,
)
from stou.domain.values import Priority, TaskStatus
from stou.shared.ids import EntityId, new_id


@dataclass(kw_only=True)
class TaskItem:
    """Material o sección asignada a una tarea, en un orden de estudio."""

    id: EntityId
    task_id: EntityId
    material_id: EntityId
    section_id: EntityId | None = None
    position: int = 0

    @classmethod
    def create(
        cls,
        *,
        task_id: EntityId,
        material_id: EntityId,
        section_id: EntityId | None = None,
        position: int = 0,
    ) -> TaskItem:
        return cls(
            id=new_id(),
            task_id=task_id,
            material_id=material_id,
            section_id=section_id,
            position=position,
        )


@dataclass(kw_only=True)
class Task(Entity):
    title: str
    description: str = ""
    category_id: EntityId | None = None
    parent_id: EntityId | None = None
    status: TaskStatus = TaskStatus.PENDING
    priority: Priority = Priority.NORMAL
    start_at: datetime | None = None
    due_at: datetime | None = None
    estimated_minutes: int | None = None
    completed_at: datetime | None = None
    position: int = 0
    items: list[TaskItem] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        title: str,
        now: datetime,
        description: str = "",
        category_id: EntityId | None = None,
        parent_id: EntityId | None = None,
        priority: Priority = Priority.NORMAL,
        start_at: datetime | None = None,
        due_at: datetime | None = None,
        estimated_minutes: int | None = None,
    ) -> Task:
        clean = title.strip()
        if not clean:
            raise ValueError("La tarea necesita un título")
        if start_at and due_at and due_at < start_at:
            raise ValueError("La fecha límite no puede ser anterior al inicio")
        task = cls(
            id=new_id(),
            created_at=now,
            updated_at=now,
            title=clean,
            description=description,
            category_id=category_id,
            parent_id=parent_id,
            priority=priority,
            start_at=start_at,
            due_at=due_at,
            estimated_minutes=estimated_minutes,
        )
        task.record(TaskCreated(task_id=task.id, category_id=category_id, title=clean), at=now)
        return task

    # --- estado ---------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return self.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)

    def begin(self, now: datetime) -> None:
        if self.status is TaskStatus.PENDING:
            self._set_status(TaskStatus.IN_PROGRESS, now)

    def complete(self, now: datetime) -> None:
        if self.status is TaskStatus.DONE:
            return
        self.completed_at = now
        self._set_status(TaskStatus.DONE, now)
        self.record(TaskCompleted(task_id=self.id), at=now)

    def reopen(self, now: datetime) -> None:
        self.completed_at = None
        self._set_status(TaskStatus.PENDING, now)

    def cancel(self, now: datetime) -> None:
        self._set_status(TaskStatus.CANCELLED, now)

    def _set_status(self, status: TaskStatus, now: datetime) -> None:
        if self.status is status:
            return
        self.status = status
        self.touch(now)
        self.record(TaskStatusChanged(task_id=self.id, status=str(status)), at=now)

    # --- edición --------------------------------------------------------------

    def edit(
        self,
        now: datetime,
        *,
        title: str | None = None,
        description: str | None = None,
        category_id: EntityId | None = None,
        priority: Priority | None = None,
        estimated_minutes: int | None = None,
    ) -> None:
        if title is not None:
            clean = title.strip()
            if not clean:
                raise ValueError("La tarea necesita un título")
            self.title = clean
        if description is not None:
            self.description = description
        if category_id is not None:
            self.category_id = category_id
        if priority is not None:
            self.priority = priority
        if estimated_minutes is not None:
            self.estimated_minutes = estimated_minutes
        self.touch(now)
        self.record(TaskUpdated(task_id=self.id), at=now)

    def reschedule(
        self, now: datetime, *, start_at: datetime | None, due_at: datetime | None
    ) -> None:
        if start_at and due_at and due_at < start_at:
            raise ValueError("La fecha límite no puede ser anterior al inicio")
        self.start_at = start_at
        self.due_at = due_at
        self.touch(now)
        self.record(TaskScheduled(task_id=self.id, due_at=due_at), at=now)

    # --- material asignado ----------------------------------------------------

    def assign(
        self,
        *,
        material_id: EntityId,
        now: datetime,
        section_id: EntityId | None = None,
    ) -> TaskItem:
        already = any(
            item.material_id == material_id and item.section_id == section_id
            for item in self.items
        )
        if already:
            raise ValueError("Ese material ya está asignado a la tarea")
        item = TaskItem.create(
            task_id=self.id,
            material_id=material_id,
            section_id=section_id,
            position=len(self.items),
        )
        self.items.append(item)
        self.touch(now)
        self.record(
            TaskMaterialAssigned(
                task_id=self.id, material_id=material_id, section_id=section_id
            ),
            at=now,
        )
        return item

    def unassign(self, item_id: EntityId, now: datetime) -> None:
        remaining = [item for item in self.items if item.id != item_id]
        if len(remaining) == len(self.items):
            return
        for position, item in enumerate(remaining):
            item.position = position
        self.items = remaining
        self.touch(now)
        self.record(TaskMaterialUnassigned(task_id=self.id, item_id=item_id), at=now)

    def reorder(self, item_ids: list[EntityId], now: datetime) -> None:
        by_id = {item.id: item for item in self.items}
        if set(item_ids) != set(by_id):
            raise ValueError("El nuevo orden debe incluir exactamente el material asignado")
        self.items = [by_id[item_id] for item_id in item_ids]
        for position, item in enumerate(self.items):
            item.position = position
        self.touch(now)
        self.record(TaskUpdated(task_id=self.id), at=now)
