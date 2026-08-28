"""Categoría: nodo de la jerarquía que clasifica material y tareas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from stou.domain.entities.base import Entity
from stou.domain.events import CategoryCreated, CategoryMoved, CategoryRenamed
from stou.shared.ids import EntityId, new_id

DEFAULT_COLOR = "#5B8DEF"


@dataclass(kw_only=True)
class Category(Entity):
    name: str
    parent_id: EntityId | None = None
    color: str = DEFAULT_COLOR
    position: int = 0

    @classmethod
    def create(
        cls,
        *,
        name: str,
        now: datetime,
        parent_id: EntityId | None = None,
        color: str = DEFAULT_COLOR,
        position: int = 0,
    ) -> Category:
        clean = _validate_name(name)
        category = cls(
            id=new_id(),
            created_at=now,
            updated_at=now,
            name=clean,
            parent_id=parent_id,
            color=color,
            position=position,
        )
        category.record(
            CategoryCreated(category_id=category.id, parent_id=parent_id, name=clean), at=now
        )
        return category

    def rename(self, name: str, now: datetime) -> None:
        clean = _validate_name(name)
        if clean == self.name:
            return
        self.name = clean
        self.touch(now)
        self.record(CategoryRenamed(category_id=self.id, name=clean), at=now)

    def move_to(self, parent_id: EntityId | None, now: datetime) -> None:
        if parent_id == self.id:
            raise ValueError("Una categoría no puede ser su propia madre")
        if parent_id == self.parent_id:
            return
        self.parent_id = parent_id
        self.touch(now)
        self.record(CategoryMoved(category_id=self.id, parent_id=parent_id), at=now)


def _validate_name(name: str) -> str:
    clean = name.strip()
    if not clean:
        raise ValueError("La categoría necesita un nombre")
    if len(clean) > 120:
        raise ValueError("El nombre de la categoría es demasiado largo")
    return clean
