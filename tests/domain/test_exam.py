"""El examen es lo que cierra el ciclo de vida del material."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from stou.domain.entities.exam import Exam
from stou.domain.values import ExamResult
from stou.shared.ids import EntityId

NOW = datetime(2026, 3, 2, 10, 0, tzinfo=UTC)
S1, S2, S3 = EntityId("s1"), EntityId("s2"), EntityId("s3")


def _exam() -> Exam:
    return Exam.create(title="Parcial 1", now=NOW, section_ids=[S1, S2, S3])


def test_aprobar_archiva_todo_el_temario() -> None:
    exam = _exam()
    archived = exam.record_result(result=ExamResult.PASSED, now=NOW, score=4.2)
    assert archived == [S1, S2, S3]
    assert exam.is_recorded


def test_reprobar_no_archiva_nada() -> None:
    exam = _exam()
    assert exam.record_result(result=ExamResult.FAILED, now=NOW) == []


def test_resultado_por_seccion_archiva_solo_las_aprobadas() -> None:
    exam = _exam()
    archived = exam.record_result(
        result=ExamResult.FAILED, now=NOW, passed_section_ids=[S1, S3]
    )
    assert archived == [S1, S3]


def test_no_se_puede_registrar_dos_veces() -> None:
    exam = _exam()
    exam.record_result(result=ExamResult.PASSED, now=NOW)
    with pytest.raises(ValueError):
        exam.record_result(result=ExamResult.FAILED, now=NOW)


def test_reintento_hereda_el_temario_y_solo_tras_reprobar() -> None:
    exam = _exam()
    with pytest.raises(ValueError):
        exam.build_retry(now=NOW)

    exam.record_result(result=ExamResult.FAILED, now=NOW)
    retry = exam.build_retry(now=NOW)
    assert retry.section_ids == [S1, S2, S3]
    assert retry.retry_of == exam.id


def test_no_se_cambia_el_temario_de_un_examen_registrado() -> None:
    exam = _exam()
    exam.record_result(result=ExamResult.PASSED, now=NOW)
    with pytest.raises(ValueError):
        exam.set_syllabus([S1], NOW)
