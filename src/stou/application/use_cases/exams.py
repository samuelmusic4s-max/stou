"""Casos de uso de exámenes: cierran el ciclo de vida del material."""

from __future__ import annotations

from datetime import datetime

from stou.application.dto import ExamRow
from stou.application.mapping import CategoryIndex, exam_row
from stou.application.ports.event_bus import EventBus
from stou.application.ports.unit_of_work import UnitOfWork
from stou.application.use_cases._shared import commit_and_publish, require
from stou.domain.entities.exam import Exam
from stou.domain.values import ExamResult
from stou.shared.clock import Clock
from stou.shared.ids import EntityId


class CreateExam:
    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(
        self,
        *,
        title: str,
        category_id: EntityId | None = None,
        scheduled_at: datetime | None = None,
        section_ids: list[EntityId] | None = None,
    ) -> EntityId:
        now = self._clock.now()
        with self._uow as uow:
            exam = Exam.create(
                title=title,
                now=now,
                category_id=category_id,
                scheduled_at=scheduled_at,
                section_ids=section_ids,
            )
            uow.exams.add(exam)
            commit_and_publish(uow, self._bus, exam)
            return exam.id


class SetExamSyllabus:
    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(self, *, exam_id: EntityId, section_ids: list[EntityId]) -> None:
        now = self._clock.now()
        with self._uow as uow:
            exam = uow.exams.get(exam_id)
            require(exam, "El examen no existe")
            assert exam is not None
            exam.set_syllabus(section_ids, now)
            uow.exams.update(exam)
            commit_and_publish(uow, self._bus, exam)


class RecordExamResult:
    """Aprobar archiva el temario. Reprobar lo deja activo para el reintento."""

    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(
        self,
        *,
        exam_id: EntityId,
        passed: bool,
        score: float | None = None,
        passed_section_ids: list[EntityId] | None = None,
    ) -> tuple[EntityId, ...]:
        now = self._clock.now()
        with self._uow as uow:
            exam = uow.exams.get(exam_id)
            require(exam, "El examen no existe")
            assert exam is not None
            to_archive = exam.record_result(
                result=ExamResult.PASSED if passed else ExamResult.FAILED,
                now=now,
                score=score,
                passed_section_ids=passed_section_ids,
            )
            uow.exams.update(exam)

            sections = uow.sections.list_by_ids(to_archive)
            for section in sections:
                section.archive(now)
                uow.sections.update(section)

            # Un material queda archivado cuando todas sus secciones lo están.
            touched_materials = []
            for material_id in {s.material_id for s in sections}:
                siblings = uow.sections.list_by_material(material_id)
                if siblings and all(not s.is_active for s in siblings):
                    material = uow.materials.get(material_id)
                    if material is not None:
                        material.archive(now)
                        uow.materials.update(material)
                        touched_materials.append(material)

            commit_and_publish(uow, self._bus, exam, *sections, *touched_materials)
            return tuple(to_archive)


class CreateExamRetry:
    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow = uow
        self._bus = bus
        self._clock = clock

    def execute(
        self, *, exam_id: EntityId, scheduled_at: datetime | None = None
    ) -> EntityId:
        now = self._clock.now()
        with self._uow as uow:
            original = uow.exams.get(exam_id)
            require(original, "El examen no existe")
            assert original is not None
            retry = original.build_retry(now=now, scheduled_at=scheduled_at)
            uow.exams.add(retry)
            commit_and_publish(uow, self._bus, retry)
            return retry.id


class ListExams:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(
        self,
        *,
        category_id: EntityId | None = None,
        scheduled_from: datetime | None = None,
        scheduled_to: datetime | None = None,
        pending_only: bool = False,
    ) -> list[ExamRow]:
        with self._uow as uow:
            index = CategoryIndex(uow.categories.list_all())
            category_ids = index.with_descendants(category_id) if category_id else None
            exams = uow.exams.list_all(
                category_ids=category_ids,
                scheduled_from=scheduled_from,
                scheduled_to=scheduled_to,
                pending_only=pending_only,
            )
            return [exam_row(exam, index) for exam in exams]


class DeleteExam:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(self, *, exam_id: EntityId) -> None:
        with self._uow as uow:
            uow.exams.delete(exam_id)
            uow.commit()
