"""Repositorios SQLite. Cumplen los puertos declarados en el dominio."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from stou.domain.entities.category import Category
from stou.domain.entities.exam import Exam
from stou.domain.entities.material import Material
from stou.domain.entities.section import Section
from stou.domain.entities.study_session import StudySession
from stou.domain.entities.task import Task
from stou.domain.values import MaterialKind, MaterialState, TaskStatus
from stou.infrastructure.persistence.database import Database
from stou.infrastructure.persistence.mappers import (
    dt_out,
    exam_params,
    material_params,
    section_params,
    session_params,
    task_params,
    to_category,
    to_exam,
    to_material,
    to_section,
    to_session,
    to_task,
    to_task_item,
)
from stou.shared.ids import EntityId


class _Base:
    def __init__(self, db: Database) -> None:
        self._db = db

    @property
    def _conn(self) -> sqlite3.Connection:
        return self._db.conn

    def _upsert(self, table: str, params: dict[str, object]) -> None:
        columns = list(params)
        placeholders = ", ".join(f":{c}" for c in columns)
        updates = ", ".join(f"{c} = excluded.{c}" for c in columns if c != "id")
        self._conn.execute(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}",
            params,
        )


def _in_clause(values: list[EntityId] | list[str]) -> str:
    return ", ".join("?" for _ in values)


class SqliteCategoryRepository(_Base):
    def add(self, category: Category) -> None:
        self._upsert("categories", self._params(category))

    def update(self, category: Category) -> None:
        self._upsert("categories", self._params(category))

    def get(self, category_id: EntityId) -> Category | None:
        row = self._conn.execute(
            "SELECT * FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        return to_category(row) if row else None

    def list_all(self) -> list[Category]:
        rows = self._conn.execute(
            "SELECT * FROM categories ORDER BY position, name COLLATE NOCASE"
        ).fetchall()
        return [to_category(r) for r in rows]

    def delete(self, category_id: EntityId) -> None:
        self._conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))

    def has_children(self, category_id: EntityId) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM categories WHERE parent_id = ? LIMIT 1", (category_id,)
        ).fetchone()
        return row is not None

    @staticmethod
    def _params(category: Category) -> dict[str, object]:
        return {
            "id": category.id,
            "name": category.name,
            "parent_id": category.parent_id,
            "color": category.color,
            "position": category.position,
            "created_at": dt_out(category.created_at),
            "updated_at": dt_out(category.updated_at),
        }


class SqliteMaterialRepository(_Base):
    def add(self, material: Material) -> None:
        self._upsert("materials", material_params(material))

    def update(self, material: Material) -> None:
        self._upsert("materials", material_params(material))

    def get(self, material_id: EntityId) -> Material | None:
        row = self._conn.execute(
            "SELECT * FROM materials WHERE id = ?", (material_id,)
        ).fetchone()
        return to_material(row) if row else None

    def delete(self, material_id: EntityId) -> None:
        self._conn.execute("DELETE FROM materials WHERE id = ?", (material_id,))

    def find_by_hash(self, blob_hash: str) -> Material | None:
        row = self._conn.execute(
            "SELECT * FROM materials WHERE blob_hash = ?", (blob_hash,)
        ).fetchone()
        return to_material(row) if row else None

    def list_all(
        self,
        *,
        category_ids: list[EntityId] | None = None,
        kinds: list[MaterialKind] | None = None,
        include_archived: bool = False,
        search: str | None = None,
        limit: int | None = None,
    ) -> list[Material]:
        sql = "SELECT * FROM materials WHERE 1 = 1"
        params: list[object] = []
        if not include_archived:
            sql += " AND state = ?"
            params.append(str(MaterialState.ACTIVE))
        if category_ids is not None:
            if not category_ids:
                return []
            sql += f" AND category_id IN ({_in_clause(category_ids)})"
            params.extend(category_ids)
        if kinds:
            sql += f" AND kind IN ({_in_clause([str(k) for k in kinds])})"
            params.extend(str(k) for k in kinds)
        if search:
            sql += " AND title LIKE ?"
            params.append(f"%{search}%")
        sql += " ORDER BY title COLLATE NOCASE"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [to_material(r) for r in rows]

    def count(self, *, include_archived: bool = False) -> int:
        sql = "SELECT COUNT(*) FROM materials"
        params: list[object] = []
        if not include_archived:
            sql += " WHERE state = ?"
            params.append(str(MaterialState.ACTIVE))
        return int(self._conn.execute(sql, params).fetchone()[0])


class SqliteSectionRepository(_Base):
    def add(self, section: Section) -> None:
        self._upsert("sections", section_params(section))

    def add_many(self, sections: list[Section]) -> None:
        for section in sections:
            self._upsert("sections", section_params(section))

    def update(self, section: Section) -> None:
        self._upsert("sections", section_params(section))

    def get(self, section_id: EntityId) -> Section | None:
        row = self._conn.execute(
            "SELECT * FROM sections WHERE id = ?", (section_id,)
        ).fetchone()
        return to_section(row) if row else None

    def delete(self, section_id: EntityId) -> None:
        self._conn.execute("DELETE FROM sections WHERE id = ?", (section_id,))

    def list_by_material(
        self, material_id: EntityId, *, include_archived: bool = True
    ) -> list[Section]:
        sql = "SELECT * FROM sections WHERE material_id = ?"
        params: list[object] = [material_id]
        if not include_archived:
            sql += " AND state = ?"
            params.append(str(MaterialState.ACTIVE))
        sql += " ORDER BY position, range_start"
        rows = self._conn.execute(sql, params).fetchall()
        return [to_section(r) for r in rows]

    def list_by_ids(self, section_ids: list[EntityId]) -> list[Section]:
        if not section_ids:
            return []
        rows = self._conn.execute(
            f"SELECT * FROM sections WHERE id IN ({_in_clause(section_ids)})", section_ids
        ).fetchall()
        return [to_section(r) for r in rows]

    def list_by_categories(
        self,
        category_ids: list[EntityId],
        *,
        include_archived: bool = False,
        only_unstudied: bool = False,
    ) -> list[Section]:
        if not category_ids:
            return []
        sql = (
            "SELECT s.* FROM sections s JOIN materials m ON m.id = s.material_id "
            f"WHERE m.category_id IN ({_in_clause(category_ids)})"
        )
        params: list[object] = list(category_ids)
        if not include_archived:
            sql += " AND s.state = ?"
            params.append(str(MaterialState.ACTIVE))
        if only_unstudied:
            sql += " AND s.studied_at IS NULL"
        sql += " ORDER BY m.title COLLATE NOCASE, s.position"
        rows = self._conn.execute(sql, params).fetchall()
        return [to_section(r) for r in rows]


class SqliteTaskRepository(_Base):
    def add(self, task: Task) -> None:
        self._write(task)

    def update(self, task: Task) -> None:
        self._write(task)

    def _write(self, task: Task) -> None:
        self._upsert("tasks", task_params(task))
        self._conn.execute("DELETE FROM task_items WHERE task_id = ?", (task.id,))
        for position, item in enumerate(task.items):
            self._conn.execute(
                "INSERT INTO task_items "
                "(id, task_id, material_id, section_id, position, role) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    item.id,
                    task.id,
                    item.material_id,
                    item.section_id,
                    position,
                    str(item.role),
                ),
            )

    def get(self, task_id: EntityId) -> Task | None:
        row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        return to_task(row, self._items(task_id))

    def delete(self, task_id: EntityId) -> None:
        self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    def list_all(
        self,
        *,
        category_ids: list[EntityId] | None = None,
        statuses: list[TaskStatus] | None = None,
        due_from: datetime | None = None,
        due_to: datetime | None = None,
        search: str | None = None,
        limit: int | None = None,
    ) -> list[Task]:
        sql = "SELECT * FROM tasks WHERE 1 = 1"
        params: list[object] = []
        if category_ids is not None:
            if not category_ids:
                return []
            sql += f" AND category_id IN ({_in_clause(category_ids)})"
            params.extend(category_ids)
        if statuses:
            sql += f" AND status IN ({_in_clause([str(s) for s in statuses])})"
            params.extend(str(s) for s in statuses)
        if due_from is not None:
            sql += " AND due_at >= ?"
            params.append(dt_out(due_from))
        if due_to is not None:
            sql += " AND due_at < ?"
            params.append(dt_out(due_to))
        if search:
            sql += " AND (title LIKE ? OR description LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        sql += (
            " ORDER BY CASE WHEN due_at IS NULL THEN 1 ELSE 0 END, due_at, "
            "position, title COLLATE NOCASE"
        )
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [to_task(r, self._items(EntityId(r["id"]))) for r in rows]

    def list_children(self, parent_id: EntityId) -> list[Task]:
        rows = self._conn.execute(
            "SELECT * FROM tasks WHERE parent_id = ? ORDER BY position", (parent_id,)
        ).fetchall()
        return [to_task(r, self._items(EntityId(r["id"]))) for r in rows]

    def list_by_section(self, section_id: EntityId) -> list[Task]:
        rows = self._conn.execute(
            "SELECT t.* FROM tasks t JOIN task_items i ON i.task_id = t.id "
            "WHERE i.section_id = ? ORDER BY t.due_at",
            (section_id,),
        ).fetchall()
        return [to_task(r, self._items(EntityId(r["id"]))) for r in rows]

    def _items(self, task_id: EntityId) -> list:
        rows = self._conn.execute(
            "SELECT * FROM task_items WHERE task_id = ? ORDER BY position", (task_id,)
        ).fetchall()
        return [to_task_item(r) for r in rows]


class SqliteStudySessionRepository(_Base):
    def add(self, session: StudySession) -> None:
        self._upsert("study_sessions", session_params(session))

    def update(self, session: StudySession) -> None:
        self._upsert("study_sessions", session_params(session))

    def get(self, session_id: EntityId) -> StudySession | None:
        row = self._conn.execute(
            "SELECT * FROM study_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return to_session(row) if row else None

    def delete(self, session_id: EntityId) -> None:
        self._conn.execute("DELETE FROM study_sessions WHERE id = ?", (session_id,))

    def list_open(self) -> list[StudySession]:
        rows = self._conn.execute(
            "SELECT * FROM study_sessions WHERE ended_at IS NULL ORDER BY started_at"
        ).fetchall()
        return [to_session(r) for r in rows]

    def list_by_task(self, task_id: EntityId) -> list[StudySession]:
        rows = self._conn.execute(
            "SELECT * FROM study_sessions WHERE task_id = ? ORDER BY started_at DESC",
            (task_id,),
        ).fetchall()
        return [to_session(r) for r in rows]

    def list_between(self, start: datetime, end: datetime) -> list[StudySession]:
        rows = self._conn.execute(
            "SELECT * FROM study_sessions WHERE started_at >= ? AND started_at < ? "
            "ORDER BY started_at",
            (dt_out(start), dt_out(end)),
        ).fetchall()
        return [to_session(r) for r in rows]


class SqliteExamRepository(_Base):
    def add(self, exam: Exam) -> None:
        self._write(exam)

    def update(self, exam: Exam) -> None:
        self._write(exam)

    def _write(self, exam: Exam) -> None:
        self._upsert("exams", exam_params(exam))
        self._conn.execute("DELETE FROM exam_sections WHERE exam_id = ?", (exam.id,))
        for position, section_id in enumerate(exam.section_ids):
            self._conn.execute(
                "INSERT OR IGNORE INTO exam_sections (exam_id, section_id, position) "
                "VALUES (?, ?, ?)",
                (exam.id, section_id, position),
            )

    def get(self, exam_id: EntityId) -> Exam | None:
        row = self._conn.execute("SELECT * FROM exams WHERE id = ?", (exam_id,)).fetchone()
        if row is None:
            return None
        return to_exam(row, self._section_ids(exam_id))

    def delete(self, exam_id: EntityId) -> None:
        self._conn.execute("DELETE FROM exams WHERE id = ?", (exam_id,))

    def list_all(
        self,
        *,
        category_ids: list[EntityId] | None = None,
        scheduled_from: datetime | None = None,
        scheduled_to: datetime | None = None,
        pending_only: bool = False,
    ) -> list[Exam]:
        sql = "SELECT * FROM exams WHERE 1 = 1"
        params: list[object] = []
        if category_ids is not None:
            if not category_ids:
                return []
            sql += f" AND category_id IN ({_in_clause(category_ids)})"
            params.extend(category_ids)
        if scheduled_from is not None:
            sql += " AND scheduled_at >= ?"
            params.append(dt_out(scheduled_from))
        if scheduled_to is not None:
            sql += " AND scheduled_at < ?"
            params.append(dt_out(scheduled_to))
        if pending_only:
            sql += " AND result = 'pending'"
        sql += " ORDER BY CASE WHEN scheduled_at IS NULL THEN 1 ELSE 0 END, scheduled_at"
        rows = self._conn.execute(sql, params).fetchall()
        return [to_exam(r, self._section_ids(EntityId(r["id"]))) for r in rows]

    def _section_ids(self, exam_id: EntityId) -> list[EntityId]:
        rows = self._conn.execute(
            "SELECT section_id FROM exam_sections WHERE exam_id = ? ORDER BY position",
            (exam_id,),
        ).fetchall()
        return [EntityId(r["section_id"]) for r in rows]
