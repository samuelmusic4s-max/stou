"""Instala el lanzador de STOU en el escritorio del usuario.

Por qué existe un instalador y no basta un `.desktop` suelto: el escritorio empareja una
ventana con su lanzador por el nombre del archivo `.desktop`, y solo lo busca en los
directorios estándar. Un `.desktop` que vive únicamente en el Escritorio abre la
aplicación, pero la barra de tareas no lo encuentra y muestra el ícono de «aplicación
desconocida». Lo mismo con el ícono: referenciado por ruta absoluta funciona en el
lanzador, pero el nombre del tema de íconos (`Icon=stou`) es lo que resuelven todas las
demás superficies.

Instala tres cosas, todas dentro de `$HOME`, sin pedir permisos de administrador:

    ~/.local/share/applications/stou.desktop
    ~/.local/share/icons/hicolor/<n>x<n>/apps/stou.png    un PNG por tamaño
    ~/.local/share/icons/hicolor/scalable/apps/stou.svg

Uso:

    uv run python packaging/install_desktop_entry.py            # instalar
    uv run python packaging/install_desktop_entry.py --shortcut # y copia en el Escritorio
    uv run python packaging/install_desktop_entry.py --uninstall
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Qt necesita una QGuiApplication para rasterizar, pero no una pantalla: sin esto el
# script falla si se corre por SSH o desde un servicio.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:  # permite correrlo sin instalar el paquete
    sys.path.insert(0, str(SRC))

APP_ID = "stou"
TEMPLATE = Path(__file__).parent / "stou.desktop.in"

DATA_HOME = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
APPLICATIONS = DATA_HOME / "applications"
HICOLOR = DATA_HOME / "icons" / "hicolor"


def _interpreter() -> Path:
    """El intérprete que debe arrancar la aplicación.

    Se prefiere el del entorno del proyecto: el lanzador se abre con doble clic, sin
    ningún `uv run` que resuelva las dependencias por nosotros.
    """
    venv = ROOT / ".venv" / "bin" / "python"
    return venv if venv.is_file() else Path(sys.executable)


def _desktop_entry() -> str:
    interpreter = str(_interpreter())
    # La especificación pide comillas dobles si la ruta trae espacios.
    if " " in interpreter:
        interpreter = f'"{interpreter}"'
    return (
        TEMPLATE.read_text(encoding="utf-8")
        .replace("@EXEC@", f"{interpreter} -m stou")
        .replace("@PATH@", str(ROOT))
    )


def _icon_targets() -> list[Path]:
    """Todas las rutas que ocupa el ícono, para instalar y para desinstalar."""
    from stou.presentation.qt.theme import ICON_VARIANTS

    targets = [HICOLOR / "scalable" / "apps" / f"{APP_ID}.svg"]
    for _, sizes in ICON_VARIANTS:
        targets += [HICOLOR / f"{n}x{n}" / "apps" / f"{APP_ID}.png" for n in sizes]
    return targets


def _install_icons() -> int:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    from stou.presentation.qt.theme import ASSETS, ICON_VARIANTS

    if QGuiApplication.instance() is None:
        QGuiApplication([sys.argv[0]])

    written = 0
    for name, sizes in ICON_VARIANTS:
        source = ASSETS / name
        if not source.is_file():
            print(f"  falta {source}, se omite")
            continue
        renderer = QSvgRenderer(str(source))
        for size in sizes:
            image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            renderer.render(painter)
            painter.end()
            target = HICOLOR / f"{size}x{size}" / "apps" / f"{APP_ID}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            if not image.save(str(target), "PNG"):
                raise RuntimeError(f"no se pudo escribir {target}")
            written += 1

    # El SVG queda como variante escalable, para tamaños que no rasterizamos.
    scalable = HICOLOR / "scalable" / "apps" / f"{APP_ID}.svg"
    scalable.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ASSETS / "icon.svg", scalable)
    return written + 1


def _refresh_caches() -> None:
    """Avisar al escritorio. Cada comando puede no existir; ninguno es obligatorio."""
    for command in (
        ["update-desktop-database", str(APPLICATIONS)],
        ["gtk-update-icon-cache", "-qtf", str(HICOLOR)],
        ["kbuildsycoca6", "--noincremental"],
        ["kbuildsycoca5", "--noincremental"],
        ["xdg-desktop-menu", "forceupdate"],
    ):
        if shutil.which(command[0]) is None:
            continue
        subprocess.run(command, check=False, capture_output=True)  # noqa: S603


def _desktop_dir() -> Path:
    """La carpeta del escritorio, que en un sistema en español es «Escritorio»."""
    try:
        result = subprocess.run(  # noqa: S603
            ["xdg-user-dir", "DESKTOP"], check=True, capture_output=True, text=True
        )
        candidate = Path(result.stdout.strip())
        if candidate.is_dir():
            return candidate
    except (OSError, subprocess.CalledProcessError):
        pass
    for name in ("Escritorio", "Desktop"):
        candidate = Path.home() / name
        if candidate.is_dir():
            return candidate
    return Path.home()


def install(shortcut: bool) -> None:
    APPLICATIONS.mkdir(parents=True, exist_ok=True)
    entry = APPLICATIONS / f"{APP_ID}.desktop"
    entry.write_text(_desktop_entry(), encoding="utf-8")
    entry.chmod(0o755)
    print(f"lanzador  {entry}")

    count = _install_icons()
    print(f"ícono     {count} archivo(s) en {HICOLOR}")

    if shortcut:
        copy = _desktop_dir() / "STOU.desktop"
        shutil.copyfile(entry, copy)
        copy.chmod(0o755)
        print(f"atajo     {copy}")

    _refresh_caches()
    print("\nListo. Cierra y vuelve a abrir STOU para que la ventana tome el ícono.")
    if shortcut:
        print(
            "Para anclar a la barra de tareas, usa el menú de inicio o el clic derecho\n"
            "sobre la ventana abierta. Anclar la copia del Escritorio crea un segundo\n"
            "ícono, porque el panel la guarda por ruta y no la empareja con la ventana."
        )


def uninstall() -> None:
    removed = 0
    for path in [APPLICATIONS / f"{APP_ID}.desktop", *_icon_targets()]:
        if path.exists():
            path.unlink()
            removed += 1
    _refresh_caches()
    print(f"Se eliminaron {removed} archivo(s).")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--shortcut", action="store_true", help="dejar también una copia en el Escritorio"
    )
    parser.add_argument("--uninstall", action="store_true", help="quitar lo instalado")
    args = parser.parse_args()

    if args.uninstall:
        uninstall()
    else:
        install(args.shortcut)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
