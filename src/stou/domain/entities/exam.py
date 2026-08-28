"""Examen: cierra el ciclo de vida del material.

Aprobar archiva las secciones del temario; reprobar las mantiene activas y habilita
un reintento que hereda el temario.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from stou.domain.entities.base import Entity
from stou.domain.events import ExamCreated, ExamRecorded
from stou.domain.values import ExamResult
from stou.shared.ids import EntityId, new_id


@dataclass(kw_only=True)
class Exam(Entity):
    title: str
    category_id: EntityId | None = None
    scheduled_at: datetime | None = None
    result: ExamResult = ExamResult.PENDING
    score: float | None = None
    notes: str = ""
    recorded_at: datetime | None = None
    retry_of: EntityId | None = None
    section_ids: list[EntityId] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        title: str,
        now: datetime,
        category_id: EntityId | None = None,
        scheduled_at: datetime | None = None,
        section_ids: list[EntityId] | None = None,
        retry_of: EntityId | None = None,
    ) -> Exam:
        clean = title.strip()
        if not clean:
            raise ValueError("El examen necesita un título")
        exam = cls(
            id=new_id(),
            created_at=now,
            updated_at=now,
            title=clean,
            category_id=category_id,
            scheduled_at=scheduled_at,
            section_ids=list(section_ids or []),
            retry_of=retry_of,
        )
        exam.record(ExamCreated(exam_id=exam.id, category_id=category_id, title=clean), at=now)
        return exam

    @property
    def is_recorded(self) -> bool:
        return self.result is not ExamResult.PENDING

    def set_syllabus(self, section_ids: list[EntityId], now: datetime) -> None:
        if self.is_recorded:
            raise ValueError("No se puede cambiar el temario de un examen ya registrado")
        self.section_ids = list(dict.fromkeys(section_ids))
        self.touch(now)

    def record_result(
        self,
        *,
        result: ExamResult,
        now: datetime,
        score: float | None = None,
        passed_section_ids: list[EntityId] | None = None,
    ) -> list[EntityId]:
        """Registra el resultado y devuelve las secciones que deben archivarse."""
        if result is ExamResult.PENDING:
            raise ValueError("Un resultado registrado no puede quedar pendiente")
        if self.is_recorded:
            raise ValueError("El examen ya tiene un resultado registrado")

        if passed_section_ids is not None:
            unknown = set(passed_section_ids) - set(self.section_ids)
            if unknown:
                raise ValueError("Hay secciones aprobadas que no están en el temario")
            to_archive = [sid for sid in self.section_ids if sid in set(passed_section_ids)]
        elif result is ExamResult.PASSED:
            to_archive = list(self.section_ids)
        else:
            to_archive = []

        self.result = result
        self.score = score
        self.recorded_at = now
        self.touch(now)
        self.record(
            ExamRecorded(
                exam_id=self.id, result=str(result), archived_section_ids=tuple(to_archive)
            ),
            at=now,
        )
        return to_archive

    def build_retry(self, *, now: datetime, scheduled_at: datetime | None = None) -> Exam:
        if self.result is not ExamResult.FAILED:
            raise ValueError("Solo un examen reprobado admite reintento")
        pending = [sid for sid in self.section_ids]
        return Exam.create(
            title=f"{self.title} (reintento)",
            now=now,
            category_id=self.category_id,
            scheduled_at=scheduled_at,
            section_ids=pending,
            retry_of=self.id,
        )
