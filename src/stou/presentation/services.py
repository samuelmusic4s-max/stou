"""Lo que la presentación recibe del composition root.

Es la frontera: las vistas conocen casos de uso, no repositorios ni bases de datos.
"""

from __future__ import annotations

from dataclasses import dataclass

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
from stou.presentation.qt.events import UiEvents


@dataclass(frozen=True)
class AppServices:
    events: UiEvents

    # categorías
    category_tree: GetCategoryTree
    create_category: CreateCategory
    rename_category: RenameCategory
    move_category: MoveCategory
    delete_category: DeleteCategory

    # material
    import_files: ImportMaterialFiles
    add_link: AddLinkMaterial
    create_note: CreateNote
    update_material: UpdateMaterial
    set_material_state: SetMaterialState
    delete_material: DeleteMaterial
    list_materials: ListMaterials
    resolve_source: ResolveMaterialSource
    prepare_epub: PrepareEpubReading
    save_position: SaveReadingPosition
    split_material: SplitMaterialEvenly

    # secciones
    list_sections: ListSections
    create_section: CreateSection
    update_section: UpdateSection
    delete_section: DeleteSection
    mark_studied: MarkSectionStudied

    # tareas
    create_task: CreateTask
    update_task: UpdateTask
    reschedule_task: RescheduleTask
    change_task_status: ChangeTaskStatus
    delete_task: DeleteTask
    list_tasks: ListTasks
    task_detail: GetTaskDetail
    assign_material: AssignMaterialToTask
    unassign_item: UnassignTaskItem
    reorder_items: ReorderTaskItems
    suggest_sections: SuggestSections

    # estudio
    start_session: StartStudySession
    tick_session: TickStudySession
    close_session: CloseStudySession
    add_manual_session: AddManualSession
    adjust_session: AdjustSession
    delete_session: DeleteSession
    list_sessions: ListSessions

    # exámenes
    create_exam: CreateExam
    set_syllabus: SetExamSyllabus
    record_exam: RecordExamResult
    exam_retry: CreateExamRetry
    list_exams: ListExams
    delete_exam: DeleteExam

    # vistas agregadas
    home: GetHomeOverview
    dashboard: GetDashboard
    calendar_month: GetCalendarMonth
