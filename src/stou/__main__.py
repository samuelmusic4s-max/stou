"""Arranque de STOU: python -m stou"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from stou.composition import subscriptions
from stou.composition.container import Container


def build_services(container: Container):  # noqa: ANN201 - se resuelve en presentación
    from stou.presentation.qt.events import UiEvents
    from stou.presentation.services import AppServices

    use_cases = container.build_use_cases()
    return AppServices(events=UiEvents(container.bus), **use_cases)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    args = argv if argv is not None else sys.argv[1:]
    data_dir = Path(args[0]) if args else None

    from PySide6.QtWidgets import QApplication

    from stou.presentation.qt.main_window import MainWindow
    from stou.presentation.qt.theme import apply_theme

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
    apply_theme(app)

    services = build_services(container)
    window = MainWindow(services)
    window.show()

    try:
        return app.exec()
    finally:
        container.close()


if __name__ == "__main__":
    raise SystemExit(main())
