"""Material: una unidad de contenido de la biblioteca."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from stou.domain.entities.base import Entity
from stou.domain.events import (
    MaterialArchived,
    MaterialImported,
    MaterialReactivated,
    MaterialUpdated,
    ReadingPositionSaved,
)
from stou.domain.values import MaterialKind, MaterialState
from stou.shared.ids import EntityId, new_id


@dataclass(kw_only=True)
class Material(Entity):
    kind: MaterialKind
    title: str
    category_id: EntityId | None = None
    state: MaterialState = MaterialState.ACTIVE
    # Contenido local: referencia al blob store (hash de contenido).
    blob_hash: str | None = None
    blob_ext: str = ""
    size_bytes: int = 0
    # Contenido remoto o nota.
    url: str | None = None
    body: str | None = None
    # Metadatos de consumo.
    source: str | None = None
    page_count: int | None = None
    duration_seconds: float | None = None
    reading_position: float = 0.0
    tags: list[str] = field(default_factory=list)
    text_indexed: bool = False

    @classmethod
    def create(
        cls,
        *,
        kind: MaterialKind,
        title: str,
        now: datetime,
        category_id: EntityId | None = None,
        blob_hash: str | None = None,
        blob_ext: str = "",
        size_bytes: int = 0,
        url: str | None = None,
        body: str | None = None,
        source: str | None = None,
        page_count: int | None = None,
        duration_seconds: float | None = None,
    ) -> Material:
        clean = title.strip()
        if not clean:
            raise ValueError("El material necesita un título")
        if kind.is_remote and not url:
            raise ValueError("Un material remoto necesita una URL")
        if not kind.is_remote and kind is not MaterialKind.NOTE and not blob_hash:
            raise ValueError("Un material local necesita un archivo almacenado")

        material = cls(
            id=new_id(),
            created_at=now,
            updated_at=now,
            kind=kind,
            title=clean,
            category_id=category_id,
            blob_hash=blob_hash,
            blob_ext=blob_ext,
            size_bytes=size_bytes,
            url=url,
            body=body,
            source=source,
            page_count=page_count,
            duration_seconds=duration_seconds,
        )
        material.record(
            MaterialImported(
                material_id=material.id,
                category_id=category_id,
                kind=str(kind),
                title=clean,
            ),
            at=now,
        )
        return material

    @property
    def is_active(self) -> bool:
        return self.state is MaterialState.ACTIVE

    def rename(self, title: str, now: datetime) -> None:
        clean = title.strip()
        if not clean:
            raise ValueError("El material necesita un título")
        if clean == self.title:
            return
        self.title = clean
        self.touch(now)
        self.record(MaterialUpdated(material_id=self.id), at=now)

    def move_to_category(self, category_id: EntityId | None, now: datetime) -> None:
        if category_id == self.category_id:
            return
        self.category_id = category_id
        self.touch(now)
        self.record(MaterialUpdated(material_id=self.id), at=now)

    def edit_body(self, body: str, now: datetime) -> None:
        if self.kind is not MaterialKind.NOTE:
            raise ValueError("Solo una nota tiene cuerpo editable")
        if body == self.body:
            return
        self.body = body
        self.touch(now)
        self.record(MaterialUpdated(material_id=self.id), at=now)

    def save_reading_position(self, position: float, now: datetime) -> None:
        if position < 0:
            raise ValueError("La posición de lectura no puede ser negativa")
        if position == self.reading_position:
            return
        self.reading_position = position
        self.touch(now)
        self.record(ReadingPositionSaved(material_id=self.id, position=position), at=now)

    def archive(self, now: datetime) -> None:
        if self.state is MaterialState.ARCHIVED:
            return
        self.state = MaterialState.ARCHIVED
        self.touch(now)
        self.record(MaterialArchived(material_id=self.id), at=now)

    def reactivate(self, now: datetime) -> None:
        if self.state is MaterialState.ACTIVE:
            return
        self.state = MaterialState.ACTIVE
        self.touch(now)
        self.record(MaterialReactivated(material_id=self.id), at=now)

    def mark_indexed(self, now: datetime) -> None:
        self.text_indexed = True
        self.touch(now)
