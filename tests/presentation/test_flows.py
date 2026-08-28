"""Flujos de usuario, extremo a extremo sobre la interfaz real.

Cada test recorre un camino que una persona puede hacer con el ratón. La primera
mitad son los caminos felices; la segunda, los bordes: lo que pasa cuando falta algo,
cuando el usuario se equivoca o cuando el archivo está roto.

El bug que motivó este archivo: «Nueva tarea» no hacía nada porque `clicked` emite un
bool que entraba como fecha límite, el diálogo reventaba en su constructor y Qt se
comía la excepción. Un botón muerto y ni una pista. De ahí en adelante, cada acción
tiene su test que la pulsa de verdad.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from stou.application.dto import TaskDetail
from stou.domain.values import TaskStatus
from stou.presentation.qt.main_window import MainWindow
from stou.presentation.services import AppServices
from stou.presentation.views.home_view import HomeView, _TaskButton
from stou.presentation.views.study_view import StudyWindow
from stou.presentation.widgets.components import ActionCard, EmptyState, StepRow
from stou.presentation.widgets.dialogs import TaskDialog
from stou.shared.clock import FixedClock

from .conftest import Script

# --- utilidades ---------------------------------------------------------------


def cards(root) -> list[ActionCard]:  # noqa: ANN001
    return root.findChildren(ActionCard)


def card_titled(root, needle: str) -> ActionCard | None:  # noqa: ANN001
    """La tarjeta cuyo texto menciona lo buscado."""
    for card in cards(root):
        texts = [w.text() for w in card.findChildren(QLabel)]
        if any(needle.lower() in text.lower() for text in texts):
            return card
    return None


def button_titled(root, needle: str) -> QPushButton | None:  # noqa: ANN001
    for button in root.findChildren(QPushButton):
        if needle.lower() in button.text().lower():
            return button
    return None


def empty_states(root) -> list[EmptyState]:  # noqa: ANN001
    return root.findChildren(EmptyState)


def empty_text(root) -> str:  # noqa: ANN001
    """Todo el texto de los estados vacíos presentes, para poder aseverar sobre él."""
    parts: list[str] = []
    for state in empty_states(root):
        parts.extend(w.text() for w in state.findChildren(QLabel))
    return " ".join(parts).lower()


def seed_material(services: AppServices, pdf: Path, *, category: str = "Cálculo I"):  # noqa: ANN201
    """Deja el sistema con una materia, un libro seccionado y nada más."""
    category_id = services.create_category.execute(name=category)
    outcome = services.import_files.execute(paths=[pdf], category_id=category_id)
    material_id = outcome.imported[0]
    sections = services.list_sections.execute(material_id=material_id)
    return category_id, material_id, sections


# =============================================================================
# Caminos felices
# =============================================================================


def test_primer_uso_la_pantalla_de_inicio_guia_paso_a_paso(
    window: MainWindow, services: AppServices, script: Script, pump, sample_pdf: Path
) -> None:
    home: HomeView = window._home  # noqa: SLF001

    # Paso 1: no hay nada. La pantalla lo dice y ofrece un solo botón.
    assert services.home.execute().onboarding_step == 1
    steps = home.findChildren(StepRow)
    assert len(steps) == 3
    with_button = [s for s in steps if s.action_button is not None]
    assert len(with_button) == 1, "solo el paso actual debe ofrecer acción"
    assert with_button[0].action_button.text() == "Crear materia"

    # El usuario pulsa el botón del paso 1 y escribe el nombre.
    script.text_answers = ["Matemáticas"]
    with_button[0].action_button.click()
    pump()
    assert services.home.execute().onboarding_step == 2

    # Paso 2: subir material.
    steps = home.findChildren(StepRow)
    current = [s for s in steps if s.action_button is not None][0]
    assert current.action_button.text() == "Subir material"
    script.files = [sample_pdf]
    current.action_button.click()
    QApplication.processEvents()
    _wait_for(lambda: services.home.execute().has_material, pump)
    assert services.home.execute().onboarding_step == 3

    # Paso 3: crear la primera tarea.
    home.refresh()
    current = [s for s in home.findChildren(StepRow) if s.action_button is not None][0]
    assert current.action_button.text() == "Crear tarea"
    script.task_form.title = "Estudiar el capítulo 1"
    current.action_button.click()
    pump()

    overview = services.home.execute()
    assert overview.onboarding_step == 0
    assert overview.next_task is not None
    # Y la guía desaparece: ya no tiene sentido mostrarla.
    assert home.findChildren(StepRow) == []


def test_el_boton_nueva_tarea_abre_el_dialogo_y_crea(
    window: MainWindow, services: AppServices, script: Script, pump
) -> None:
    """Regresión del bug reportado: el botón no hacía absolutamente nada."""
    window.go_to("tasks")
    tasks = window._tasks  # noqa: SLF001

    script.task_form.title = "Leer termodinámica"
    tasks._new_btn.click()  # noqa: SLF001 - es el clic real, con su bool incluido
    pump()

    assert "Leer termodinámica" in tasks.row_titles()
    assert [t.title for t in services.list_tasks.execute()] == ["Leer termodinámica"]


def test_el_dialogo_de_tarea_aguanta_un_bool_como_fecha(qapp, services: AppServices) -> None:
    """`clicked` emite bool. Construir el diálogo con eso no puede romperlo."""
    dialog = TaskDialog(services.category_tree.execute(), default_due=False)  # type: ignore[arg-type]
    assert dialog.data().due_at is None


def test_crear_tarea_funciona_igual_desde_los_tres_caminos(
    window: MainWindow, services: AppServices, script: Script, pump
) -> None:
    script.task_form.title = "Desde el botón"
    window._tasks._new_btn.click()  # noqa: SLF001
    pump()

    script.task_form.title = "Desde el atajo global"
    window.new_task()  # Ctrl+N
    pump()

    script.task_form.title = "Desde el calendario"
    window.go_to("calendar")
    window._calendar.create_task()  # noqa: SLF001
    pump()

    titles = {t.title for t in services.list_tasks.execute()}
    assert titles == {"Desde el botón", "Desde el atajo global", "Desde el calendario"}


def test_estudiar_desde_inicio_registra_tiempo_y_se_ve_en_el_historial(
    window: MainWindow,
    services: AppServices,
    script: Script,
    pump,
    clock: FixedClock,
    sample_pdf: Path,
) -> None:
    category_id, _material_id, sections = seed_material(services, sample_pdf)
    task_id = services.create_task.execute(
        title="Derivadas",
        category_id=category_id,
        due_at=clock.now() + timedelta(days=1),
        section_ids=[sections[0].id],
    )
    window._home.refresh()  # noqa: SLF001
    pump()

    # La tarjeta principal habla de esa tarea y abre el modo estudio.
    hero = cards(window._home)[0]  # noqa: SLF001
    labels = " ".join(w.text() for w in hero.findChildren(QLabel))
    assert "Derivadas" in labels

    hero.clicked.emit()
    pump()
    study = _only_study_window(window)
    assert study._session_id is not None  # noqa: SLF001

    clock.advance(600)
    study._had_activity = True  # noqa: SLF001
    study._tick()  # noqa: SLF001
    assert study._clock.text() == "00:10:00"  # noqa: SLF001
    assert "contando" in study._clock_state.text()  # noqa: SLF001

    # Marca la sección como estudiada desde el modo estudio.
    study._mark_current_studied()  # noqa: SLF001
    pump()
    detail: TaskDetail = services.task_detail.execute(task_id=task_id)
    assert detail.items[0].studied

    study.close()
    pump()

    assert "10 min" in window._status_label.text()  # noqa: SLF001
    window.go_to("dashboard")
    assert window._dashboard._headline._value.text() == "10m"  # noqa: SLF001
    assert services.home.execute().today_seconds == 600


def test_asignar_material_a_una_tarea_existente_desde_su_menu(
    window: MainWindow, services: AppServices, script: Script, pump, sample_pdf: Path
) -> None:
    category_id, _material, sections = seed_material(services, sample_pdf)
    task_id = services.create_task.execute(title="Repasar", category_id=category_id)
    window.go_to("tasks")
    pump()

    script.sections_to_pick = 2
    window._tasks._offer_assign(task_id, category_id)  # noqa: SLF001
    pump()

    detail = services.task_detail.execute(task_id=task_id)
    assert detail.task.item_count == 2
    assert len(sections) == 3  # el resto sigue disponible


def test_abrir_material_desde_la_biblioteca_abre_el_visor(
    window: MainWindow, services: AppServices, script: Script, pump, sample_pdf: Path
) -> None:
    _category, material_id, _sections = seed_material(services, sample_pdf)
    window.go_to("library")
    window._library.refresh()  # noqa: SLF001
    pump()

    assert window._library.material_titles() == ["libro"]  # noqa: SLF001

    window.open_material(material_id, 0.0)
    pump()
    viewer_windows = [w for w in window._windows if not isinstance(w, StudyWindow)]  # noqa: SLF001
    assert len(viewer_windows) == 1
    viewer_windows[0].close()
    pump()


def test_aprobar_un_examen_archiva_el_temario_y_lo_explica(
    window: MainWindow, services: AppServices, script: Script, pump, sample_pdf: Path
) -> None:
    category_id, material_id, sections = seed_material(services, sample_pdf)
    exam_id = services.create_exam.execute(
        title="Parcial 1",
        category_id=category_id,
        section_ids=[s.id for s in sections[:2]],
    )

    window.go_to("calendar")
    script.exam_passed = True
    window._calendar.record_exam(exam_id, "Parcial 1")  # noqa: SLF001
    pump()

    assert script.said("archivad"), "hay que decirle al usuario qué pasó con su material"
    remaining = services.suggest_sections.execute(category_id=category_id)
    assert len(remaining) == 1

    # Sigue consultable: aparece al activar «Ver archivado».
    window.go_to("library")
    window._library._archived.setChecked(True)  # noqa: SLF001
    pump()
    rows = services.list_sections.execute(material_id=material_id, include_archived=True)
    assert sum(1 for r in rows if r.archived) == 2


def test_registrar_tiempo_a_mano_suma_al_historial(
    window: MainWindow, services: AppServices, script: Script, pump
) -> None:
    task_id = services.create_task.execute(title="Clase presencial")
    window.go_to("tasks")
    row = services.list_tasks.execute()[0]

    script.manual_minutes = 45
    window._tasks._manual_time(row)  # noqa: SLF001
    pump()

    sessions = services.list_sessions.execute(task_id=task_id)
    assert len(sessions) == 1
    assert sessions[0].effective_seconds == 45 * 60
    assert sessions[0].manual


def test_las_cinco_vistas_se_recorren_y_se_refrescan(
    window: MainWindow, pump
) -> None:
    for index, key in enumerate(["home", "tasks", "library", "calendar", "dashboard"]):
        window.go_to(key)
        pump()
        assert window._stack.currentIndex() == index  # noqa: SLF001
        assert window._nav.currentRow() == index  # noqa: SLF001


def test_agregar_un_enlace_de_youtube_entra_como_material(
    window: MainWindow, services: AppServices, script: Script, pump
) -> None:
    window.go_to("library")
    script.link_url = "https://youtu.be/dQw4w9WgXcQ"
    script.link_title = "Clase de límites"
    window._library.add_link()  # noqa: SLF001
    pump()

    rows = services.list_materials.execute()
    assert [r.title for r in rows] == ["Clase de límites"]
    assert rows[0].kind.value == "youtube"


# =============================================================================
# Bordes
# =============================================================================


def test_tarea_sin_titulo_no_crea_nada_y_lo_dice(
    window: MainWindow, services: AppServices, script: Script, pump
) -> None:
    script.task_form.title = "   "
    window._tasks._new_btn.click()  # noqa: SLF001
    pump()

    assert services.list_tasks.execute() == []
    assert script.said("título")


def test_cancelar_el_dialogo_no_crea_nada(
    window: MainWindow, services: AppServices, script: Script, pump
) -> None:
    script.accept_dialogs = False
    window._tasks._new_btn.click()  # noqa: SLF001
    pump()
    assert services.list_tasks.execute() == []
    assert script.messages == []


def test_tarea_sin_material_explica_como_asignarlo_y_sigue_contando(
    window: MainWindow, services: AppServices, script: Script, pump, clock: FixedClock
) -> None:
    task_id = services.create_task.execute(title="Tarea pelada")
    window.open_study(task_id)
    pump()
    study = _only_study_window(window)

    # El visor muestra la explicación, no una pantalla en blanco.
    assert study._viewer_stack.currentIndex() == 1  # noqa: SLF001
    assert "no tiene material asignado" in empty_text(study)
    assert not study._studied_btn.isEnabled()  # noqa: SLF001

    # Y el tiempo se registra igual: el usuario está trabajando.
    clock.advance(120)
    study._had_activity = True  # noqa: SLF001
    study._tick()  # noqa: SLF001
    assert study._clock.text() == "00:02:00"  # noqa: SLF001

    study.close()
    pump()
    assert services.list_sessions.execute(task_id=task_id)[0].effective_seconds == 120


def test_marcar_estudiada_sobre_material_completo_avisa_en_vez_de_fallar(
    window: MainWindow, services: AppServices, script: Script, pump, sample_pdf: Path
) -> None:
    category_id, material_id, _sections = seed_material(services, sample_pdf)
    task_id = services.create_task.execute(title="Leer todo", category_id=category_id)
    services.assign_material.execute(task_id=task_id, material_id=material_id)

    window.open_study(task_id)
    pump()
    study = _only_study_window(window)
    study._mark_current_studied()  # noqa: SLF001

    assert script.said("solo las secciones")
    study.close()
    pump()


def test_importar_un_pdf_corrupto_informa_y_no_tumba_la_vista(
    window: MainWindow, services: AppServices, script: Script, pump, tmp_path: Path
) -> None:
    roto = tmp_path / "roto.pdf"
    roto.write_bytes(b"%PDF-1.7 esto no es un PDF de verdad")

    window.go_to("library")
    script.files = [roto]
    window._library.import_files()  # noqa: SLF001
    _wait_for(lambda: services.list_materials.execute() != [] or script.messages != [], pump)

    # El archivo entra como material «otro» sin índice, o se informa el fallo.
    # Lo que no puede pasar es que la vista quede inservible.
    assert window._library.isEnabled()
    rows = services.list_materials.execute()
    assert len(rows) <= 1


def test_importar_el_mismo_archivo_dos_veces_avisa_que_ya_estaba(
    window: MainWindow, services: AppServices, script: Script, pump, sample_pdf: Path
) -> None:
    window.go_to("library")
    script.files = [sample_pdf]
    window._library.import_files()  # noqa: SLF001
    _wait_for(lambda: services.list_materials.execute() != [], pump)

    script.clear()
    window._library.import_files()  # noqa: SLF001
    _wait_for(lambda: script.messages != [], pump)

    assert script.said("ya")
    assert len(services.list_materials.execute()) == 1


def test_eliminar_una_materia_con_submaterias_se_explica(
    window: MainWindow, services: AppServices, script: Script, pump
) -> None:
    padre = services.create_category.execute(name="Ciencias")
    services.create_category.execute(name="Física", parent_id=padre)

    with pytest.raises(ValueError) as error:
        services.delete_category.execute(category_id=padre)
    assert "subcategor" in str(error.value).lower()

    # La materia sigue ahí: no se perdió nada por intentarlo.
    assert len(services.category_tree.execute()) == 1


def test_eliminar_material_asignado_deja_la_tarea_consistente(
    window: MainWindow, services: AppServices, script: Script, pump, sample_pdf: Path
) -> None:
    category_id, material_id, sections = seed_material(services, sample_pdf)
    task_id = services.create_task.execute(
        title="Con material", category_id=category_id, section_ids=[sections[0].id]
    )
    assert services.task_detail.execute(task_id=task_id).task.item_count == 1

    services.delete_material.execute(material_id=material_id)
    pump()

    detail = services.task_detail.execute(task_id=task_id)
    assert detail.task.item_count == 0

    # Y se puede estudiar sin explotar, mostrando el estado vacío.
    window.open_study(task_id)
    pump()
    study = _only_study_window(window)
    assert study._viewer_stack.currentIndex() == 1  # noqa: SLF001
    study.close()
    pump()


def test_crear_examen_sin_material_no_deja_seguir_y_lo_explica(
    window: MainWindow, services: AppServices, script: Script, pump
) -> None:
    window.go_to("calendar")
    assert window._calendar.create_exam() is None  # noqa: SLF001
    assert script.said("temario")
    assert services.list_exams.execute() == []


def test_reprobar_un_examen_mantiene_el_material_activo(
    window: MainWindow, services: AppServices, script: Script, pump, sample_pdf: Path
) -> None:
    category_id, _material, sections = seed_material(services, sample_pdf)
    exam_id = services.create_exam.execute(
        title="Quiz", category_id=category_id, section_ids=[s.id for s in sections]
    )

    window.go_to("calendar")
    script.exam_passed = False
    window._calendar.record_exam(exam_id, "Quiz")  # noqa: SLF001
    pump()

    assert script.said("sigue activo") or script.said("reintento")
    assert len(services.suggest_sections.execute(category_id=category_id)) == 3


def test_dividir_sin_material_seleccionado_avisa(
    window: MainWindow, script: Script, pump
) -> None:
    window.go_to("library")
    window._library.split_material()  # noqa: SLF001
    assert script.said("elige primero")


def test_busqueda_sin_resultados_ofrece_limpiar(
    window: MainWindow, services: AppServices, script: Script, pump
) -> None:
    services.create_task.execute(title="Álgebra lineal")
    window.go_to("tasks")
    window._tasks._search.setText("no existe esta tarea")  # noqa: SLF001
    pump()

    assert window._tasks.row_titles() == []  # noqa: SLF001
    text = empty_text(window._tasks)  # noqa: SLF001
    assert "coincide" in text
    limpiar = button_titled(window._tasks, "limpiar")  # noqa: SLF001
    assert limpiar is not None
    limpiar.click()
    pump()
    assert window._tasks.row_titles() == ["Álgebra lineal"]  # noqa: SLF001


def test_sin_material_la_lista_de_tareas_manda_a_subir_material(
    window: MainWindow, script: Script, pump
) -> None:
    window.go_to("tasks")
    window._tasks.refresh()  # noqa: SLF001
    text = empty_text(window._tasks)  # noqa: SLF001
    assert "sube" in text or "subir" in text


def test_cerrar_dos_veces_la_ventana_de_estudio_no_duplica_la_sesion(
    window: MainWindow, services: AppServices, script: Script, pump, clock: FixedClock
) -> None:
    task_id = services.create_task.execute(title="Cierre doble")
    window.open_study(task_id)
    pump()
    study = _only_study_window(window)

    clock.advance(60)
    study._had_activity = True  # noqa: SLF001
    study._tick()  # noqa: SLF001

    study.close()
    study.close()  # el usuario pulsa dos veces, o Qt reenvía el cierre
    pump()

    sessions = services.list_sessions.execute(task_id=task_id)
    assert len(sessions) == 1
    assert sessions[0].effective_seconds == 60


def test_una_sesion_sin_actividad_no_infla_el_tiempo(
    window: MainWindow, services: AppServices, script: Script, pump, clock: FixedClock
) -> None:
    task_id = services.create_task.execute(title="Se fue a almorzar")
    window.open_study(task_id)
    pump()
    study = _only_study_window(window)

    clock.advance(3600)  # una hora sin tocar nada
    study._had_activity = False  # noqa: SLF001
    study._tick()  # noqa: SLF001

    assert study._clock.text() == "00:05:00"  # noqa: SLF001 - solo el umbral de gracia
    assert "pausa" in study._clock_state.text()  # noqa: SLF001
    study.close()
    pump()
    assert services.list_sessions.execute(task_id=task_id)[0].effective_seconds == 300


def test_enlace_sin_esquema_se_rechaza_con_explicacion(
    window: MainWindow, services: AppServices, script: Script, pump
) -> None:
    window.go_to("library")
    script.link_url = "youtube.com/watch?v=abc"
    window._library.add_link()  # noqa: SLF001
    pump()

    assert script.said("http")
    assert services.list_materials.execute() == []


def test_el_historial_vacio_explica_en_lugar_de_mostrar_ceros(
    window: MainWindow, pump
) -> None:
    window.go_to("dashboard")
    dashboard = window._dashboard  # noqa: SLF001
    assert dashboard._headline._value.text() == "—"  # noqa: SLF001
    assert "sin sesiones" in dashboard._headline._note.text().lower()  # noqa: SLF001
    assert not dashboard._bars.has_data  # noqa: SLF001
    assert empty_states(dashboard), "las pestañas vacías deben explicar qué falta"


def test_inicio_sin_tareas_abiertas_ofrece_crear_una(
    window: MainWindow, services: AppServices, script: Script, pump, sample_pdf: Path
) -> None:
    # Con material pero sin tareas ya no es primer uso, así que la tarjeta principal
    # tiene que convertirse en una invitación a crear la tarea.
    seed_material(services, sample_pdf)
    services.create_task.execute(title="Única")
    task = services.list_tasks.execute()[0]
    services.change_task_status.execute(task_id=task.id, status=TaskStatus.DONE)

    window._home.refresh()  # noqa: SLF001
    pump()
    hero = cards(window._home)[0]  # noqa: SLF001
    texts = " ".join(w.text() for w in hero.findChildren(QLabel)).lower()
    assert "no tienes ninguna tarea abierta" in texts

    script.task_form.title = "Nueva desde inicio"
    hero.clicked.emit()
    pump()
    assert "Nueva desde inicio" in [t.title for t in services.list_tasks.execute()]


def test_las_tarjetas_recientes_de_inicio_abren_el_modo_estudio(
    window: MainWindow, services: AppServices, script: Script, pump, sample_pdf: Path
) -> None:
    seed_material(services, sample_pdf)  # sin esto, Inicio muestra la guía inicial
    services.create_task.execute(title="Primera")
    services.create_task.execute(title="Segunda")
    window._home.refresh()  # noqa: SLF001
    pump()

    buttons = window._home.findChildren(_TaskButton)  # noqa: SLF001
    assert len(buttons) == 2
    buttons[0]._on_click(buttons[0].task_id)  # noqa: SLF001
    pump()
    assert len(window._windows) == 1  # noqa: SLF001
    window._windows[0].close()  # noqa: SLF001
    pump()


# --- ayuda --------------------------------------------------------------------


def _only_study_window(window: MainWindow) -> StudyWindow:
    studies = [w for w in window._windows if isinstance(w, StudyWindow)]  # noqa: SLF001
    assert len(studies) == 1, f"se esperaba una ventana de estudio, hay {len(studies)}"
    return studies[0]


def _wait_for(condition, pump, attempts: int = 60) -> None:  # noqa: ANN001
    """Espera a que termine un trabajo en segundo plano (importar, indexar)."""
    import time

    for _ in range(attempts):
        if condition():
            pump()
            return
        pump()
        time.sleep(0.02)
    pump()
