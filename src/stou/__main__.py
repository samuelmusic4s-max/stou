"""Arranque de STOU: python -m stou"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from stou.composition import subscriptions
from stou.composition.container import Container


def build_services(container: Container):  # noqa: ANN201 - se resuelve en presentación
    from stou.presentation.qt.events import UiEvents
    from stou.presentation.services import AppServices

    use_cases = container.build_use_cases()
    return AppServices(events=UiEvents(container.bus), **use_cases)


def _install_error_reporting() -> None:
    """Que ningún fallo quede en silencio.

    Qt atrapa las excepciones que ocurren dentro de un slot: escribe el traceback en la
    consola y sigue como si nada. Para el usuario eso significa un botón que no hace
    nada y ni un mensaje. Aquí se convierte en un aviso visible.
    """
    import traceback

    from PySide6.QtWidgets import QApplication, QMessageBox

    log = logging.getLogger("stou")

    def hook(kind, value, tb) -> None:  # noqa: ANN001
        if issubclass(kind, KeyboardInterrupt):
            sys.__excepthook__(kind, value, tb)
            return
        log.error("Error no controlado", exc_info=(kind, value, tb))
        if QApplication.instance() is None:
            return
        detail = "".join(traceback.format_exception(kind, value, tb))[-1500:]
        QMessageBox.critical(
            None,
            "Algo falló",
            f"{kind.__name__}: {value}\n\nLa aplicación sigue abierta. El detalle "
            f"técnico está en la consola.\n\n{detail}",
        )

    sys.excepthook = hook


def _claim_window_identity() -> None:
    """Fijar el nombre de instancia de la ventana antes de que Qt lo invente.

    En X11 la ventana se identifica con `WM_CLASS`, un par (instancia, clase). La clase
    sale de `setApplicationName` («STOU»), pero la instancia la deduce Qt del nombre del
    programa: arrancando con `python -m stou`, `sys.argv[0]` es la ruta de `__main__.py`
    y la ventana terminaba anunciándose como «__main__.py». Qt respeta `RESOURCE_NAME`
    si está puesto, así que se declara aquí y el par queda («stou», «STOU»), estable sea
    que se abra por el lanzador, por `uv run` o por doble clic.
    """
    os.environ.setdefault("RESOURCE_NAME", "stou")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    args = argv if argv is not None else sys.argv[1:]
    data_dir = Path(args[0]) if args else None

    _claim_window_identity()

    from PySide6.QtWidgets import QApplication

    from stou.presentation.qt.main_window import MainWindow
    from stou.presentation.qt.theme import app_icon, apply_theme

    container = Container.create(data_dir)
    subscriptions.register(container.bus)

    recovered = container.close_abandoned_sessions()
    if recovered:
        logging.getLogger("stou").info(
            "Se cerraron %d sesión(es) que quedaron abiertas", recovered
        )

    app = QApplication(sys.argv[:1])
    app.setApplicationName("STOU")
    app.setOrganizationName("stou")
    # El escritorio empareja la ventana con su lanzador por este nombre. Sin él, Qt
    # anuncia el del intérprete («python3»), no existe «python3.desktop», y la barra de
    # tareas muestra el ícono de «aplicación desconocida» en vez del nuestro.
    app.setDesktopFileName("stou")
    app.setWindowIcon(app_icon())
    apply_theme(app)
    _install_error_reporting()

    services = build_services(container)
    window = MainWindow(services)
    window.show()

    try:
        return app.exec()
    finally:
        container.close()


if __name__ == "__main__":
    raise SystemExit(main())
