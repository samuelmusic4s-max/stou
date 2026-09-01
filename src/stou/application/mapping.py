"""Traducción de entidades a DTOs. Función pura: no toca repositorios."""

from __future__ import annotations

from datetime import datetime

from stou.application.dto import (
    CategoryNode,
    ExamRow,
    MaterialRow,
    SectionRow,
    SessionRow,
    TaskItemRow,
    TaskRow,
)
from stou.domain.entities.category import Category
from stou.domain.entities.exam import Exam
from stou.domain.entities.material import Material
from stou.domain.entities.section import Section
from stou.domain.entities.study_session import StudySession
from stou.domain.entities.task import Task
from stou.domain.values import ItemRole, MaterialState, TaskStatus
from stou.shared.ids import EntityId

UNCATEGORIZED = "Sin categoría"


class CategoryIndex:
    """Índice en memoria de la jerarquía de categorías."""

    def __init__(self, categories: list[Category]) -> None:
        self._by_id: dict[EntityId, Category] = {c.id: c for c in categories}
        self._children: dict[EntityId | None, list[Category]] = {}
        for category in sorted(categories, key=lambda c: (c.position, c.name.lower())):
            self._children.setdefault(category.parent_id, []).append(category)

    def get(self, category_id: EntityId | None) -> Category | None:
        return self._by_id.get(category_id) if category_id else None

    def path(self, category_id: EntityId | None) -> str:
        if not category_id:
            return UNCATEGORIZED
        parts: list[str] = []
        current = self._by_id.get(category_id)
        guard = 0
        while current is not None and guard < 64:
            parts.append(current.name)
            current = self._by_id.get(current.parent_id) if current.parent_id else None
            guard += 1
        return " › ".join(reversed(parts)) if parts else UNCATEGORIZED

    def color(self, category_id: EntityId | None) -> str:
        category = self.get(category_id)
        return category.color if category else "#8A8A8A"

    def with_descendants(self, category_id: EntityId | None) -> list[EntityId]:
        """La categoría y todas sus descendientes."""
        if not category_id:
            return []
        out: list[EntityId] = []
        stack = [category_id]
        while stack:
            current = stack.pop()
            if current in out:
                continue
            out.append(current)
            stack.extend(child.id for child in self._children.get(current, []))
        return out

    def is_descendant(self, candidate: EntityId, ancestor: EntityId) -> bool:
        return candidate in self.with_descendants(ancestor)

    def tree(self) -> tuple[CategoryNode, ...]:
        return tuple(self._node(c) for c in self._children.get(None, []))

    def _node(self, category: Category) -> CategoryNode:
        return CategoryNode(
            id=category.id,
            name=category.name,
            color=category.color,
            parent_id=category.parent_id,
            children=tuple(self._node(c) for c in self._children.get(category.id, [])),
        )


def material_row(
    material: Material,
    index: CategoryIndex,
    *,
    section_count: int = 0,
    studied_sections: int = 0,
) -> MaterialRow:
    return MaterialRow(
        id=material.id,
        title=material.title,
        kind=material.kind,
        category_id=material.category_id,
        category_path=index.path(material.category_id),
        archived=material.state is MaterialState.ARCHIVED,
        section_count=section_count,
        studied_sections=studied_sections,
        size_bytes=material.size_bytes,
        url=material.url,
        has_blob=material.blob_hash is not None,
    )


def section_row(section: Section, material: Material, *, level: int = 0) -> SectionRow:
    return SectionRow(
        id=section.id,
        material_id=section.material_id,
        material_title=material.title,
        material_kind=material.kind,
        title=section.title,
        range_label=section.locator.label(),
        start=section.locator.start,
        end=section.locator.end,
        studied=section.is_studied,
        archived=section.state is MaterialState.ARCHIVED,
        level=level,
    )


def task_row(
    task: Task,
    index: CategoryIndex,
    *,
    now: datetime,
    spent_seconds: int = 0,
    studied_items: int = 0,
) -> TaskRow:
    closed = (TaskStatus.DONE, TaskStatus.CANCELLED)
    overdue = bool(task.due_at and task.due_at < now and task.status not in closed)
    return TaskRow(
        id=task.id,
        title=task.title,
        status=task.status,
        priority=task.priority,
        category_id=task.category_id,
        category_path=index.path(task.category_id),
        due_at=task.due_at,
        start_at=task.start_at,
        estimated_minutes=task.estimated_minutes,
        # Solo el enunciado cuenta para el progreso; la solución no se «estudia».
        item_count=len(task.material_items),
        studied_items=studied_items,
        spent_seconds=spent_seconds,
        overdue=overdue,
    )


def task_item_row(
    item_id: EntityId,
    material: Material,
    section: Section | None,
    position: int,
    role: ItemRole = ItemRole.MATERIAL,
) -> TaskItemRow:
    return TaskItemRow(
        item_id=item_id,
        material_id=material.id,
        section_id=section.id if section else None,
        title=f"{material.title} — {section.title}" if section else material.title,
        kind=material.kind,
        range_label=section.locator.label() if section else "",
        studied=section.is_studied if section else False,
        position=position,
        role=role,
    )


def exam_row(exam: Exam, index: CategoryIndex) -> ExamRow:
    return ExamRow(
        id=exam.id,
        title=exam.title,
        category_id=exam.category_id,
        category_path=index.path(exam.category_id),
        scheduled_at=exam.scheduled_at,
        result=exam.result,
        score=exam.score,
        section_count=len(exam.section_ids),
    )


def session_row(
    session: StudySession, task: Task | None, index: CategoryIndex
) -> SessionRow:
    return SessionRow(
        id=session.id,
        task_id=session.task_id,
        task_title=task.title if task else "(tarea eliminada)",
        category_path=index.path(session.category_id),
        started_at=session.started_at,
        ended_at=session.ended_at,
        effective_seconds=session.effective_seconds,
        manual=session.manual,
    )
