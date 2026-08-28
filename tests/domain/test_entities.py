"""Invariantes de tarea, categoría y sección."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from stou.domain.entities.category import Category
from stou.domain.entities.section import Section
from stou.domain.entities.task import Task
from stou.domain.values import Locator, LocatorUnit, TaskStatus
from stou.shared.ids import EntityId

NOW = datetime(2026, 3, 2, 10, 0, tzinfo=UTC)
MATERIAL = EntityId("m1")


def test_la_tarea_exige_titulo() -> None:
    with pytest.raises(ValueError):
        Task.create(title="   ", now=NOW)


def test_no_se_asigna_dos_veces_el_mismo_material() -> None:
    task = Task.create(title="Leer", now=NOW)
    task.assign(material_id=MATERIAL, now=NOW)
    with pytest.raises(ValueError):
        task.assign(material_id=MATERIAL, now=NOW)


def test_asignar_la_misma_seccion_a_otra_tarea_si_es_posible() -> None:
    section = EntityId("s1")
    first = Task.create(title="Leer", now=NOW)
    second = Task.create(title="Repasar", now=NOW)
    first.assign(material_id=MATERIAL, section_id=section, now=NOW)
    second.assign(material_id=MATERIAL, section_id=section, now=NOW)
    assert len(first.items) == len(second.items) == 1


def test_reordenar_exige_el_mismo_conjunto() -> None:
    task = Task.create(title="Leer", now=NOW)
    a = task.assign(material_id=MATERIAL, section_id=EntityId("s1"), now=NOW)
    task.assign(material_id=MATERIAL, section_id=EntityId("s2"), now=NOW)
    with pytest.raises(ValueError):
        task.reorder([a.id], NOW)


def test_completar_registra_fecha_y_evento() -> None:
    task = Task.create(title="Leer", now=NOW)
    task.pull_events()
    task.complete(NOW)
    assert task.status is TaskStatus.DONE
    assert task.completed_at == NOW
    assert {e.event_name for e in task.pull_events()} == {"TaskStatusChanged", "TaskCompleted"}


def test_fecha_limite_no_puede_ser_anterior_al_inicio() -> None:
    later = NOW.replace(hour=12)
    with pytest.raises(ValueError):
        Task.create(title="Leer", now=NOW, start_at=later, due_at=NOW)


def test_categoria_no_puede_ser_su_propia_madre() -> None:
    category = Category.create(name="Matemáticas", now=NOW)
    with pytest.raises(ValueError):
        category.move_to(category.id, NOW)


def test_seccion_valida_su_intervalo() -> None:
    with pytest.raises(ValueError):
        Locator(unit=LocatorUnit.PAGE, start=10, end=4)


def test_marcar_estudiada_es_idempotente() -> None:
    section = Section.create(
        material_id=MATERIAL,
        title="Cap 1",
        locator=Locator(unit=LocatorUnit.PAGE, start=1, end=10),
        now=NOW,
    )
    section.mark_studied(NOW)
    section.mark_studied(NOW.replace(hour=12))
    assert section.studied_at == NOW
    assert len([e for e in section.pull_events() if e.event_name == "SectionStudied"]) == 1
