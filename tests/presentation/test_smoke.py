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
    ICON_VARIANTS,
    MOTION,
    RADIUS,
    SPACE,
    STYLESHEET,
    _tokens,
    app_icon,
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


def test_el_icono_de_la_aplicacion_trae_todos_los_tamanos(qapp: QApplication) -> None:
    """El ícono se arma a mano, así que hay que comprobar que cada tamaño se dibujó.

    Un SVG mal formado no lanza: QSvgRenderer devuelve un pixmap vacío y la barra de
    tareas acaba con un cuadro transparente.
    """
    from stou.presentation.qt.theme import ASSETS

    del qapp  # el ícono necesita que exista una QApplication, no usarla
    faltantes = [name for name, _sizes in ICON_VARIANTS if not (ASSETS / name).is_file()]
    assert not faltantes, f"faltan variantes del ícono: {faltantes}"

    icon = app_icon()
    assert not icon.isNull()

    esperados = sorted({size for _name, sizes in ICON_VARIANTS for size in sizes})
    disponibles = sorted({size.width() for size in icon.availableSizes()})
    assert disponibles == esperados

    for size in esperados:
        pixmap = icon.pixmap(size, size)
        assert not pixmap.isNull(), f"el ícono de {size} px salió vacío"
        assert not pixmap.toImage().allGray(), f"el ícono de {size} px no dibujó nada"


def test_la_hoja_de_lectura_no_deja_marcadores_sin_reemplazar() -> None:
    """El CSS del EPUB se inyecta como texto: un token mal escrito no lanza, solo deja
    el documento con el estilo de la editorial y nadie se entera."""
    import re

    from stou.presentation.qt.theme import reading_css

    rendered = reading_css()
    leftovers = re.findall(r"\{[a-z_][a-z_0-9]*\}", rendered)
    assert not leftovers, f"tokens sin resolver: {set(leftovers)}"
    # Lo que hace legible la lectura, y que la hoja de la editorial suele romper.
    assert COLORS["paper"] in rendered
    assert COLORS["paper_ink"] in rendered
    assert "max-width: 34em !important" in rendered
    assert "text-align: left !important" in rendered


def test_el_papel_contrasta_de_verdad_con_su_tinta() -> None:
    """Papel claro con tinta clara sería ilegible; conviene comprobarlo, no suponerlo."""

    def luminance(value: str) -> float:
        color = QColor(value)
        channels = []
        for raw in (color.redF(), color.greenF(), color.blueF()):
            channels.append(raw / 12.92 if raw <= 0.03928 else ((raw + 0.055) / 1.055) ** 2.4)
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    pairs = [("paper", "paper_ink"), ("paper", "paper_ink_dim"), ("bg", "text")]
    for background, foreground in pairs:
        light = luminance(COLORS[background])
        dark = luminance(COLORS[foreground])
        top, bottom = max(light, dark), min(light, dark)
        ratio = (top + 0.05) / (bottom + 0.05)
        assert ratio >= 4.5, f"{foreground} sobre {background} contrasta {ratio:.1f}:1"


def test_fechas_en_lenguaje_humano() -> None:
    now = datetime(2026, 3, 2, 12, 0, tzinfo=UTC)
    assert relative_day(now, now) == "hoy"
    assert relative_day(now + timedelta(days=1), now) == "mañana"
    assert relative_day(now - timedelta(days=1), now) == "ayer"
    assert relative_day(now + timedelta(days=3), now) == "en 3 días"
    assert relative_day(now - timedelta(days=4), now) == "hace 4 días"
    assert "/" in relative_day(now + timedelta(days=30), now)
