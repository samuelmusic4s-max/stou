"""Unidad de trabajo: una transacción con acceso a todos los repositorios."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol

from stou.domain.ports.repositories import (
    CategoryRepository,
    ExamRepository,
    MaterialRepository,
    SectionRepository,
    StudySessionRepository,
    TaskRepository,
)


class UnitOfWork(Protocol):
    categories: CategoryRepository
    materials: MaterialRepository
    sections: SectionRepository
    tasks: TaskRepository
    sessions: StudySessionRepository
    exams: ExamRepository

    def __enter__(self) -> UnitOfWork: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
