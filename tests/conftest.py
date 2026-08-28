"""Fixtures compartidas."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from stou.composition.container import Container
from stou.shared.clock import FixedClock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

START = datetime(2026, 3, 2, 14, 0, tzinfo=UTC)  # lunes


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(START)


@pytest.fixture
def container(tmp_path: Path, clock: FixedClock) -> Container:
    built = Container.create(tmp_path / "data", clock=clock)
    built.bus.record_history(True)
    yield built
    built.close()


@pytest.fixture
def use_cases(container: Container) -> dict:
    return container.build_use_cases()


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """PDF de 12 páginas con marcadores, para probar el seccionado automático."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(12):
        writer.add_blank_page(width=200, height=300)
    writer.add_outline_item("Capítulo 1", 0)
    writer.add_outline_item("Capítulo 2", 4)
    writer.add_outline_item("Capítulo 3", 8)

    path = tmp_path / "libro.pdf"
    with open(path, "wb") as handle:
        writer.write(handle)
    return path
