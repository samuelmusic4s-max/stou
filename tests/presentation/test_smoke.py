"""Humo de la interfaz: que arranque, que las vistas se pinten y que reaccionen a eventos.

Corre con QT_QPA_PLATFORM=offscreen, sin servidor gráfico.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QApplication  # noqa: E402

from stou.composition.container import Container  # noqa: E402
from stou.presentation.qt.events import UiEvents  # noqa: E402
from stou.presentation.qt.main_window import MainWindow  # noqa: E402
from stou.presentation.qt.theme import apply_theme, format_duration  # noqa: E402
from stou.presentation.services import AppServices  # noqa: E402


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    return app


@pytest.fixture
def services(container: Container, qapp: QApplication) -> AppServices:
    return AppServices(events=UiEvents(container.bus), **container.build_use_cases())


def test_la_ventana_principal_abre_con_sus_cuatro_vistas(
    services: AppServices, qapp: QApplication
) -> None:
    window = MainWindow(services)
    window.show()
    qapp.processEvents()

    assert window._stack.count() == 4
    for index in range(4):
        window._nav.setCurrentRow(index)
        qapp.processEvents()
        assert window._stack.currentIndex() == index

    window.close()


def test_la_biblioteca_se_refresca_al_publicarse_un_evento(
    services: AppServices, qapp: QApplication, sample_pdf: Path
) -> None:
    window = MainWindow(services)
    window.show()
    qapp.processEvents()

    assert window._library._materials.topLevelItemCount() == 0

    services.import_files.execute(paths=[sample_pdf])
    qapp.processEvents()  # el relay entrega el evento en el hilo de la GUI

    assert window._library._materials.topLevelItemCount() == 1
    # La barra de estado narra el último hecho publicado.
    assert window._status_label.text() in ("Material importado", "Secciones creadas")

    window.close()


def test_el_modo_estudio_abre_y_cierra_registrando_la_sesion(
    services: AppServices, qapp: QApplication, container: Container, sample_pdf: Path
) -> None:
    material_id = services.import_files.execute(paths=[sample_pdf]).imported[0]
    sections = services.list_sections.execute(material_id=material_id)
    task_id = services.create_task.execute(
        title="Leer el capítulo 1", section_ids=[sections[0].id]
    )

    window = MainWindow(services)
    window.open_study(task_id)
    qapp.processEvents()

    study = window._windows[0]
    assert study._session_id is not None
    assert study._items.count() == 1

    container.clock.advance(120)  # type: ignore[attr-defined]
    study._had_activity = True
    study._tick()
    assert study._clock.text() == "00:02:00"

    study.close()
    qapp.processEvents()

    sessions = services.list_sessions.execute(task_id=task_id)
    assert len(sessions) == 1
    assert sessions[0].effective_seconds == 120
    window.close()


def test_el_dashboard_dice_cuando_no_hay_datos(
    services: AppServices, qapp: QApplication
) -> None:
    window = MainWindow(services)
    window._dashboard.refresh()
    qapp.processEvents()

    assert window._dashboard._total._value.text() == "—"
    assert window._dashboard._upcoming.item(0).text() == "Nada con fecha en esta semana"
    window.close()


def test_formato_de_duracion() -> None:
    assert format_duration(0) == "0 s"
    assert format_duration(90) == "1 min"
    assert format_duration(3700) == "1 h 01 min"
