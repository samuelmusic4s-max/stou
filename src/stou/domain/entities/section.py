"""Sección: fragmento estudiable de un material.

Es la unidad real de trabajo del sistema: se asigna a tareas, se marca como
estudiada y es lo que un examen archiva.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from stou.domain.entities.base import Entity
from stou.domain.events import SectionArchived, SectionStudied
from stou.domain.values import Locator, MaterialState
from stou.shared.ids import EntityId, new_id


@dataclass(kw_only=True)
class Section(Entity):
    material_id: EntityId
    title: str
    locator: Locator
    parent_id: EntityId | None = None
    position: int = 0
    state: MaterialState = MaterialState.ACTIVE
    studied_at: datetime | None = None
    notes: str | None = None

    @classmethod
    def create(
        cls,
        *,
        material_id: EntityId,
        title: str,
        locator: Locator,
        now: datetime,
        parent_id: EntityId | None = None,
        position: int = 0,
    ) -> Section:
        clean = title.strip()
        if not clean:
            raise ValueError("La sección necesita un título")
        return cls(
            id=new_id(),
            created_at=now,
            updated_at=now,
            material_id=material_id,
            title=clean,
            locator=locator,
            parent_id=parent_id,
            position=position,
        )

    @property
    def is_active(self) -> bool:
        return self.state is MaterialState.ACTIVE

    @property
    def is_studied(self) -> bool:
        return self.studied_at is not None

    def mark_studied(self, now: datetime) -> None:
        if self.studied_at is not None:
            return
        self.studied_at = now
        self.touch(now)
        self.record(SectionStudied(section_id=self.id, material_id=self.material_id), at=now)

    def unmark_studied(self, now: datetime) -> None:
        self.studied_at = None
        self.touch(now)

    def rename(self, title: str, now: datetime) -> None:
        clean = title.strip()
        if not clean:
            raise ValueError("La sección necesita un título")
        self.title = clean
        self.touch(now)

    def retarget(self, locator: Locator, now: datetime) -> None:
        self.locator = locator
        self.touch(now)

    def archive(self, now: datetime) -> None:
        if self.state is MaterialState.ARCHIVED:
            return
        self.state = MaterialState.ARCHIVED
        self.touch(now)
        self.record(SectionArchived(section_id=self.id, material_id=self.material_id), at=now)

    def reactivate(self, now: datetime) -> None:
        self.state = MaterialState.ACTIVE
        self.touch(now)
