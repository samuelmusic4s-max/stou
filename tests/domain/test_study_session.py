"""El conteo de tiempo es el dato del que vive el dashboard: se prueba en detalle."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from stou.domain.entities.study_session import StudySession
from stou.shared.ids import EntityId

T0 = datetime(2026, 3, 2, 10, 0, tzinfo=UTC)
TASK = EntityId("task-1")


def _session() -> StudySession:
    return StudySession.start(task_id=TASK, now=T0)


def test_tiempo_se_acumula_mientras_hay_interaccion() -> None:
    session = _session()
    for minute in range(1, 6):
        moment = T0 + timedelta(minutes=minute)
        session.note_activity(moment)
        session.tick(moment)
    assert session.effective_seconds == 300
    assert not session.paused


def test_se_pausa_tras_el_umbral_de_inactividad_y_descarta_el_resto() -> None:
    session = _session()
    # Sin ninguna interacción: solo cuentan los primeros 5 minutos de gracia.
    session.tick(T0 + timedelta(minutes=40), idle_threshold_seconds=300)
    assert session.effective_seconds == 300
    assert session.paused


def test_reproducir_un_video_mantiene_el_conteo_sin_interaccion() -> None:
    session = _session()
    session.tick(T0 + timedelta(minutes=40), media_playing=True, idle_threshold_seconds=300)
    assert session.effective_seconds == 2400
    assert not session.paused


def test_reanuda_sin_abrir_una_sesion_nueva() -> None:
    session = _session()
    session.tick(T0 + timedelta(minutes=40), idle_threshold_seconds=300)
    assert session.paused

    resume = T0 + timedelta(minutes=41)
    session.note_activity(resume)
    session.tick(resume + timedelta(minutes=1), idle_threshold_seconds=300)

    assert not session.paused
    assert session.effective_seconds == 300 + 60
    assert session.is_open


def test_cerrar_registra_el_evento_con_el_tiempo_efectivo() -> None:
    session = _session()
    session.note_activity(T0 + timedelta(minutes=10))
    session.close(T0 + timedelta(minutes=10))

    assert not session.is_open
    names = [event.event_name for event in session.pull_events()]
    assert names == ["StudySessionStarted", "StudySessionClosed"]


def test_sesion_manual_queda_cerrada_con_la_duracion_indicada() -> None:
    session = StudySession.create_manual(
        task_id=TASK, started_at=T0, seconds=1800, now=T0 + timedelta(hours=1)
    )
    assert session.effective_seconds == 1800
    assert not session.is_open
    assert session.manual


def test_una_sesion_cerrada_ya_no_acumula() -> None:
    session = _session()
    session.close(T0 + timedelta(minutes=5))
    before = session.effective_seconds
    session.tick(T0 + timedelta(hours=2), media_playing=True)
    assert session.effective_seconds == before
