"""DTOs: lo único que la presentación recibe. Nunca entidades de dominio."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from stou.domain.values import ExamResult, ItemRole, MaterialKind, Priority, TaskStatus
from stou.shared.ids import EntityId


@dataclass(frozen=True, slots=True)
class CategoryNode:
    id: EntityId
    name: str
    color: str
    parent_id: EntityId | None
    children: tuple[CategoryNode, ...] = ()

    def flatten(self) -> list[CategoryNode]:
        out = [self]
        for child in self.children:
            out.extend(child.flatten())
        return out


@dataclass(frozen=True, slots=True)
class MaterialRow:
    id: EntityId
    title: str
    kind: MaterialKind
    category_id: EntityId | None
    category_path: str
    archived: bool
    section_count: int
    studied_sections: int
    size_bytes: int
    url: str | None
    has_blob: bool


@dataclass(frozen=True, slots=True)
class SectionRow:
    id: EntityId
    material_id: EntityId
    material_title: str
    material_kind: MaterialKind
    title: str
    range_label: str
    start: float
    end: float | None
    studied: bool
    archived: bool
    level: int


@dataclass(frozen=True, slots=True)
class TaskItemRow:
    item_id: EntityId
    material_id: EntityId
    section_id: EntityId | None
    title: str
    kind: MaterialKind
    range_label: str
    studied: bool
    position: int
    role: ItemRole = ItemRole.MATERIAL

    @property
    def is_solution(self) -> bool:
        return self.role is ItemRole.SOLUTION


@dataclass(frozen=True, slots=True)
class TaskRow:
    id: EntityId
    title: str
    status: TaskStatus
    priority: Priority
    category_id: EntityId | None
    category_path: str
    due_at: datetime | None
    start_at: datetime | None
    estimated_minutes: int | None
    item_count: int
    studied_items: int
    spent_seconds: int
    overdue: bool


@dataclass(frozen=True, slots=True)
class TaskDetail:
    task: TaskRow
    description: str
    items: tuple[TaskItemRow, ...]

    @property
    def material(self) -> tuple[TaskItemRow, ...]:
        return tuple(item for item in self.items if not item.is_solution)

    @property
    def solutions(self) -> tuple[TaskItemRow, ...]:
        return tuple(item for item in self.items if item.is_solution)


@dataclass(frozen=True, slots=True)
class ExamRow:
    id: EntityId
    title: str
    category_id: EntityId | None
    category_path: str
    scheduled_at: datetime | None
    result: ExamResult
    score: float | None
    section_count: int


@dataclass(frozen=True, slots=True)
class SessionRow:
    id: EntityId
    task_id: EntityId
    task_title: str
    category_path: str
    started_at: datetime
    ended_at: datetime | None
    effective_seconds: int
    manual: bool


# --- Dashboard ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CategoryTime:
    category_id: EntityId | None
    category_path: str
    color: str
    seconds: int


@dataclass(frozen=True, slots=True)
class DayTime:
    day: date
    seconds: int


@dataclass(frozen=True, slots=True)
class CategoryProgress:
    category_id: EntityId
    category_path: str
    total_sections: int
    studied_sections: int
    archived_sections: int


@dataclass(frozen=True, slots=True)
class DashboardData:
    period_label: str
    total_seconds: int
    by_category: tuple[CategoryTime, ...]
    by_day: tuple[DayTime, ...]
    completed_tasks: int
    open_tasks: int
    overdue: tuple[TaskRow, ...]
    upcoming_tasks: tuple[TaskRow, ...]
    upcoming_exams: tuple[ExamRow, ...]
    week_plan: tuple[TaskRow, ...]
    streak_days: int
    progress: tuple[CategoryProgress, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class CalendarEntry:
    day: date
    task: TaskRow | None = None
    exam: ExamRow | None = None


# --- Pantalla de inicio -------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HomeOverview:
    """Lo que STOU necesita saber para decirle al usuario qué hacer ahora.

    ``onboarding_step`` es 0 cuando el sistema ya tiene categoría, material y
    tarea; si no, indica el paso pendiente (1, 2 o 3). La pantalla de inicio usa
    ese número para mostrar una sola instrucción a la vez.
    """

    onboarding_step: int
    has_categories: bool
    has_material: bool
    has_tasks: bool

    next_task: TaskRow | None
    in_progress: bool
    recent_tasks: tuple[TaskRow, ...]
    # Todo lo abierto, ordenado por urgencia: es la lista que gobierna la pantalla.
    pending_tasks: tuple[TaskRow, ...]

    today_seconds: int
    week_seconds: int
    streak_days: int

    open_tasks: int
    overdue_tasks: int
    material_count: int
    unstudied_sections: int

    next_exam: ExamRow | None
    days_to_exam: int | None

    # Actividad reciente para el gráfico y el desglose por materia.
    recent_days: tuple[DayTime, ...] = ()
    recent_by_category: tuple[CategoryTime, ...] = ()
    progress: tuple[CategoryProgress, ...] = ()
    recent_window_days: int = 0
    recent_total_seconds: int = 0

    @property
    def is_first_run(self) -> bool:
        return self.onboarding_step != 0
