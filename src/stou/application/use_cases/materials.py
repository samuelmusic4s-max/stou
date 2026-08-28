"""Casos de uso de la biblioteca de material."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from stou.application.dto import MaterialRow
from stou.application.mapping import CategoryIndex, material_row
from stou.application.ports.content import EpubUnpacker, FileStorage, MaterialInspector
from stou.application.ports.event_bus import EventBus
from stou.application.ports.unit_of_work import UnitOfWork
from stou.application.sectioning import sections_from_outline, single_section, split_evenly
from stou.application.use_cases._shared import commit_and_publish, require
from stou.domain.entities.material import Material
from stou.domain.events import MaterialDeleted, SectionsCreated
from stou.domain.values import MaterialKind
from stou.shared.clock import Clock
from stou.shared.ids import EntityId

YOUTUBE_HOSTS = ("youtube.com", "youtu.be", "www.youtube.com", "m.youtube.com")


@dataclass(frozen=True, slots=True)
class ImportOutcome:
    imported: tuple[EntityId, ...]
    duplicates: tuple[str, ...]
    failed: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class MaterialSource:
    """Cómo abrir un material: archivo local, URL o cuerpo de nota."""

    material_id: EntityId
    kind: MaterialKind
    title: str
    path: Path | None
    url: str | None
    body: str | None
    reading_position: float


class ImportMaterialFiles:
    """Copia archivos a la biblioteca y crea sus secciones a partir del índice."""

    def __init__(
        self,
        uow: UnitOfWork,
        bus: EventBus,
        clock: Clock,
        storage: FileStorage,
        inspector: MaterialInspector,
    ) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock
        self._storage = storage
        self._inspector = inspector

    def execute(
        self,
        *,
        paths: list[Path],
        category_id: EntityId | None = None,
        auto_section: bool = True,
    ) -> ImportOutcome:
        imported: list[EntityId] = []
        duplicates: list[str] = []
        failed: list[tuple[str, str]] = []

        for path in paths:
            try:
                outcome = self._import_one(path, category_id, auto_section)
            except Exception as exc:  # un archivo malo no aborta el lote
                failed.append((path.name, str(exc)))
                continue
            if outcome is None:
                duplicates.append(path.name)
            else:
                imported.append(outcome)

        return ImportOutcome(
            imported=tuple(imported), duplicates=tuple(duplicates), failed=tuple(failed)
        )

    def _import_one(
        self, path: Path, category_id: EntityId | None, auto_section: bool
    ) -> EntityId | None:
        now = self._clock.now()
        kind = self._inspector.detect_kind(path)
        blob = self._storage.store(path)
        inspected = self._inspector.inspect(self._storage.path_for(blob.hash, blob.ext), kind)

        with self._uow as uow:
            existing = uow.materials.find_by_hash(blob.hash)
            if existing is not None:
                return None

            material = Material.create(
                kind=kind,
                # El nombre del archivo que el usuario reconoce manda; el título
                # embebido solo se usa si existe.
                title=inspected.title or path.stem,
                now=now,
                category_id=category_id,
                blob_hash=blob.hash,
                blob_ext=blob.ext,
                size_bytes=blob.size_bytes,
                source=str(path),
                page_count=inspected.page_count,
                duration_seconds=inspected.duration_seconds,
            )
            uow.materials.add(material)

            if auto_section:
                sections = sections_from_outline(material, inspected.outline, now)
                if not sections:
                    sections = [single_section(material, now)]
                uow.sections.add_many(sections)
                material.record(
                    SectionsCreated(
                        material_id=material.id,
                        section_ids=tuple(s.id for s in sections),
                    ),
                    at=now,
                )

            commit_and_publish(uow, self._bus, material)
            return material.id


class AddLinkMaterial:
    """Registra una URL: video de YouTube o página web."""

    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(
        self,
        *,
        url: str,
        title: str | None = None,
        category_id: EntityId | None = None,
        duration_seconds: float | None = None,
    ) -> EntityId:
        clean = url.strip()
        if not clean.lower().startswith(("http://", "https://")):
            raise ValueError("La dirección debe empezar por http:// o https://")
        kind = MaterialKind.YOUTUBE if _is_youtube(clean) else MaterialKind.WEB

        now = self._clock.now()
        with self._uow as uow:
            material = Material.create(
                kind=kind,
                title=title or clean,
                now=now,
                category_id=category_id,
                url=clean,
                source=clean,
                duration_seconds=duration_seconds,
            )
            uow.materials.add(material)
            commit_and_publish(uow, self._bus, material)
            return material.id


class CreateNote:
    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(
        self, *, title: str, body: str = "", category_id: EntityId | None = None
    ) -> EntityId:
        now = self._clock.now()
        with self._uow as uow:
            material = Material.create(
                kind=MaterialKind.NOTE,
                title=title,
                now=now,
                category_id=category_id,
                body=body,
            )
            uow.materials.add(material)
            commit_and_publish(uow, self._bus, material)
            return material.id


class UpdateMaterial:
    """Renombra, recategoriza o edita el cuerpo de una nota."""

    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(
        self,
        *,
        material_id: EntityId,
        title: str | None = None,
        category_id: EntityId | None = None,
        body: str | None = None,
    ) -> None:
        now = self._clock.now()
        with self._uow as uow:
            material = uow.materials.get(material_id)
            require(material, "El material no existe")
            assert material is not None
            if title is not None:
                material.rename(title, now)
            if category_id is not None:
                material.move_to_category(category_id, now)
            if body is not None:
                material.edit_body(body, now)
            uow.materials.update(material)
            commit_and_publish(uow, self._bus, material)


class SaveReadingPosition:
    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(self, *, material_id: EntityId, position: float) -> None:
        now = self._clock.now()
        with self._uow as uow:
            material = uow.materials.get(material_id)
            if material is None:
                return
            material.save_reading_position(position, now)
            uow.materials.update(material)
            commit_and_publish(uow, self._bus, material)


class SetMaterialState:
    """Archiva o reactiva un material y sus secciones."""

    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(self, *, material_id: EntityId, archived: bool) -> None:
        now = self._clock.now()
        with self._uow as uow:
            material = uow.materials.get(material_id)
            require(material, "El material no existe")
            assert material is not None
            if archived:
                material.archive(now)
            else:
                material.reactivate(now)
            uow.materials.update(material)

            sections = uow.sections.list_by_material(material_id)
            for section in sections:
                if archived:
                    section.archive(now)
                else:
                    section.reactivate(now)
                uow.sections.update(section)
            commit_and_publish(uow, self._bus, material, *sections)


class DeleteMaterial:
    def __init__(
        self, uow: UnitOfWork, bus: EventBus, clock: Clock, storage: FileStorage
    ) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock
        self._storage = storage

    def execute(self, *, material_id: EntityId, delete_file: bool = True) -> None:
        now = self._clock.now()
        with self._uow as uow:
            material = uow.materials.get(material_id)
            require(material, "El material no existe")
            assert material is not None
            blob = (material.blob_hash, material.blob_ext)
            uow.materials.delete(material_id)
            uow.commit()

        if delete_file and blob[0]:
            self._storage.delete(blob[0], blob[1])
        self._bus.publish(MaterialDeleted(material_id=material_id, occurred_at=now))


class ListMaterials:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(
        self,
        *,
        category_id: EntityId | None = None,
        include_subcategories: bool = True,
        kinds: list[MaterialKind] | None = None,
        include_archived: bool = False,
        search: str | None = None,
    ) -> list[MaterialRow]:
        with self._uow as uow:
            index = CategoryIndex(uow.categories.list_all())
            category_ids = (
                index.with_descendants(category_id)
                if category_id and include_subcategories
                else ([category_id] if category_id else None)
            )
            materials = uow.materials.list_all(
                category_ids=category_ids,
                kinds=kinds,
                include_archived=include_archived,
                search=search,
            )
            rows: list[MaterialRow] = []
            for material in materials:
                sections = uow.sections.list_by_material(material.id)
                rows.append(
                    material_row(
                        material,
                        index,
                        section_count=len(sections),
                        studied_sections=sum(1 for s in sections if s.is_studied),
                    )
                )
            return rows


class ResolveMaterialSource:
    """Le dice a la presentación cómo abrir un material, sin exponer el almacenamiento."""

    def __init__(self, uow: UnitOfWork, storage: FileStorage) -> None:
        self._uow = uow
        self._storage = storage

    def execute(self, *, material_id: EntityId) -> MaterialSource:
        with self._uow as uow:
            material = uow.materials.get(material_id)
            require(material, "El material no existe")
            assert material is not None
            path = (
                self._storage.path_for(material.blob_hash, material.blob_ext)
                if material.blob_hash
                else None
            )
            return MaterialSource(
                material_id=material.id,
                kind=material.kind,
                title=material.title,
                path=path,
                url=material.url,
                body=material.body,
                reading_position=material.reading_position,
            )


class PrepareEpubReading:
    """Deja un EPUB listo para leer y devuelve sus documentos en orden."""

    def __init__(self, uow: UnitOfWork, storage: FileStorage, unpacker: EpubUnpacker) -> None:
        self._uow = uow
        self._storage = storage
        self._unpacker = unpacker

    def execute(self, *, material_id: EntityId) -> list[Path]:
        with self._uow as uow:
            material = uow.materials.get(material_id)
            require(material, "El material no existe")
            assert material is not None
            if material.kind is not MaterialKind.EPUB or not material.blob_hash:
                raise ValueError("El material no es un EPUB de la biblioteca")
            path = self._storage.path_for(material.blob_hash, material.blob_ext)
        return self._unpacker.unpack(path, material.blob_hash)


class SplitMaterialEvenly:
    """Reemplaza las secciones de un material por N partes iguales."""

    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(self, *, material_id: EntityId, parts: int) -> tuple[EntityId, ...]:
        now = self._clock.now()
        with self._uow as uow:
            material = uow.materials.get(material_id)
            require(material, "El material no existe")
            assert material is not None
            for existing in uow.sections.list_by_material(material_id):
                uow.sections.delete(existing.id)
            sections = split_evenly(material, count=parts, now=now)
            uow.sections.add_many(sections)
            material.record(
                SectionsCreated(
                    material_id=material.id, section_ids=tuple(s.id for s in sections)
                ),
                at=now,
            )
            commit_and_publish(uow, self._bus, material)
            return tuple(s.id for s in sections)


def _is_youtube(url: str) -> bool:
    lowered = url.lower()
    return any(host in lowered for host in YOUTUBE_HOSTS)
