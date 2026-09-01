# CONVENTIONS

Cómo se escribe código en STOU. No son preferencias estéticas: cada punto de aquí se
sostiene en algo que el proyecto necesita.

> **Módulo** CONVENTIONS · **Fuente** `pyproject.toml`, todo `src/` · **Verificado en** `c97ac40`

---

## 1. Herramientas y su configuración

```toml
[tool.ruff]
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
```

`E`/`F` estilo y errores, `I` orden de imports, `UP` modernización de sintaxis, `B`
trampas comunes (*bugbear*), `SIM` simplificaciones. Cien columnas porque el código de Qt
tiene nombres largos y ochenta forzaría cortes artificiales.

```bash
uv run ruff check src tests     # verificar
uv run ruff check --fix         # corregir lo automático
```

Las excepciones se marcan una por una, con motivo:

```python
def closeEvent(self, event) -> None:  # noqa: ANN001, N802 - API de Qt
```

Un `# noqa` sin explicación es deuda. Uno con explicación es una decisión.

---

## 2. Idioma

| Qué | Idioma | Por qué |
|---|---|---|
| Clases, campos, funciones, eventos | **inglés** | `Task`, `StudySession`, `TaskCompleted`. Es el idioma del oficio y de la mayoría de bibliotecas |
| Textos de interfaz | **español** | Es la audiencia |
| Mensajes de error | **español** | Muchos llegan tal cual al usuario |
| Comentarios y docstrings | **español** | Se leen más que el código |
| Nombres de pruebas | **español** | Se leen como afirmaciones sobre el producto |

La correspondencia entre el vocabulario del código y el de la pantalla está en
[`GLOSSARY.md`](GLOSSARY.md). Importa: en el código es `Category`, en pantalla es
«materia».

---

## 3. Tipado

- `from __future__ import annotations` en **todos** los archivos. Es la primera línea
  después del docstring.
- Sintaxis moderna: `str | None`, `list[Task]`, `dict[str, int]`. Nunca `Optional`,
  `List`, `Dict`.
- Anotaciones completas en todo lo público, incluido el retorno.
- Los puertos se declaran como `typing.Protocol`, no como clases base abstractas: quien
  los cumple no tiene que heredar de nada.
- `NewType` para identificadores: `EntityId = NewType("EntityId", str)`. Un `str`
  cualquiera no es un id por accidente.
- Tras un `require(x, "…")`, el `assert x is not None` que sigue es para el verificador de
  tipos, no para el runtime. Es un patrón deliberado y repetido.

---

## 4. Dataclasses

Es el estilo dominante y casi no hay clases escritas a mano.

| Uso | Forma |
|---|---|
| Entidad de dominio | `@dataclass(kw_only=True)`, mutable, hereda `Entity` |
| Evento de dominio | `@dataclass(frozen=True, slots=True, kw_only=True)` |
| DTO | `@dataclass(frozen=True, slots=True)` |
| Value object | `@dataclass(frozen=True, slots=True)` |

`kw_only=True` en casi todo: con diez campos, los argumentos posicionales son una
invitación a equivocarse. `slots=True` en lo inmutable, que además es lo que más se crea.

Nada de herencia profunda. La única jerarquía es `Entity` → entidades, y `DomainEvent` →
eventos.

---

## 5. Construcción de objetos de dominio

Las entidades se crean con un **classmethod nombrado**, no con el constructor:

```python
Task.create(title=..., now=...)
Material.create(kind=..., title=..., now=...)
StudySession.start(task_id=..., now=...)
StudySession.create_manual(...)
Exam.create(...)
Section.create(...)
```

El constructor por defecto existe (lo necesitan los mappers para reconstruir desde la
base) pero **no valida ni emite eventos**. El classmethod es el único camino que garantiza
las invariantes y registra el hecho de creación. Reconstruir una fila no es crear algo
nuevo, y por eso son dos caminos distintos.

---

## 6. Errores

- El dominio lanza `ValueError` con un mensaje en español dirigido al usuario.
- La aplicación lanza `NotFound` a través de `require(entidad, "mensaje")`.
- Un mensaje de error dice **qué hacer**, no solo qué pasó:

  > «La categoría tiene subcategorías: muévelas o bórralas primero»

- La infraestructura que lee formatos **no propaga fallos de inspección**: registra una
  advertencia y devuelve lo mínimo. Un PDF corrupto entra a la biblioteca sin índice.
- Los suscriptores de eventos fallan aislados: el bus atrapa y registra.
- Nada queda en silencio en la interfaz: `sys.excepthook` convierte cualquier excepción no
  controlada en un aviso visible.

---

## 7. Tiempo

- Todo instante se guarda en **UTC**, en ISO-8601.
- La conversión a hora local ocurre **solo al presentar** o al calcular períodos
  (`application/periods.py`).
- El dominio y los casos de uso **no llaman a `datetime.now()`**: reciben `Clock` o el
  `now` por argumento. Lo verifica `tests/test_architecture.py`.
- Un «día» de las métricas es un día **local**, no un día UTC.

---

## 8. Comentarios y docstrings

El estilo del proyecto es deliberado: el docstring de módulo explica **la decisión** que
contiene ese archivo, no lo que hace.

```python
"""Reloj inyectable.

El dominio y los casos de uso nunca llaman a ``datetime.now()``: reciben un Clock.
Así el comportamiento dependiente del tiempo (inactividad, métricas por período)
es verificable sin esperar.
"""
```

Un comentario que repite el código es ruido; uno que explica por qué el código es así se
vuelve valiosísimo a los seis meses. Cuando un comentario documenta una trampa que ya
costó tiempo, mejor todavía: eso es lo que impide repetirla.

---

## 9. Nombres

| Cosa | Forma | Ejemplo |
|---|---|---|
| Caso de uso | verbo + objeto, imperativo | `CreateTask`, `RecordExamResult` |
| Evento | hecho en pasado | `TaskCompleted`, `SectionArchived` |
| DTO de lista | `<Cosa>Row` | `TaskRow`, `MaterialRow` |
| DTO de detalle | `<Cosa>Detail` | `TaskDetail` |
| Repositorio | `Sqlite<Cosa>Repository` | `SqliteTaskRepository` |
| Vista | `<Cosa>View` / `<Cosa>Window` | `LibraryView`, `StudyWindow` |
| Señal Qt | `camelCase` (convención de Qt) | `studyRequested` |
| Privado del módulo | `_` inicial | `_pick_next`, `_HUMAN` |

Las señales rompen el `snake_case` a propósito: son API de Qt y se leen mejor con la
convención de Qt.

---

## 10. Qt, específicamente

- `clicked.connect(lambda: self._metodo())`, **siempre** envuelto si el método acepta
  argumentos. Ver [`UI_MAP.md`](UI_MAP.md) §6.
- Trabajo que pueda tardar → `worker.run_async`. La interfaz no se congela.
- Nunca tocar widgets desde otro hilo: los eventos llegan por `UiEvents`, ya en el hilo de
  la GUI.
- Espacios y colores desde `SPACE` y `COLORS`. Ningún número mágico en las vistas.
- Antes de animar algo que pudo cerrarse, `motion.is_alive(widget)`.

---

## 11. Dependencias

El proyecto vive con **dos** dependencias de ejecución: PySide6 y pypdf. El soporte de
EPUB está escrito con `zipfile` y `ElementTree` de la biblioteca estándar, y sirve como
referencia de hasta dónde se llega sin agregar nada.

Antes de proponer una dependencia nueva: ¿se resuelve con la biblioteca estándar? ¿Está
mantenida? ¿Qué se rompe si desaparece? Si entra, entra con versión **exacta** —así están
las cuatro que hay— y se anota el motivo en [`DECISIONS.md`](DECISIONS.md).

`ffprobe` es el modelo de dependencia opcional: si está, se aprovecha; si no, el sistema
funciona igual con menos información.
