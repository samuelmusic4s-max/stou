"""Conversión entre filas de SQLite y entidades de dominio."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from stou.domain.entities.category import Category
from stou.domain.entities.exam import Exam
from stou.domain.entities.material import Material
from stou.domain.entities.section import Section
from stou.domain.entities.study_session import StudySession
from stou.domain.entities.task import Task, TaskItem
from stou.domain.values import (
    ExamResult,
    Locator,
    LocatorUnit,
    MaterialKind,
    MaterialState,
    Priority,
    TaskStatus,
)
from stou.shared.ids import EntityId


def dt_out(moment: datetime | None) -> str | None:
    if moment is None:
        return None
    return moment.astimezone(UTC).isoformat()


def dt_in(raw: str | None) -> datetime | None:
    if not raw:
        return None
    parsed = datetime.fromisoformat(raw)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def require_dt(raw: str | None) -> datetime:
    value = dt_in(raw)
    if value is None:
        raise ValueError("Se esperaba una fecha en la base de datos")
    return value


def to_category(row: sqlite3.Row) -> Category:
    return Category(
        id=EntityId(row["id"]),
        created_at=require_dt(row["created_at"]),
        updated_at=require_dt(row["updated_at"]),
        name=row["name"],
        parent_id=EntityId(row["parent_id"]) if row["parent_id"] else None,
        color=row["color"],
        position=row["position"],
    )


def to_material(row: sqlite3.Row) -> Material:
    tags = [t for t in (row["tags"] or "").split("\u001f") if t]
    return Material(
        id=EntityId(row["id"]),
        created_at=require_dt(row["created_at"]),
        updated_at=require_dt(row["updated_at"]),
        kind=MaterialKind(row["kind"]),
        title=row["title"],
        category_id=EntityId(row["category_id"]) if row["category_id"] else None,
        state=MaterialState(row["state"]),
        blob_hash=row["blob_hash"],
        blob_ext=row["blob_ext"],
        size_bytes=row["size_bytes"],
        url=row["url"],
        body=row["body"],
        source=row["source"],
        page_count=row["page_count"],
        duration_seconds=row["duration_seconds"],
        reading_position=row["reading_position"],
        tags=tags,
        text_indexed=bool(row["text_indexed"]),
    )


def material_params(material: Material) -> dict[str, object]:
    return {
        "id": material.id,
        "kind": str(material.kind),
        "title": material.title,
        "category_id": material.category_id,
        "state": str(material.state),
        "blob_hash": material.blob_hash,
        "blob_ext": material.blob_ext,
        "size_bytes": material.size_bytes,
        "url": material.url,
        "body": material.body,
        "source": material.source,
        "page_count": material.page_count,
        "duration_seconds": material.duration_seconds,
        "reading_position": material.reading_position,
        "tags": "\u001f".join(material.tags),
        "text_indexed": int(material.text_indexed),
        "created_at": dt_out(material.created_at),
        "updated_at": dt_out(material.updated_at),
    }


def to_section(row: sqlite3.Row) -> Section:
    return Section(
        id=EntityId(row["id"]),
        created_at=require_dt(row["created_at"]),
        updated_at=require_dt(row["updated_at"]),
        material_id=EntityId(row["material_id"]),
        parent_id=EntityId(row["parent_id"]) if row["parent_id"] else None,
        title=row["title"],
        locator=Locator(
            unit=LocatorUnit(row["unit"]),
            start=row["range_start"],
            end=row["range_end"],
        ),
        position=row["position"],
        state=MaterialState(row["state"]),
        studied_at=dt_in(row["studied_at"]),
        notes=row["notes"],
    )


def section_params(section: Section) -> dict[str, object]:
    return {
        "id": section.id,
        "material_id": section.material_id,
        "parent_id": section.parent_id,
        "title": section.title,
        "unit": str(section.locator.unit),
        "range_start": section.locator.start,
        "range_end": section.locator.end,
        "position": section.position,
        "state": str(section.state),
        "studied_at": dt_out(section.studied_at),
        "notes": section.notes,
        "created_at": dt_out(section.created_at),
        "updated_at": dt_out(section.updated_at),
    }


def to_task(row: sqlite3.Row, items: list[TaskItem]) -> Task:
    return Task(
        id=EntityId(row["id"]),
        created_at=require_dt(row["created_at"]),
        updated_at=require_dt(row["updated_at"]),
        title=row["title"],
        description=row["description"],
        category_id=EntityId(row["category_id"]) if row["category_id"] else None,
        parent_id=EntityId(row["parent_id"]) if row["parent_id"] else None,
        status=TaskStatus(row["status"]),
        priority=Priority(row["priority"]),
        start_at=dt_in(row["start_at"]),
        due_at=dt_in(row["due_at"]),
        estimated_minutes=row["estimated_minutes"],
        completed_at=dt_in(row["completed_at"]),
        position=row["position"],
        items=items,
    )


def task_params(task: Task) -> dict[str, object]:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "category_id": task.category_id,
        "parent_id": task.parent_id,
        "status": str(task.status),
        "priority": str(task.priority),
        "start_at": dt_out(task.start_at),
        "due_at": dt_out(task.due_at),
        "estimated_minutes": task.estimated_minutes,
        "completed_at": dt_out(task.completed_at),
        "position": task.position,
        "created_at": dt_out(task.created_at),
        "updated_at": dt_out(task.updated_at),
    }


def to_task_item(row: sqlite3.Row) -> TaskItem:
    return TaskItem(
        id=EntityId(row["id"]),
        task_id=EntityId(row["task_id"]),
        material_id=EntityId(row["material_id"]),
        section_id=EntityId(row["section_id"]) if row["section_id"] else None,
        position=row["position"],
    )


def to_session(row: sqlite3.Row) -> StudySession:
    return StudySession(
        id=EntityId(row["id"]),
        created_at=require_dt(row["created_at"]),
        updated_at=require_dt(row["updated_at"]),
        task_id=EntityId(row["task_id"]),
        category_id=EntityId(row["category_id"]) if row["category_id"] else None,
        started_at=require_dt(row["started_at"]),
        ended_at=dt_in(row["ended_at"]),
        last_activity_at=require_dt(row["last_activity_at"]),
        last_tick_at=require_dt(row["last_tick_at"]),
        accumulated_seconds=row["accumulated_seconds"],
        paused=bool(row["paused"]),
        material_id=EntityId(row["material_id"]) if row["material_id"] else None,
        manual=bool(row["manual"]),
    )


def session_params(session: StudySession) -> dict[str, object]:
    return {
        "id": session.id,
        "task_id": session.task_id,
        "category_id": session.category_id,
        "started_at": dt_out(session.started_at),
        "ended_at": dt_out(session.ended_at),
        "last_activity_at": dt_out(session.last_activity_at),
        "last_tick_at": dt_out(session.last_tick_at),
        "accumulated_seconds": session.accumulated_seconds,
        "paused": int(session.paused),
        "material_id": session.material_id,
        "manual": int(session.manual),
        "created_at": dt_out(session.created_at),
        "updated_at": dt_out(session.updated_at),
    }


def to_exam(row: sqlite3.Row, section_ids: list[EntityId]) -> Exam:
    return Exam(
        id=EntityId(row["id"]),
        created_at=require_dt(row["created_at"]),
        updated_at=require_dt(row["updated_at"]),
        title=row["title"],
        category_id=EntityId(row["category_id"]) if row["category_id"] else None,
        scheduled_at=dt_in(row["scheduled_at"]),
        result=ExamResult(row["result"]),
        score=row["score"],
        notes=row["notes"],
        recorded_at=dt_in(row["recorded_at"]),
        retry_of=EntityId(row["retry_of"]) if row["retry_of"] else None,
        section_ids=section_ids,
    )


def exam_params(exam: Exam) -> dict[str, object]:
    return {
        "id": exam.id,
        "title": exam.title,
        "category_id": exam.category_id,
        "scheduled_at": dt_out(exam.scheduled_at),
        "result": str(exam.result),
        "score": exam.score,
        "notes": exam.notes,
        "recorded_at": dt_out(exam.recorded_at),
        "retry_of": exam.retry_of,
        "created_at": dt_out(exam.created_at),
        "updated_at": dt_out(exam.updated_at),
    }
