"""Trabajo en segundo plano.

La regla de la capa es que la interfaz nunca se congela: importar archivos, leer
índices o indexar texto pasa por aquí.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str)


class _Job(QRunnable):
    def __init__(self, fn: Callable[[], Any]) -> None:
        super().__init__()
        self._fn = fn
        self.signals = _Signals()

    @Slot()
    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:
            self.signals.failed.emit(str(exc) or type(exc).__name__)
            return
        self.signals.done.emit(result)


def run_async(
    fn: Callable[[], Any],
    *,
    on_done: Callable[[Any], None] | None = None,
    on_error: Callable[[str], None] | None = None,
) -> None:
    """Ejecuta ``fn`` en un hilo del pool y entrega el resultado en el hilo de la GUI."""
    job = _Job(fn)
    if on_done is not None:
        job.signals.done.connect(on_done)
    if on_error is not None:
        job.signals.failed.connect(on_error)
    QThreadPool.globalInstance().start(job)
