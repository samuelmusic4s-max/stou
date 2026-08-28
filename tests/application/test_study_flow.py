"""Recorrido completo: importar un libro, seccionarlo, estudiarlo y examinarlo."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from stou.application import periods
from stou.composition.container import Container
from stou.domain.values import MaterialKind, TaskStatus
from stou.shared.clock import FixedClock


def test_importar_pdf_crea_secciones_desde_los_marcadores(
    use_cases: dict, sample_pdf: Path
) -> None:
    outcome = use_cases["import_files"].execute(paths=[sample_pdf])
    assert len(outcome.imported) == 1

    material_id = outcome.imported[0]
    sections = use_cases["list_sections"].execute(material_id=material_id)
    assert [s.title for s in sections] == ["Capítulo 1", "Capítulo 2", "Capítulo 3"]
    # El primer capítulo termina donde empieza el segundo.
    assert (sections[0].start, sections[0].end) == (1.0, 4.0)
    assert sections[2].end == 12.0


def test_importar_el_mismo_archivo_dos_veces_no_duplica(
    use_cases: dict, sample_pdf: Path
) -> None:
    use_cases["import_files"].execute(paths=[sample_pdf])
    second = use_cases["import_files"].execute(paths=[sample_pdf])
    assert second.imported == ()
    assert second.duplicates == (sample_pdf.name,)


def test_dividir_en_partes_iguales(use_cases: dict, sample_pdf: Path) -> None:
    material_id = use_cases["import_files"].execute(paths=[sample_pdf]).imported[0]
    ids = use_cases["split_material"].execute(material_id=material_id, parts=4)
    sections = use_cases["list_sections"].execute(material_id=material_id)
    assert len(ids) == 4
    assert [(s.start, s.end) for s in sections] == [
        (1.0, 3.0),
        (4.0, 6.0),
        (7.0, 9.0),
        (10.0, 12.0),
    ]


def test_flujo_de_estudio_registra_tiempo_por_categoria(
    container: Container, use_cases: dict, clock: FixedClock, sample_pdf: Path
) -> None:
    mate = use_cases["create_category"].execute(name="Matemáticas")
    calculo = use_cases["create_category"].execute(name="Cálculo I", parent_id=mate)

    material_id = use_cases["import_files"].execute(
        paths=[sample_pdf], category_id=calculo
    ).imported[0]
    sections = use_cases["list_sections"].execute(material_id=material_id)

    task_id = use_cases["create_task"].execute(
        title="Estudiar derivadas",
        category_id=calculo,
        due_at=clock.now() + timedelta(days=1),
        section_ids=[sections[0].id, sections[1].id],
    )

    detail = use_cases["task_detail"].execute(task_id=task_id)
    assert detail.task.item_count == 2
    assert detail.items[0].kind is MaterialKind.PDF

    session_id = use_cases["start_session"].execute(task_id=task_id)
    assert use_cases["task_detail"].execute(task_id=task_id).task.status is TaskStatus.IN_PROGRESS

    # 20 minutos de trabajo con interacción cada 5.
    for _ in range(4):
        clock.advance(300)
        use_cases["tick_session"].execute(session_id=session_id, had_activity=True)

    # 30 minutos sin tocar nada: solo cuentan los 5 de gracia.
    clock.advance(1800)
    state = use_cases["tick_session"].execute(session_id=session_id)
    assert state.paused
    assert state.effective_seconds == 1500

    use_cases["mark_studied"].execute(section_id=sections[0].id)
    total = use_cases["close_session"].execute(session_id=session_id)
    assert total == 1500

    data = use_cases["dashboard"].execute(period=periods.current_week(clock.now()))
    assert data.total_seconds == 1500
    assert data.by_category[0].category_path == "Matemáticas › Cálculo I"
    assert data.streak_days == 1

    row = use_cases["task_detail"].execute(task_id=task_id).task
    assert row.spent_seconds == 1500
    assert row.studied_items == 1


def test_aprobar_examen_archiva_el_temario_y_lo_saca_de_las_sugerencias(
    use_cases: dict, clock: FixedClock, sample_pdf: Path
) -> None:
    categoria = use_cases["create_category"].execute(name="Física")
    material_id = use_cases["import_files"].execute(
        paths=[sample_pdf], category_id=categoria
    ).imported[0]
    sections = use_cases["list_sections"].execute(material_id=material_id)

    exam_id = use_cases["create_exam"].execute(
        title="Parcial 1",
        category_id=categoria,
        scheduled_at=clock.now() + timedelta(days=3),
        section_ids=[s.id for s in sections[:2]],
    )

    assert len(use_cases["suggest_sections"].execute(category_id=categoria)) == 3

    archived = use_cases["record_exam"].execute(exam_id=exam_id, passed=True, score=4.5)
    assert len(archived) == 2

    remaining = use_cases["suggest_sections"].execute(category_id=categoria)
    assert len(remaining) == 1
    assert remaining[0].title == "Capítulo 3"

    # Archivado pero consultable.
    todas = use_cases["list_sections"].execute(material_id=material_id, include_archived=True)
    assert sum(1 for s in todas if s.archived) == 2


def test_reprobar_mantiene_el_material_activo_y_permite_reintento(
    use_cases: dict, clock: FixedClock, sample_pdf: Path
) -> None:
    categoria = use_cases["create_category"].execute(name="Química")
    material_id = use_cases["import_files"].execute(
        paths=[sample_pdf], category_id=categoria
    ).imported[0]
    sections = use_cases["list_sections"].execute(material_id=material_id)

    exam_id = use_cases["create_exam"].execute(
        title="Quiz", category_id=categoria, section_ids=[s.id for s in sections]
    )
    assert use_cases["record_exam"].execute(exam_id=exam_id, passed=False) == ()
    assert len(use_cases["suggest_sections"].execute(category_id=categoria)) == 3

    retry_id = use_cases["exam_retry"].execute(
        exam_id=exam_id, scheduled_at=clock.now() + timedelta(days=7)
    )
    exams = {e.id: e for e in use_cases["list_exams"].execute()}
    assert exams[retry_id].section_count == 3


def test_el_calendario_agrupa_tareas_y_examenes_por_dia(
    use_cases: dict, clock: FixedClock
) -> None:
    due = clock.now() + timedelta(days=2)
    use_cases["create_task"].execute(title="Leer capítulo", due_at=due)
    use_cases["create_exam"].execute(title="Parcial", scheduled_at=due)

    month = use_cases["calendar_month"].execute(year=due.year, month=due.month)
    day = periods.to_local_date(due)
    assert len(month[day]) == 2
    assert any(entry.exam for entry in month[day])
    assert any(entry.task for entry in month[day])


def test_los_eventos_se_publican_despues_del_commit(container: Container, use_cases: dict) -> None:
    use_cases["create_category"].execute(name="Historia")
    names = [event.event_name for event in container.bus.history]
    assert "CategoryCreated" in names

    # El evento describe algo que ya está en la base.
    with container.uow as uow:
        assert len(uow.categories.list_all()) == 1


def test_una_sesion_abandonada_se_cierra_con_su_ultimo_tick(
    container: Container, use_cases: dict, clock: FixedClock
) -> None:
    task_id = use_cases["create_task"].execute(title="Repasar")
    session_id = use_cases["start_session"].execute(task_id=task_id)
    clock.advance(120)
    use_cases["tick_session"].execute(session_id=session_id, had_activity=True)

    # Simula un cierre anormal: nadie llamó a close_session.
    clock.advance(7200)
    assert container.close_abandoned_sessions() == 1

    sessions = use_cases["list_sessions"].execute(task_id=task_id)
    assert len(sessions) == 1
    assert sessions[0].effective_seconds == 120  # no se inventa el tiempo ausente
    assert sessions[0].ended_at is not None
