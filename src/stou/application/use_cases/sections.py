"""Casos de uso de secciones: la unidad estudiable del material."""

from __future__ import annotations

from stou.application.dto import SectionRow
from stou.application.mapping import section_row
from stou.application.ports.event_bus import EventBus
from stou.application.ports.unit_of_work import UnitOfWork
from stou.application.sectioning import unit_for
from stou.application.use_cases._shared import commit_and_publish, require
from stou.domain.entities.section import Section
from stou.domain.events import SectionsCreated
from stou.domain.values import Locator
from stou.shared.clock import Clock
from stou.shared.ids import EntityId


class ListSections:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(
        self, *, material_id: EntityId, include_archived: bool = True
    ) -> list[SectionRow]:
        with self._uow as uow:
            material = uow.materials.get(material_id)
            require(material, "El material no existe")
            assert material is not None
            sections = uow.sections.list_by_material(
                material_id, include_archived=include_archived
            )
            by_id = {s.id: s for s in sections}
            return [
                section_row(section, material, level=_level_of(section, by_id))
                for section in sections
            ]


class CreateSection:
    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(
        self,
        *,
        material_id: EntityId,
        title: str,
        start: float,
        end: float | None = None,
        parent_id: EntityId | None = None,
    ) -> EntityId:
        now = self._clock.now()
        with self._uow as uow:
            material = uow.materials.get(material_id)
            require(material, "El material no existe")
            assert material is not None
            siblings = uow.sections.list_by_material(material_id)
            section = Section.create(
                material_id=material_id,
                title=title,
                locator=Locator(unit=unit_for(material.kind), start=start, end=end),
                now=now,
                parent_id=parent_id,
                position=len(siblings),
            )
            uow.sections.add(section)
            material.record(
                SectionsCreated(material_id=material_id, section_ids=(section.id,)), at=now
            )
            commit_and_publish(uow, self._bus, material)
            return section.id


class UpdateSection:
    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(
        self,
        *,
        section_id: EntityId,
        title: str | None = None,
        start: float | None = None,
        end: float | None = None,
    ) -> None:
        now = self._clock.now()
        with self._uow as uow:
            section = uow.sections.get(section_id)
            require(section, "La sección no existe")
            assert section is not None
            if title is not None:
                section.rename(title, now)
            if start is not None or end is not None:
                section.retarget(
                    Locator(
                        unit=section.locator.unit,
                        start=start if start is not None else section.locator.start,
                        end=end if end is not None else section.locator.end,
                    ),
                    now,
                )
            uow.sections.update(section)
            commit_and_publish(uow, self._bus, section)


class DeleteSection:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self, *, section_id: EntityId) -> None:
        with self._uow as uow:
            uow.sections.delete(section_id)
            uow.commit()


class MarkSectionStudied:
    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(self, *, section_id: EntityId, studied: bool = True) -> None:
        now = self._clock.now()
        with self._uow as uow:
            section = uow.sections.get(section_id)
            require(section, "La sección no existe")
            assert section is not None
            if studied:
                section.mark_studied(now)
            else:
                section.unmark_studied(now)
            uow.sections.update(section)
            commit_and_publish(uow, self._bus, section)


def _level_of(section: Section, by_id: dict[EntityId, Section]) -> int:
    level = 0
    current = section
    guard = 0
    while current.parent_id and guard < 16:
        parent = by_id.get(current.parent_id)
        if parent is None:
            break
        level += 1
        current = parent
        guard += 1
    return level
