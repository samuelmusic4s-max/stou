"""Andamiaje para probar la interfaz.

Los diálogos modales son el enemigo de un test: `exec()` bloquea para siempre. Aquí
se sustituyen por respuestas programadas, de modo que un test pueda recorrer un flujo
completo («pulsa Nueva tarea, escribe un título, acepta») sin intervención humana.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QDialog,
    QFileDialog,
    QInputDialog,
    QMessageBox,
)

from stou.composition.container import Container  # noqa: E402
from stou.domain.values import Priority  # noqa: E402
from stou.presentation.qt.events import UiEvents  # noqa: E402
from stou.presentation.qt.main_window import MainWindow  # noqa: E402
from stou.presentation.qt.theme import apply_theme  # noqa: E402
from stou.presentation.services import AppServices  # noqa: E402
from stou.presentation.views import (  # noqa: E402
    calendar_view,
    library_view,
    study_view,  # noqa: E402
    tasks_view,
)
from stou.presentation.widgets import dialogs as dialogs_module  # noqa: E402

ACCEPTED = QDialog.DialogCode.Accepted
REJECTED = QDialog.DialogCode.Rejected


@dataclass
class TaskFormAnswer:
    title: str = "Tarea de prueba"
    description: str = ""
    category_id: str | None = None
    priority: Priority = Priority.NORMAL
    due_at: datetime | None = None
    estimated_minutes: int | None = None


@dataclass
class Script:
    """Respuestas programadas para los diálogos, y registro de lo que se mostró."""

    # Qué debe responder cada diálogo.
    accept_dialogs: bool = True
    task_form: TaskFormAnswer = field(default_factory=TaskFormAnswer)
    text_answers: list[str] = field(default_factory=list)
    int_answer: int = 4
    double_answers: list[float] = field(default_factory=list)
    files: list[Path] = field(default_factory=list)
    sections_to_pick: int | None = None  # cuántas secciones marcar; None = todas
    exam_passed: bool = True
    exam_score: float | None = 4.0
    manual_minutes: int = 30
    link_url: str = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    link_title: str | None = "Video de prueba"
    question_answer: QMessageBox.StandardButton = QMessageBox.StandardButton.Yes

    # Qué vio el usuario.
    messages: list[tuple[str, str, str]] = field(default_factory=list)

    def next_text(self) -> str:
        return self.text_answers.pop(0) if self.text_answers else "Sin nombre"

    def next_double(self) -> float:
        return self.double_answers.pop(0) if self.double_answers else 1.0

    # --- consultas para los asserts ---------------------------------------

    def titles(self) -> list[str]:
        return [title for _kind, title, _body in self.messages]

    def bodies(self) -> list[str]:
        return [body for _kind, _title, body in self.messages]

    def said(self, needle: str) -> bool:
        needle = needle.lower()
        return any(needle in f"{title} {body}".lower() for _k, title, body in self.messages)

    def clear(self) -> None:
        self.messages.clear()


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    return app


@pytest.fixture
def script(monkeypatch: pytest.MonkeyPatch, qapp: QApplication) -> Script:
    plan = Script()

    # --- avisos ---------------------------------------------------------------
    def record(kind: str):  # noqa: ANN202
        def handler(_parent, title, text, *args, **kwargs):  # noqa: ANN001, ANN202
            plan.messages.append((kind, str(title), str(text)))
            if kind == "question":
                return plan.question_answer
            return QMessageBox.StandardButton.Ok

        return handler

    for name in ("information", "warning", "critical", "about"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(record(name)))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(record("question")))

    # --- diálogos simples de Qt ----------------------------------------------
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        staticmethod(lambda *a, **k: (plan.next_text(), plan.accept_dialogs)),
    )
    monkeypatch.setattr(
        QInputDialog,
        "getInt",
        staticmethod(lambda *a, **k: (plan.int_answer, plan.accept_dialogs)),
    )
    monkeypatch.setattr(
        QInputDialog,
        "getDouble",
        staticmethod(lambda *a, **k: (plan.next_double(), plan.accept_dialogs)),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileNames",
        staticmethod(lambda *a, **k: ([str(p) for p in plan.files], "")),
    )

    # --- diálogos propios -----------------------------------------------------
    def result() -> QDialog.DialogCode:
        return ACCEPTED if plan.accept_dialogs else REJECTED

    monkeypatch.setattr(dialogs_module.TaskDialog, "exec", lambda self: result())
    monkeypatch.setattr(
        dialogs_module.TaskDialog,
        "data",
        lambda self: dialogs_module.TaskFormData(
            title=plan.task_form.title,
            description=plan.task_form.description,
            category_id=plan.task_form.category_id,
            priority=plan.task_form.priority,
            due_at=plan.task_form.due_at,
            estimated_minutes=plan.task_form.estimated_minutes,
        ),
    )

    def pick_sections(self) -> list[str]:  # noqa: ANN001
        available = [row.id for row in self._all]  # noqa: SLF001
        if plan.sections_to_pick is None:
            return available
        return available[: plan.sections_to_pick]

    monkeypatch.setattr(dialogs_module.AssignSectionsDialog, "exec", lambda self: result())
    monkeypatch.setattr(dialogs_module.AssignSectionsDialog, "selected_ids", pick_sections)

    monkeypatch.setattr(dialogs_module.ExamDialog, "exec", lambda self: result())
    monkeypatch.setattr(dialogs_module.ExamDialog, "title", lambda self: "Parcial de prueba")
    monkeypatch.setattr(
        dialogs_module.ExamDialog,
        "section_ids",
        lambda self: pick_sections(self._sections),  # noqa: SLF001
    )

    monkeypatch.setattr(dialogs_module.RecordExamDialog, "exec", lambda self: result())
    monkeypatch.setattr(dialogs_module.RecordExamDialog, "passed", lambda self: plan.exam_passed)
    monkeypatch.setattr(dialogs_module.RecordExamDialog, "score", lambda self: plan.exam_score)

    monkeypatch.setattr(dialogs_module.ManualSessionDialog, "exec", lambda self: result())
    monkeypatch.setattr(
        dialogs_module.ManualSessionDialog, "minutes", lambda self: plan.manual_minutes
    )

    monkeypatch.setattr(dialogs_module.LinkDialog, "exec", lambda self: result())
    monkeypatch.setattr(dialogs_module.LinkDialog, "url", lambda self: plan.link_url)
    monkeypatch.setattr(dialogs_module.LinkDialog, "title", lambda self: plan.link_title)

    # Los módulos importan las clases por nombre: hay que apuntar a las mismas.
    for module in (tasks_view, calendar_view, library_view, study_view):
        for attribute in (
            "TaskDialog",
            "AssignSectionsDialog",
            "ExamDialog",
            "RecordExamDialog",
            "ManualSessionDialog",
            "LinkDialog",
        ):
            if hasattr(module, attribute):
                monkeypatch.setattr(module, attribute, getattr(dialogs_module, attribute))

    return plan


@pytest.fixture
def services(container: Container, qapp: QApplication) -> AppServices:
    return AppServices(events=UiEvents(container.bus), **container.build_use_cases())


@pytest.fixture
def window(services: AppServices, qapp: QApplication, script: Script) -> MainWindow:
    main = MainWindow(services)
    main.show()
    qapp.processEvents()
    yield main
    for extra in list(main._windows):  # noqa: SLF001
        extra.close()
    main.close()
    qapp.processEvents()


@pytest.fixture
def pump(qapp: QApplication):  # noqa: ANN201
    """Deja que Qt entregue las señales pendientes (los eventos llegan por señal)."""

    def run(times: int = 3) -> None:
        for _ in range(times):
            qapp.processEvents()

    return run
