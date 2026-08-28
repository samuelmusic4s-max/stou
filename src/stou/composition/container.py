"""Composition root: el único lugar donde se conocen todas las capas."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from stou.application.use_cases.calendar import GetCalendarMonth
from stou.application.use_cases.categories import (
    CreateCategory,
    DeleteCategory,
    GetCategoryTree,
    MoveCategory,
    RenameCategory,
)
from stou.application.use_cases.dashboard import GetDashboard
from stou.application.use_cases.exams import (
    CreateExam,
    CreateExamRetry,
    DeleteExam,
    ListExams,
    RecordExamResult,
    SetExamSyllabus,
)
from stou.application.use_cases.home import GetHomeOverview
from stou.application.use_cases.materials import (
    AddLinkMaterial,
    CreateNote,
    DeleteMaterial,
    ImportMaterialFiles,
    ListMaterials,
    PrepareEpubReading,
    ResolveMaterialSource,
    SaveReadingPosition,
    SetMaterialState,
    SplitMaterialEvenly,
    UpdateMaterial,
)
from stou.application.use_cases.sections import (
    CreateSection,
    DeleteSection,
    ListSections,
    MarkSectionStudied,
    UpdateSection,
)
from stou.application.use_cases.study import (
    AddManualSession,
    AdjustSession,
    CloseAbandonedSessions,
    CloseStudySession,
    DeleteSession,
    ListSessions,
    StartStudySession,
    TickStudySession,
)
from stou.application.use_cases.tasks import (
    AssignMaterialToTask,
    ChangeTaskStatus,
    CreateTask,
    DeleteTask,
    GetTaskDetail,
    ListTasks,
    ReorderTaskItems,
    RescheduleTask,
    SuggestSections,
    UnassignTaskItem,
    UpdateTask,
)
from stou.infrastructure.content.epub import EpubExtractor
from stou.infrastructure.content.inspector import FileInspector
from stou.infrastructure.events.in_memory_bus import InMemoryEventBus
from stou.infrastructure.persistence.database import Database
from stou.infrastructure.persistence.unit_of_work import SqliteUnitOfWork
from stou.infrastructure.storage.blob_store import BlobStore
from stou.shared.clock import SystemClock

APP_DIR_NAME = "stou"


def default_data_dir() -> Path:
    override = os.environ.get("STOU_DATA_DIR")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_DATA_HOME")
    root = Path(base).expanduser() if base else Path.home() / ".local" / "share"
    return root / APP_DIR_NAME


@dataclass
class Container:
    """Contiene la infraestructura viva y sabe construir los casos de uso."""

    data_dir: Path
    database: Database
    bus: InMemoryEventBus
    uow: SqliteUnitOfWork
    storage: BlobStore
    inspector: FileInspector
    epub: EpubExtractor
    clock: SystemClock

    @classmethod
    def create(cls, data_dir: Path | None = None, clock: object | None = None) -> Container:
        root = Path(data_dir) if data_dir else default_data_dir()
        root.mkdir(parents=True, exist_ok=True)
        database = Database(root / "stou.db")
        return cls(
            data_dir=root,
            database=database,
            bus=InMemoryEventBus(),
            uow=SqliteUnitOfWork(database),
            storage=BlobStore(root / "library"),
            inspector=FileInspector(),
            epub=EpubExtractor(root / "cache" / "epub"),
            clock=clock or SystemClock(),  # type: ignore[arg-type]
        )

    def close(self) -> None:
        self.database.close()

    # --- casos de uso ---------------------------------------------------------

    def build_use_cases(self) -> dict[str, object]:
        uow, bus, clock = self.uow, self.bus, self.clock
        return {
            "category_tree": GetCategoryTree(uow),
            "create_category": CreateCategory(uow, bus, clock),
            "rename_category": RenameCategory(uow, bus, clock),
            "move_category": MoveCategory(uow, bus, clock),
            "delete_category": DeleteCategory(uow, bus, clock),
            "import_files": ImportMaterialFiles(uow, bus, clock, self.storage, self.inspector),
            "add_link": AddLinkMaterial(uow, bus, clock),
            "create_note": CreateNote(uow, bus, clock),
            "update_material": UpdateMaterial(uow, bus, clock),
            "set_material_state": SetMaterialState(uow, bus, clock),
            "delete_material": DeleteMaterial(uow, bus, clock, self.storage),
            "list_materials": ListMaterials(uow),
            "resolve_source": ResolveMaterialSource(uow, self.storage),
            "prepare_epub": PrepareEpubReading(uow, self.storage, self.epub),
            "save_position": SaveReadingPosition(uow, bus, clock),
            "split_material": SplitMaterialEvenly(uow, bus, clock),
            "list_sections": ListSections(uow),
            "create_section": CreateSection(uow, bus, clock),
            "update_section": UpdateSection(uow, bus, clock),
            "delete_section": DeleteSection(uow, clock),
            "mark_studied": MarkSectionStudied(uow, bus, clock),
            "create_task": CreateTask(uow, bus, clock),
            "update_task": UpdateTask(uow, bus, clock),
            "reschedule_task": RescheduleTask(uow, bus, clock),
            "change_task_status": ChangeTaskStatus(uow, bus, clock),
            "delete_task": DeleteTask(uow, bus, clock),
            "list_tasks": ListTasks(uow, clock),
            "task_detail": GetTaskDetail(uow, clock),
            "assign_material": AssignMaterialToTask(uow, bus, clock),
            "unassign_item": UnassignTaskItem(uow, bus, clock),
            "reorder_items": ReorderTaskItems(uow, bus, clock),
            "suggest_sections": SuggestSections(uow),
            "start_session": StartStudySession(uow, bus, clock),
            "tick_session": TickStudySession(uow, bus, clock),
            "close_session": CloseStudySession(uow, bus, clock),
            "add_manual_session": AddManualSession(uow, bus, clock),
            "adjust_session": AdjustSession(uow, bus, clock),
            "delete_session": DeleteSession(uow),
            "list_sessions": ListSessions(uow),
            "create_exam": CreateExam(uow, bus, clock),
            "set_syllabus": SetExamSyllabus(uow, bus, clock),
            "record_exam": RecordExamResult(uow, bus, clock),
            "exam_retry": CreateExamRetry(uow, bus, clock),
            "list_exams": ListExams(uow),
            "delete_exam": DeleteExam(uow),
            "home": GetHomeOverview(uow, clock),
            "dashboard": GetDashboard(uow, clock),
            "calendar_month": GetCalendarMonth(uow, clock),
        }

    def close_abandoned_sessions(self) -> int:
        return CloseAbandonedSessions(self.uow, self.bus, self.clock).execute()
