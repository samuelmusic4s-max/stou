"""Conexión SQLite y aplicación de migraciones.

Una conexión por hilo: los workers de la GUI no pueden compartir la del hilo
principal. WAL para que leer no bloquee escribir.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from stou.infrastructure.persistence.schema import MIGRATIONS


class Database:
    def __init__(self, path: Path | str) -> None:
        self._path = str(path)
        self._local = threading.local()
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._shared: sqlite3.Connection | None = None
        if self._path == ":memory:":
            # En memoria toda conexión nueva sería una base distinta: se comparte una.
            self._shared = self._build_connection()
        self.migrate()

    # --- conexión -------------------------------------------------------------

    @property
    def conn(self) -> sqlite3.Connection:
        if self._shared is not None:
            return self._shared
        existing = getattr(self._local, "conn", None)
        if existing is None:
            existing = self._build_connection()
            self._local.conn = existing
        return existing

    def _build_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self._path,
            isolation_level=None,  # el control de transacción es explícito
            check_same_thread=False,
            timeout=10.0,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    def close(self) -> None:
        existing = getattr(self._local, "conn", None)
        if existing is not None:
            existing.close()
            self._local.conn = None
        if self._shared is not None:
            self._shared.close()
            self._shared = None

    # --- migraciones ----------------------------------------------------------

    def migrate(self) -> int:
        conn = self.conn
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
        count = 0
        for version, sql in MIGRATIONS:
            if version in applied:
                continue
            # executescript hace commit implícito, así que la transacción va dentro
            # del propio script para que la migración sea atómica.
            stamp = datetime.now(UTC).isoformat()
            script = (
                "BEGIN;\n"
                f"{sql}\n"
                "INSERT INTO schema_migrations (version, applied_at) VALUES "
                f"({int(version)}, '{stamp}');\n"
                "COMMIT;"
            )
            try:
                conn.executescript(script)
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
            count += 1
        return count

    @property
    def version(self) -> int:
        row = self.conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return int(row[0] or 0)
