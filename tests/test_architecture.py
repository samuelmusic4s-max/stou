"""La regla de dependencia se verifica, no se confía.

Si alguien importa infraestructura desde el dominio, este test lo dice antes de que
la arquitectura se degrade en silencio.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "stou"

# Qué paquetes de stou puede importar cada capa.
ALLOWED: dict[str, set[str]] = {
    "shared": set(),
    "domain": {"shared"},
    "application": {"shared", "domain"},
    "infrastructure": {"shared", "domain", "application"},
    "presentation": {"shared", "domain", "application"},
    "composition": {"shared", "domain", "application", "infrastructure", "presentation"},
}

# Librerías externas restringidas a ciertas capas.
EXTERNAL_LIMITS: dict[str, set[str]] = {
    "PySide6": {"presentation", "composition"},
    "sqlite3": {"infrastructure"},
    "pypdf": {"infrastructure"},
}


def _layer_of(path: Path) -> str | None:
    relative = path.relative_to(SRC)
    return relative.parts[0] if len(relative.parts) > 1 else None


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.append(node.module)
    return found


def _modules() -> list[tuple[Path, str]]:
    out = []
    for path in SRC.rglob("*.py"):
        layer = _layer_of(path)
        if layer in ALLOWED:
            out.append((path, layer))
    return out


def test_las_capas_solo_importan_hacia_adentro() -> None:
    violations: list[str] = []
    for path, layer in _modules():
        for imported in _imports(path):
            if not imported.startswith("stou."):
                continue
            target = imported.split(".")[1]
            if target == layer or target not in ALLOWED:
                continue
            if target not in ALLOWED[layer]:
                violations.append(f"{path.relative_to(SRC)}: {layer} → {target}")
    assert not violations, "Dependencias prohibidas:\n" + "\n".join(violations)


def test_las_librerias_externas_se_quedan_en_su_capa() -> None:
    violations: list[str] = []
    for path, layer in _modules():
        for imported in _imports(path):
            root = imported.split(".")[0]
            allowed_layers = EXTERNAL_LIMITS.get(root)
            if allowed_layers is not None and layer not in allowed_layers:
                violations.append(f"{path.relative_to(SRC)}: {layer} importa {root}")
    assert not violations, "Dependencias externas fuera de lugar:\n" + "\n".join(violations)


def test_el_dominio_no_conoce_el_reloj_del_sistema() -> None:
    """El tiempo entra como argumento: si no, el comportamiento no es verificable."""
    offenders: list[str] = []
    for path in (SRC / "domain").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "datetime.now(" in source or "time.time(" in source:
            offenders.append(str(path.relative_to(SRC)))
    assert not offenders, f"El dominio no debe leer el reloj: {offenders}"


def test_los_eventos_son_inmutables() -> None:
    import dataclasses

    from stou.domain import events

    mutable = [
        name
        for name, obj in vars(events).items()
        if isinstance(obj, type)
        and dataclasses.is_dataclass(obj)
        and issubclass(obj, events.DomainEvent)
        and not obj.__dataclass_params__.frozen
    ]
    assert not mutable, f"Eventos mutables: {mutable}"


def test_ninguna_senal_clicked_conecta_un_metodo_con_argumentos() -> None:
    """El bug del botón muerto, convertido en regla.

    ``QPushButton.clicked`` emite un ``bool``. Si se conecta directamente a un método
    que acepta argumentos, ese bool entra como el primero de ellos, el método falla y
    Qt se come la excepción: el botón queda muerto sin una sola pista. La forma segura
    es envolverlo en una lambda sin parámetros.
    """
    offenders: list[str] = []

    for path in (SRC / "presentation").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        # Métodos del módulo que aceptan algo más que self.
        with_args: dict[str, int] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                positional = len(node.args.args) - 1  # descontando self
                keyword_only = len(node.args.kwonlyargs)
                if positional > 0 or keyword_only > 0:
                    with_args[node.name] = positional + keyword_only

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            if not (isinstance(target, ast.Attribute) and target.attr == "connect"):
                continue
            signal = target.value
            if not (
                isinstance(signal, ast.Attribute)
                and signal.attr in {"clicked", "toggled", "triggered", "pressed"}
            ):
                continue
            if not node.args:
                continue
            handler = node.args[0]
            # self._algo  →  método del propio widget
            if (
                isinstance(handler, ast.Attribute)
                and isinstance(handler.value, ast.Name)
                and handler.value.id == "self"
                and handler.attr in with_args
            ):
                offenders.append(
                    f"{path.relative_to(SRC)}:{node.lineno} "
                    f"{signal.attr}.connect(self.{handler.attr}) — envuélvelo en lambda"
                )

    assert not offenders, "Conexiones que se romperán en silencio:\n" + "\n".join(offenders)
