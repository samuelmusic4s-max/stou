"""Eventos de dominio.

Un evento es un hecho ya ocurrido. Son inmutables y solo transportan IDs y datos
serializables: quien reacciona vuelve a consultar lo que necesite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from stou.shared.ids import EntityId, new_id


@dataclass(frozen=True, slots=True, kw_only=True)
class DomainEvent:
    event_id: EntityId = field(default_factory=new_id)
    occurred_at: datetime | None = None

    @property
    def event_name(self) -> str:
        """Nombre del hecho. No se llama ``name`` porque varios eventos llevan un
        campo ``name`` propio y se taparían entre sí."""
        return type(self).__name__


# --- Categorías ---------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class CategoryCreated(DomainEvent):
    category_id: EntityId
    parent_id: EntityId | None
    name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class CategoryRenamed(DomainEvent):
    category_id: EntityId
    name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class CategoryMoved(DomainEvent):
    category_id: EntityId
    parent_id: EntityId | None


@dataclass(frozen=True, slots=True, kw_only=True)
class CategoryDeleted(DomainEvent):
    category_id: EntityId


# --- Material -----------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class MaterialImported(DomainEvent):
    material_id: EntityId
    category_id: EntityId | None
    kind: str
    title: str


@dataclass(frozen=True, slots=True, kw_only=True)
class MaterialUpdated(DomainEvent):
    material_id: EntityId


@dataclass(frozen=True, slots=True, kw_only=True)
class MaterialDeleted(DomainEvent):
    material_id: EntityId


@dataclass(frozen=True, slots=True, kw_only=True)
class MaterialArchived(DomainEvent):
    material_id: EntityId


@dataclass(frozen=True, slots=True, kw_only=True)
class MaterialReactivated(DomainEvent):
    material_id: EntityId


@dataclass(frozen=True, slots=True, kw_only=True)
class ReadingPositionSaved(DomainEvent):
    material_id: EntityId
    position: float


# --- Secciones ----------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class SectionsCreated(DomainEvent):
    material_id: EntityId
    section_ids: tuple[EntityId, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class SectionStudied(DomainEvent):
    section_id: EntityId
    material_id: EntityId


@dataclass(frozen=True, slots=True, kw_only=True)
class SectionArchived(DomainEvent):
    section_id: EntityId
    material_id: EntityId


# --- Tareas -------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskCreated(DomainEvent):
    task_id: EntityId
    category_id: EntityId | None
    title: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskUpdated(DomainEvent):
    task_id: EntityId


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskStatusChanged(DomainEvent):
    task_id: EntityId
    status: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskCompleted(DomainEvent):
    task_id: EntityId


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskDeleted(DomainEvent):
    task_id: EntityId


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskScheduled(DomainEvent):
    task_id: EntityId
    due_at: datetime | None


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskMaterialAssigned(DomainEvent):
    task_id: EntityId
    material_id: EntityId
    section_id: EntityId | None


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskMaterialUnassigned(DomainEvent):
    task_id: EntityId
    item_id: EntityId


# --- Sesiones de estudio ------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class StudySessionStarted(DomainEvent):
    session_id: EntityId
    task_id: EntityId


@dataclass(frozen=True, slots=True, kw_only=True)
class StudySessionPaused(DomainEvent):
    session_id: EntityId
    reason: str


@dataclass(frozen=True, slots=True, kw_only=True)
class StudySessionResumed(DomainEvent):
    session_id: EntityId


@dataclass(frozen=True, slots=True, kw_only=True)
class StudySessionClosed(DomainEvent):
    session_id: EntityId
    task_id: EntityId
    effective_seconds: int


# --- Exámenes -----------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class ExamCreated(DomainEvent):
    exam_id: EntityId
    category_id: EntityId | None
    title: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExamRecorded(DomainEvent):
    exam_id: EntityId
    result: str
    archived_section_ids: tuple[EntityId, ...]
