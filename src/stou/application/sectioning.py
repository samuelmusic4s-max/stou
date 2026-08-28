"""Conversión de la estructura interna de un material en secciones estudiables.

Lógica pura: recibe el índice ya leído por infrastructure y decide los intervalos.
"""

from __future__ import annotations

from datetime import datetime

from stou.application.ports.content import OutlineEntry
from stou.domain.entities.material import Material
from stou.domain.entities.section import Section
from stou.domain.values import Locator, LocatorUnit, MaterialKind

_UNIT_BY_KIND = {
    MaterialKind.PDF: LocatorUnit.PAGE,
    MaterialKind.EPUB: LocatorUnit.LOCATION,
    MaterialKind.VIDEO: LocatorUnit.SECOND,
    MaterialKind.AUDIO: LocatorUnit.SECOND,
    MaterialKind.YOUTUBE: LocatorUnit.SECOND,
}


def unit_for(kind: MaterialKind) -> LocatorUnit:
    return _UNIT_BY_KIND.get(kind, LocatorUnit.NONE)


def material_extent(material: Material) -> float | None:
    """Última posición del material, si se conoce."""
    unit = unit_for(material.kind)
    if unit is LocatorUnit.PAGE:
        return float(material.page_count) if material.page_count else None
    if unit is LocatorUnit.SECOND:
        return material.duration_seconds
    return None


def sections_from_outline(
    material: Material,
    outline: list[OutlineEntry] | tuple[OutlineEntry, ...],
    now: datetime,
) -> list[Section]:
    """Cada entrada del índice se vuelve una sección que termina donde empieza la siguiente."""
    entries = [e for e in outline if e.title.strip()]
    if not entries:
        return []

    unit = unit_for(material.kind)
    extent = material_extent(material)
    ordered = sorted(entries, key=lambda e: e.start)

    sections: list[Section] = []
    for position, entry in enumerate(ordered):
        end = entry.end
        if end is None:
            following = next(
                (o.start for o in ordered[position + 1 :] if o.start > entry.start), None
            )
            if following is not None:
                end = following - 1 if unit is LocatorUnit.PAGE else following
            else:
                end = extent
        if end is not None and end < entry.start:
            end = entry.start
        sections.append(
            Section.create(
                material_id=material.id,
                title=entry.title.strip(),
                locator=Locator(unit=unit, start=entry.start, end=end),
                now=now,
                position=position,
            )
        )
    return sections


def single_section(material: Material, now: datetime) -> Section:
    """Sección que cubre el material completo, para material sin estructura."""
    unit = unit_for(material.kind)
    return Section.create(
        material_id=material.id,
        title=material.title,
        locator=Locator(
            unit=unit,
            start=1.0 if unit is LocatorUnit.PAGE else 0.0,
            end=material_extent(material),
        ),
        now=now,
        position=0,
    )


def split_evenly(
    material: Material, *, count: int, now: datetime, prefix: str = "Parte"
) -> list[Section]:
    """Divide el material en partes iguales cuando no hay índice aprovechable."""
    if count < 1:
        raise ValueError("El número de partes debe ser al menos 1")
    extent = material_extent(material)
    if extent is None:
        raise ValueError("No se conoce la extensión del material para dividirlo")

    unit = unit_for(material.kind)
    start_at = 1.0 if unit is LocatorUnit.PAGE else 0.0
    span = (extent - start_at + 1) if unit is LocatorUnit.PAGE else extent
    step = span / count

    sections: list[Section] = []
    for i in range(count):
        raw_start = start_at + i * step
        raw_end = start_at + (i + 1) * step
        if unit is LocatorUnit.PAGE:
            start = float(int(raw_start))
            end = float(int(raw_end) - 1) if i < count - 1 else extent
            if end < start:
                end = start
        else:
            start = raw_start
            end = raw_end if i < count - 1 else extent
        sections.append(
            Section.create(
                material_id=material.id,
                title=f"{prefix} {i + 1}",
                locator=Locator(unit=unit, start=start, end=end),
                now=now,
                position=i,
            )
        )
    return sections
