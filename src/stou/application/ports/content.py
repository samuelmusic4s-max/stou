"""Puertos de contenido: almacenamiento de archivos e inspección de material."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from stou.domain.values import MaterialKind


@dataclass(frozen=True, slots=True)
class StoredBlob:
    hash: str
    ext: str
    size_bytes: int


class FileStorage(Protocol):
    """Guarda los archivos del usuario por hash de contenido."""

    def store(self, source: Path) -> StoredBlob: ...

    def path_for(self, blob_hash: str, ext: str) -> Path: ...

    def exists(self, blob_hash: str, ext: str) -> bool: ...

    def delete(self, blob_hash: str, ext: str) -> None: ...


@dataclass(frozen=True, slots=True)
class OutlineEntry:
    """Entrada de la estructura interna de un material (capítulo, marcador)."""

    title: str
    start: float
    end: float | None = None
    level: int = 0


@dataclass(frozen=True, slots=True)
class InspectedMaterial:
    kind: MaterialKind
    title: str | None = None
    page_count: int | None = None
    duration_seconds: float | None = None
    outline: tuple[OutlineEntry, ...] = field(default=())


class MaterialInspector(Protocol):
    """Lee metadatos y estructura de un archivo para seccionarlo automáticamente."""

    def detect_kind(self, path: Path) -> MaterialKind: ...

    def inspect(self, path: Path, kind: MaterialKind) -> InspectedMaterial: ...


class TextExtractor(Protocol):
    """Extrae texto para el índice de búsqueda."""

    def supports(self, kind: MaterialKind) -> bool: ...

    def extract(self, path: Path, kind: MaterialKind) -> list[tuple[float, str]]:
        """Devuelve pares (posición, texto). La posición usa la unidad del material."""
        ...


class EpubUnpacker(Protocol):
    """Descomprime un EPUB y devuelve sus documentos en el orden de lectura.

    Existe para que la presentación pueda mostrar un libro sin saber nada del
    formato: recibe una lista de archivos y navega entre ellos.
    """

    def unpack(self, path: Path, key: str) -> list[Path]: ...
