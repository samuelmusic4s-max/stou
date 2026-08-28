"""Unidad de trabajo sobre SQLite.

Reentrante: si un caso de uso ya abrió la transacción, el bloque interno se suma a
ella en lugar de abrir otra. El estado de anidamiento es por hilo, porque cada hilo
tiene su propia conexión.
"""

from __future__ import annotations

import threading
from types import TracebackType

from stou.infrastructure.persistence.database import Database
from stou.infrastructure.persistence.repositories import (
    SqliteCategoryRepository,
    SqliteExamRepository,
    SqliteMaterialRepository,
    SqliteSectionRepository,
    SqliteStudySessionRepository,
    SqliteTaskRepository,
)


class SqliteUnitOfWork:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._state = threading.local()
        self.categories = SqliteCategoryRepository(db)
        self.materials = SqliteMaterialRepository(db)
        self.sections = SqliteSectionRepository(db)
        self.tasks = SqliteTaskRepository(db)
        self.sessions = SqliteStudySessionRepository(db)
        self.exams = SqliteExamRepository(db)

    @property
    def _depth(self) -> int:
        return getattr(self._state, "depth", 0)

    @_depth.setter
    def _depth(self, value: int) -> None:
        self._state.depth = value

    @property
    def _pending_commit(self) -> bool:
        return getattr(self._state, "pending_commit", False)

    @_pending_commit.setter
    def _pending_commit(self, value: bool) -> None:
        self._state.pending_commit = value

    def __enter__(self) -> SqliteUnitOfWork:
        if self._depth == 0:
            self._pending_commit = False
            if not self._db.conn.in_transaction:
                self._db.conn.execute("BEGIN")
        self._depth += 1
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._depth -= 1
        if self._depth > 0:
            return
        self._depth = 0
        if self._db.conn.in_transaction:
            if exc is None and self._pending_commit:
                self._db.conn.execute("COMMIT")
            else:
                # Nadie pidió commit o algo falló: se descarta.
                self._db.conn.execute("ROLLBACK")
        self._pending_commit = False

    def commit(self) -> None:
        if self._depth > 1:
            # El commit real lo hace el bloque más externo, para no partir la
            # transacción por la mitad.
            self._pending_commit = True
            return
        self._pending_commit = True
        if self._db.conn.in_transaction:
            self._db.conn.execute("COMMIT")

    def rollback(self) -> None:
        self._pending_commit = False
        if self._db.conn.in_transaction:
            self._db.conn.execute("ROLLBACK")
