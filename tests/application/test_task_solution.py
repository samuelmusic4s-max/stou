"""La solución de una tarea.

Una tarea puede llevar, además de su enunciado, el material con la respuesta. Lo que
se prueba aquí es que las dos cosas no se confundan: ni en el progreso, ni en lo que
el modo estudio abre por su cuenta.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from stou.domain.entities.task import Task
from stou.domain.values import ItemRole
from stou.shared.ids import new_id

NOW = datetime(2026, 3, 2, 14, 0, tzinfo=UTC)


def test_la_solucion_se_guarda_aparte_del_enunciado() -> None:
    task = Task.create(title="Integrales por partes", now=NOW)
    material = new_id()
    solucion = new_id()

    task.assign(material_id=material, now=NOW)
    task.assign(material_id=solucion, now=NOW, role=ItemRole.SOLUTION)

    assert len(task.items) == 2
    assert [item.material_id for item in task.material_items] == [material]
    assert [item.material_id for item in task.solution_items] == [solucion]
    assert task.solution_items[0].is_solution


def test_el_mismo_material_puede_ser_enunciado_y_solucion() -> None:
    """Un libro con los ejercicios y las respuestas al final es un caso real."""
    task = Task.create(title="Serie de ejercicios", now=NOW)
    material = new_id()

    task.assign(material_id=material, now=NOW)
    task.assign(material_id=material, now=NOW, role=ItemRole.SOLUTION)

    assert len(task.items) == 2


def test_no_se_asigna_dos_veces_la_misma_solucion() -> None:
    task = Task.create(title="Serie de ejercicios", now=NOW)
    solucion = new_id()
    task.assign(material_id=solucion, now=NOW, role=ItemRole.SOLUTION)

    with pytest.raises(ValueError, match="solución ya está asignada"):
        task.assign(material_id=solucion, now=NOW, role=ItemRole.SOLUTION)


def test_la_solucion_no_cuenta_para_el_progreso(use_cases: dict, sample_pdf: Path) -> None:
    """Si la solución contara como material por estudiar, la tarea nunca acabaría."""
    category = use_cases["create_category"].execute(name="Cálculo")
    use_cases["import_files"].execute(paths=[sample_pdf], category_id=category)
    sections = use_cases["suggest_sections"].execute(category_id=category)
    assert len(sections) >= 2

    task_id = use_cases["create_task"].execute(
        title="Practicar", category_id=category, section_ids=[sections[0].id]
    )
    use_cases["assign_material"].execute(
        task_id=task_id, section_ids=[sections[1].id], role=ItemRole.SOLUTION
    )

    detail = use_cases["task_detail"].execute(task_id=task_id)
    assert len(detail.items) == 2
    assert len(detail.material) == 1
    assert len(detail.solutions) == 1
    # El contador de la tarea solo mira el enunciado.
    assert detail.task.item_count == 1

    use_cases["mark_studied"].execute(section_id=sections[0].id, studied=True)
    detail = use_cases["task_detail"].execute(task_id=task_id)
    assert detail.task.studied_items == detail.task.item_count == 1


def test_la_solucion_sobrevive_a_guardar_y_volver_a_leer(
    use_cases: dict, sample_pdf: Path
) -> None:
    """El rol viaja hasta SQLite: sin la columna, al reabrir se perdería la distinción."""
    category = use_cases["create_category"].execute(name="Física")
    use_cases["import_files"].execute(paths=[sample_pdf], category_id=category)
    sections = use_cases["suggest_sections"].execute(category_id=category)

    task_id = use_cases["create_task"].execute(title="Taller", category_id=category)
    use_cases["assign_material"].execute(task_id=task_id, section_ids=[sections[0].id])
    use_cases["assign_material"].execute(
        task_id=task_id, section_ids=[sections[1].id], role=ItemRole.SOLUTION
    )

    detail = use_cases["task_detail"].execute(task_id=task_id)
    roles = {item.role for item in detail.items}
    assert roles == {ItemRole.MATERIAL, ItemRole.SOLUTION}
