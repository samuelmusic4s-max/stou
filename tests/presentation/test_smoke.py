"""Humo del sistema visual y de los formatos.

Un color mal escrito en la hoja de estilos no rompe la aplicación: Qt lo ignora en
silencio y deja un elemento sin fondo. Por eso los tokens se validan aquí.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from stou.presentation.qt.theme import (  # noqa: E402
    COLORS,
    MOTION,
    RADIUS,
    SPACE,
    STYLESHEET,
    _tokens,
    format_clock,
    format_duration,
    format_duration_short,
    format_size,
    relative_day,
)


def test_todos_los_colores_del_tema_son_validos() -> None:
    invalid = [
        f"{name}={value}"
        for name, value in COLORS.items()
        if not QColor.isValidColorName(value)
    ]
    assert not invalid, f"colores que Qt no entiende: {invalid}"


def test_la_hoja_de_estilos_no_deja_marcadores_sin_reemplazar() -> None:
    import re

    rendered = STYLESHEET.format(**_tokens())
    # Tras formatear, las llaves que quedan son de CSS. Lo que no puede quedar es un
    # marcador con nombre, señal de un token que se escribió mal.
    leftovers = re.findall(r"\{[a-z_][a-z_0-9]*\}", rendered)
    assert not leftovers, f"tokens sin resolver: {set(leftovers)}"


def test_la_hoja_de_estilos_se_aplica_sin_quejas(qapp: QApplication, capsys) -> None:  # noqa: ANN001
    from stou.presentation.qt.theme import apply_theme

    capsys.readouterr()
    apply_theme(qapp)
    qapp.processEvents()
    captured = capsys.readouterr()
    assert "Unknown color name" not in captured.err + captured.out
    assert "Could not parse" not in captured.err + captured.out


def test_las_escalas_estan_completas() -> None:
    assert set(SPACE) >= {"xs", "sm", "md", "lg", "xl"}
    assert set(MOTION) == {"fast", "base", "slow"}
    assert all(value <= 400 for value in MOTION.values()), "el movimiento debe ser corto"
    assert set(RADIUS) >= {"card", "control", "pill"}


def test_formato_de_duracion() -> None:
    assert format_duration(0) == "0 s"
    assert format_duration(90) == "1 min"
    assert format_duration(3700) == "1 h 01 min"
    assert format_duration_short(0) == "0m"
    assert format_duration_short(600) == "10m"
    assert format_duration_short(3700) == "1h 1m"
    assert format_duration_short(7200) == "2h"


def test_formato_de_reloj_y_tamano() -> None:
    assert format_clock(0) == "00:00:00"
    assert format_clock(3661) == "01:01:01"
    assert format_size(0) == "0 B"
    assert format_size(2048) == "2 KB"
    assert format_size(5 * 1024 * 1024) == "5.0 MB"


def test_fechas_en_lenguaje_humano() -> None:
    now = datetime(2026, 3, 2, 12, 0, tzinfo=UTC)
    assert relative_day(now, now) == "hoy"
    assert relative_day(now + timedelta(days=1), now) == "mañana"
    assert relative_day(now - timedelta(days=1), now) == "ayer"
    assert relative_day(now + timedelta(days=3), now) == "en 3 días"
    assert relative_day(now - timedelta(days=4), now) == "hace 4 días"
    assert "/" in relative_day(now + timedelta(days=30), now)
