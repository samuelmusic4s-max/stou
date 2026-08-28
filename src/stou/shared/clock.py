"""Reloj inyectable.

El dominio y los casos de uso nunca llaman a ``datetime.now()``: reciben un Clock.
Así el comportamiento dependiente del tiempo (inactividad, métricas por período)
es verificable sin esperar.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Instante actual, siempre con tzinfo=UTC."""
        ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """Reloj controlado, para tests."""

    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def now(self) -> datetime:
        return self._moment

    def set(self, moment: datetime) -> None:
        self._moment = moment

    def advance(self, seconds: float) -> None:
        from datetime import timedelta

        self._moment = self._moment + timedelta(seconds=seconds)
