"""Enums y value objects del dominio."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MaterialKind(StrEnum):
    PDF = "pdf"
    EPUB = "epub"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    WEB = "web"
    YOUTUBE = "youtube"
    NOTE = "note"
    OTHER = "other"

    @property
    def is_remote(self) -> bool:
        return self in (MaterialKind.WEB, MaterialKind.YOUTUBE)


class MaterialState(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class ExamResult(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"


class ItemRole(StrEnum):
    """Para qué sirve un material dentro de una tarea.

    Una tarea de estudio y su solución no son la misma cosa aunque las dos sean
    material: la solución se consulta *después* de intentarlo. Sin distinguirlas, el
    modo estudio abriría la respuesta junto al enunciado.
    """

    MATERIAL = "material"
    SOLUTION = "solution"


class LocatorUnit(StrEnum):
    """Unidad en la que se delimita una sección según el tipo de material."""

    PAGE = "page"          # PDF
    LOCATION = "location"  # EPUB
    SECOND = "second"      # video / audio
    NONE = "none"          # material sin estructura interna


@dataclass(frozen=True, slots=True)
class Locator:
    """Intervalo cerrado que delimita una sección dentro de un material."""

    unit: LocatorUnit
    start: float = 0.0
    end: float | None = None

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError("El inicio de una sección no puede ser negativo")
        if self.end is not None and self.end < self.start:
            raise ValueError("El fin de una sección no puede ser anterior a su inicio")

    @property
    def length(self) -> float | None:
        return None if self.end is None else self.end - self.start

    def label(self) -> str:
        if self.unit is LocatorUnit.PAGE:
            if self.end:
                return f"págs. {int(self.start)}–{int(self.end)}"
            return f"pág. {int(self.start)}"
        if self.unit is LocatorUnit.SECOND:
            if self.end:
                return f"{_hhmmss(self.start)}–{_hhmmss(self.end)}"
            return _hhmmss(self.start)
        if self.unit is LocatorUnit.LOCATION:
            if self.end:
                return f"pos. {int(self.start)}–{int(self.end)}"
            return f"pos. {int(self.start)}"
        return ""

    @staticmethod
    def whole() -> Locator:
        return Locator(unit=LocatorUnit.NONE, start=0.0, end=None)


def _hhmmss(total: float) -> str:
    total_s = int(total)
    h, rem = divmod(total_s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
