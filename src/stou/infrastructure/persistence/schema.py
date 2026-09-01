"""Esquema y migraciones.

Regla: solo se agregan migraciones al final. Nunca se edita una ya publicada.
"""

from __future__ import annotations

MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE categories (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            parent_id   TEXT REFERENCES categories(id) ON DELETE SET NULL,
            color       TEXT NOT NULL DEFAULT '#5B8DEF',
            position    INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );
        CREATE INDEX idx_categories_parent ON categories(parent_id);

        CREATE TABLE materials (
            id                TEXT PRIMARY KEY,
            kind              TEXT NOT NULL,
            title             TEXT NOT NULL,
            category_id       TEXT REFERENCES categories(id) ON DELETE SET NULL,
            state             TEXT NOT NULL DEFAULT 'active',
            blob_hash         TEXT,
            blob_ext          TEXT NOT NULL DEFAULT '',
            size_bytes        INTEGER NOT NULL DEFAULT 0,
            url               TEXT,
            body              TEXT,
            source            TEXT,
            page_count        INTEGER,
            duration_seconds  REAL,
            reading_position  REAL NOT NULL DEFAULT 0,
            tags              TEXT NOT NULL DEFAULT '',
            text_indexed      INTEGER NOT NULL DEFAULT 0,
            created_at        TEXT NOT NULL,
            updated_at        TEXT NOT NULL
        );
        CREATE INDEX idx_materials_category ON materials(category_id);
        CREATE INDEX idx_materials_state ON materials(state);
        CREATE UNIQUE INDEX idx_materials_blob ON materials(blob_hash)
            WHERE blob_hash IS NOT NULL;

        CREATE TABLE sections (
            id           TEXT PRIMARY KEY,
            material_id  TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
            parent_id    TEXT REFERENCES sections(id) ON DELETE SET NULL,
            title        TEXT NOT NULL,
            unit         TEXT NOT NULL,
            range_start  REAL NOT NULL DEFAULT 0,
            range_end    REAL,
            position     INTEGER NOT NULL DEFAULT 0,
            state        TEXT NOT NULL DEFAULT 'active',
            studied_at   TEXT,
            notes        TEXT,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL
        );
        CREATE INDEX idx_sections_material ON sections(material_id, position);
        CREATE INDEX idx_sections_state ON sections(state);

        CREATE TABLE tasks (
            id                TEXT PRIMARY KEY,
            title             TEXT NOT NULL,
            description       TEXT NOT NULL DEFAULT '',
            category_id       TEXT REFERENCES categories(id) ON DELETE SET NULL,
            parent_id         TEXT REFERENCES tasks(id) ON DELETE CASCADE,
            status            TEXT NOT NULL DEFAULT 'pending',
            priority          TEXT NOT NULL DEFAULT 'normal',
            start_at          TEXT,
            due_at            TEXT,
            estimated_minutes INTEGER,
            completed_at      TEXT,
            position          INTEGER NOT NULL DEFAULT 0,
            created_at        TEXT NOT NULL,
            updated_at        TEXT NOT NULL
        );
        CREATE INDEX idx_tasks_category ON tasks(category_id);
        CREATE INDEX idx_tasks_status ON tasks(status);
        CREATE INDEX idx_tasks_due ON tasks(due_at);

        CREATE TABLE task_items (
            id          TEXT PRIMARY KEY,
            task_id     TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            material_id TEXT NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
            section_id  TEXT REFERENCES sections(id) ON DELETE CASCADE,
            position    INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX idx_task_items_task ON task_items(task_id, position);
        CREATE INDEX idx_task_items_section ON task_items(section_id);

        CREATE TABLE study_sessions (
            id                  TEXT PRIMARY KEY,
            task_id             TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            category_id         TEXT,
            started_at          TEXT NOT NULL,
            ended_at            TEXT,
            last_activity_at    TEXT NOT NULL,
            last_tick_at        TEXT NOT NULL,
            accumulated_seconds REAL NOT NULL DEFAULT 0,
            paused              INTEGER NOT NULL DEFAULT 0,
            material_id         TEXT,
            manual              INTEGER NOT NULL DEFAULT 0,
            created_at          TEXT NOT NULL,
            updated_at          TEXT NOT NULL
        );
        CREATE INDEX idx_sessions_task ON study_sessions(task_id);
        CREATE INDEX idx_sessions_started ON study_sessions(started_at);
        CREATE INDEX idx_sessions_open ON study_sessions(ended_at);

        CREATE TABLE exams (
            id           TEXT PRIMARY KEY,
            title        TEXT NOT NULL,
            category_id  TEXT REFERENCES categories(id) ON DELETE SET NULL,
            scheduled_at TEXT,
            result       TEXT NOT NULL DEFAULT 'pending',
            score        REAL,
            notes        TEXT NOT NULL DEFAULT '',
            recorded_at  TEXT,
            retry_of     TEXT REFERENCES exams(id) ON DELETE SET NULL,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL
        );
        CREATE INDEX idx_exams_scheduled ON exams(scheduled_at);

        CREATE TABLE exam_sections (
            exam_id    TEXT NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
            section_id TEXT NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
            position   INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (exam_id, section_id)
        );

        CREATE VIRTUAL TABLE material_text USING fts5(
            content,
            material_id UNINDEXED,
            position UNINDEXED,
            tokenize = 'unicode61 remove_diacritics 2'
        );
        """,
    ),
    (
        2,
        """
        -- Una tarea puede llevar también su solución: el mismo material asignado con
        -- otro papel. Se separa por columna y no por tabla porque comparte todo lo
        -- demás (orden, sección, material).
        ALTER TABLE task_items ADD COLUMN role TEXT NOT NULL DEFAULT 'material';
        CREATE INDEX idx_task_items_role ON task_items(task_id, role);
        """,
    ),
]
