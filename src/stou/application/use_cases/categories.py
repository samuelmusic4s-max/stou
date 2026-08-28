"""Casos de uso de categorías."""

from __future__ import annotations

from stou.application.dto import CategoryNode
from stou.application.mapping import CategoryIndex
from stou.application.ports.event_bus import EventBus
from stou.application.ports.unit_of_work import UnitOfWork
from stou.application.use_cases._shared import NotFound, commit_and_publish, require
from stou.domain.entities.category import Category
from stou.domain.events import CategoryDeleted
from stou.shared.clock import Clock
from stou.shared.ids import EntityId


class GetCategoryTree:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(self) -> tuple[CategoryNode, ...]:
        with self._uow as uow:
            return CategoryIndex(uow.categories.list_all()).tree()


class CreateCategory:
    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(
        self, *, name: str, parent_id: EntityId | None = None, color: str | None = None
    ) -> EntityId:
        now = self._clock.now()
        with self._uow as uow:
            if parent_id is not None:
                require(uow.categories.get(parent_id), "La categoría madre no existe")
            siblings = [c for c in uow.categories.list_all() if c.parent_id == parent_id]
            category = Category.create(
                name=name,
                now=now,
                parent_id=parent_id,
                position=len(siblings),
                **({"color": color} if color else {}),
            )
            uow.categories.add(category)
            commit_and_publish(uow, self._bus, category)
            return category.id


class RenameCategory:
    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(self, *, category_id: EntityId, name: str) -> None:
        now = self._clock.now()
        with self._uow as uow:
            category = uow.categories.get(category_id)
            require(category, "La categoría no existe")
            assert category is not None
            category.rename(name, now)
            uow.categories.update(category)
            commit_and_publish(uow, self._bus, category)


class MoveCategory:
    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(self, *, category_id: EntityId, parent_id: EntityId | None) -> None:
        now = self._clock.now()
        with self._uow as uow:
            category = uow.categories.get(category_id)
            require(category, "La categoría no existe")
            assert category is not None
            if parent_id is not None:
                require(uow.categories.get(parent_id), "La categoría destino no existe")
                index = CategoryIndex(uow.categories.list_all())
                if index.is_descendant(parent_id, category_id):
                    raise ValueError("No se puede mover una categoría dentro de sí misma")
            category.move_to(parent_id, now)
            uow.categories.update(category)
            commit_and_publish(uow, self._bus, category)


class DeleteCategory:
    """Borra una categoría vacía. El material y las tareas se conservan sin categoría."""

    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(self, *, category_id: EntityId) -> None:
        now = self._clock.now()
        with self._uow as uow:
            category = uow.categories.get(category_id)
            require(category, "La categoría no existe")
            if uow.categories.has_children(category_id):
                raise ValueError("La categoría tiene subcategorías: muévelas o bórralas primero")
            uow.categories.delete(category_id)
            uow.commit()
            self._bus.publish(CategoryDeleted(category_id=category_id, occurred_at=now))


__all__ = [
    "CreateCategory",
    "DeleteCategory",
    "GetCategoryTree",
    "MoveCategory",
    "NotFound",
    "RenameCategory",
]
