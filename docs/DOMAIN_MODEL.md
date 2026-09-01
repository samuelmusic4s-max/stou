# DOMAIN_MODEL

Las entidades de STOU, sus invariantes y cómo se relacionan. Es el documento a leer
antes de agregar cualquier regla de negocio.

> **Módulo** DOMAIN_MODEL · **Fuente** `src/stou/domain/`, `src/stou/shared/` · **Verificado en** `c97ac40`

---

## 1. El modelo en una imagen

```
Category ──┬── Material ── Section ──┬── TaskItem ── Task ── StudySession
   (árbol)  │   (biblioteca)  (unidad │  (asignación)  (trabajo)  (tiempo)
            │                estudiable)
            └── Exam ── temario: [Section]  → aprobar archiva esas secciones
```

La pieza central no es la tarea: es la **sección**. Es lo que se asigna, lo que se
marca como estudiado y lo que un examen archiva.

---

## 2. Reglas generales de la capa

- Toda entidad hereda de `Entity` (`domain/entities/base.py`): `id`, `created_at`,
  `updated_at` y una lista privada de eventos.
- La identidad es el `id`. `__eq__` compara tipo e `id`, no contenido.
- `record(evento, at=...)` deja constancia de un hecho; **la entidad no publica nada**.
  El caso de uso recoge con `pull_events()` después del commit.
- `touch(now)` actualiza `updated_at`. El `now` siempre entra por argumento: el dominio
  no lee el reloj, y `tests/test_architecture.py` lo verifica.
- Los identificadores son **UUIDv7 en texto** (`shared/ids.py`): ordenables por tiempo
  de creación y monótonos dentro del mismo milisegundo.
- Todo instante es UTC. La conversión a hora local ocurre solo al presentar.

---

## 3. Value objects y enums (`domain/values.py`)

| Tipo | Valores | Nota |
|---|---|---|
| `MaterialKind` | `pdf`, `epub`, `image`, `video`, `audio`, `web`, `youtube`, `note`, `other` | `is_remote` → `web`, `youtube` |
| `MaterialState` | `active`, `archived` | Lo comparten `Material` y `Section` |
| `TaskStatus` | `pending`, `in_progress`, `done`, `cancelled` | |
| `Priority` | `low`, `normal`, `high` | |
| `ExamResult` | `pending`, `passed`, `failed` | |
| `LocatorUnit` | `page` (PDF), `location` (EPUB), `second` (video/audio), `none` | |
| `ItemRole` | `material`, `solution` | Para qué sirve un material dentro de una tarea |

### `Locator`

Intervalo cerrado que delimita una sección dentro de un material. Inmutable
(`frozen=True, slots=True`).

```python
Locator(unit=LocatorUnit.PAGE, start=1.0, end=40.0)
```

- `start` no puede ser negativo; `end`, si existe, no puede ser anterior a `start`.
- `end is None` significa «hasta donde llegue»: se usa cuando no se conoce la
  extensión del material.
- `label()` produce el texto que ve el usuario: `págs. 1–40`, `0:12:30–0:48:00`,
  `pos. 3–7`.
- `Locator.whole()` es el intervalo de un material sin estructura interna.

---

## 4. Entidades

### 4.1 `Category` — `entities/category.py`

Nodo de un árbol que clasifica material y tareas. En la interfaz se llama **materia**.

- Nombre obligatorio, sin espacios sobrantes, máximo 120 caracteres.
- Una categoría no puede ser su propia madre.
- Tiene `color` (se usa en el dashboard para atribuir tiempo) y `position`.
- Eventos: `CategoryCreated`, `CategoryRenamed`, `CategoryMoved`.
  `CategoryDeleted` lo publica el caso de uso, no la entidad.

La jerarquía se recorre en la capa de aplicación con `CategoryIndex`
(`application/mapping.py`), que da la ruta legible (`Cálculo › Integrales`), el color y
los descendientes de una categoría.

### 4.2 `Material` — `entities/material.py`

Una unidad de contenido de la biblioteca.

Invariantes en `create()`:

- Título obligatorio.
- Un material **remoto** (`web`, `youtube`) necesita `url`.
- Un material **local** que no sea nota necesita `blob_hash`: la referencia a la copia
  interna. Sin archivo almacenado no hay material.
- Solo una **nota** tiene `body` editable (`edit_body` falla en cualquier otro tipo).

Otros campos relevantes: `page_count` y `duration_seconds` (extensión, la usa el
seccionado), `reading_position` (dónde se quedó el usuario), `text_indexed` (bandera
para la búsqueda, todavía sin uso real).

Eventos: `MaterialImported`, `MaterialUpdated`, `MaterialArchived`,
`MaterialReactivated`, `ReadingPositionSaved`. `MaterialDeleted` lo publica el caso de
uso porque la entidad ya no existe cuando ocurre.

### 4.3 `Section` — `entities/section.py`

Fragmento estudiable de un material. La unidad real de trabajo.

- Pertenece a un `material_id` y lleva un `Locator`.
- Título obligatorio.
- `mark_studied(now)` es idempotente: si ya estaba estudiada no hace nada ni vuelve a
  emitir el evento.
- `archive(now)` la saca del circuito activo sin borrarla; sigue consultable.
- Puede tener `parent_id` (jerarquía de secciones) y `notes`.

Eventos: `SectionStudied`, `SectionArchived`. La creación no emite evento propio: el
caso de uso emite un solo `SectionsCreated` por lote, porque seccionar un libro produce
decenas de secciones y un evento por cada una sería ruido.

### 4.4 `Task` y `TaskItem` — `entities/task.py`

`Task` es el trabajo a hacer; `TaskItem` es una asignación de material o sección con un
orden de estudio y un **rol**: `material` (el enunciado) o `solution` (la respuesta).

La solución se guarda como un ítem más y no como una entidad aparte porque comparte
todo con el enunciado —material, sección, orden— y solo cambia para qué sirve. Lo que
sí cambia es el trato: `material_items` y `solution_items` separan las dos listas, el
progreso de la tarea solo cuenta el enunciado, y el modo estudio no abre la solución
hasta que se pide. Una respuesta vista antes de intentarlo no enseña nada.

- Título obligatorio; `due_at` no puede ser anterior a `start_at` (ni al crear ni al
  reprogramar).
- `is_open` → estado `pending` o `in_progress`.
- Transiciones: `begin()` (solo desde `pending`), `complete()`, `reopen()`, `cancel()`.
  Todas son idempotentes y solo emiten evento si el estado cambió de verdad.
- `assign()` rechaza duplicados: el mismo par (material, sección) no se asigna dos veces.
- `unassign()` y `reorder()` recompactan `position`. `reorder()` exige que la lista
  nueva contenga exactamente los mismos ítems.

Eventos: `TaskCreated`, `TaskUpdated`, `TaskStatusChanged`, `TaskCompleted`,
`TaskScheduled`, `TaskMaterialAssigned`, `TaskMaterialUnassigned`. `TaskDeleted` lo
publica el caso de uso.

### 4.5 `StudySession` — `entities/study_session.py`

El tiempo que realmente se dedicó a una tarea. Es la entidad con la lógica más sutil
del proyecto y tiene su propio documento: [`TIME_TRACKING.md`](TIME_TRACKING.md).

Resumen: `start()`, `note_activity()`, `tick()`, `close()`. Una sesión `manual` se crea
completa y cerrada de una vez (`create_manual`, exige duración positiva). `adjust()`
permite corregir el tiempo registrado y rechaza valores negativos.

Eventos: `StudySessionStarted`, `StudySessionPaused`, `StudySessionResumed`,
`StudySessionClosed`.

### 4.6 `Exam` — `entities/exam.py`

Cierra el ciclo de vida del material. Un examen tiene un **temario**: una lista de
`section_ids`.

- Título obligatorio.
- El temario no se puede cambiar una vez registrado el resultado
  (`set_syllabus` falla).
- El resultado se registra **una sola vez** y no puede ser `PENDING`.
- `record_result()` devuelve las secciones que deben archivarse:
  - aprobado sin detalle → todo el temario;
  - reprobado → nada;
  - con `passed_section_ids` → solo esas, y falla si alguna no pertenece al temario.
  Quien archiva de verdad es el caso de uso `RecordExamResult`; la entidad solo decide
  qué corresponde archivar.
- `build_retry()` solo funciona sobre un examen **reprobado**; el reintento hereda el
  temario y guarda `retry_of`.

Eventos: `ExamCreated`, `ExamRecorded` (lleva el resultado y los ids archivados).

---

## 5. Puertos de repositorio

`domain/ports/repositories.py` declara con `typing.Protocol` lo que el dominio necesita
de la persistencia: `CategoryRepository`, `MaterialRepository`, `SectionRepository`,
`TaskRepository`, `StudySessionRepository`, `ExamRepository`.

El dominio declara la necesidad; `infrastructure/persistence/repositories.py` la
cumple. Esa inversión es lo que permite probar todo sin base de datos y cambiar de
motor sin tocar reglas.

---

## 6. Kernel compartido (`shared/`)

| Módulo | Qué ofrece |
|---|---|
| `ids.py` | `EntityId` (`NewType` sobre `str`) y `new_id()`: UUIDv7 en texto |
| `clock.py` | `Clock` (Protocol), `SystemClock`, `FixedClock` para pruebas |

`FixedClock` tiene `set()` y `advance(seconds)`: es la razón por la que el
comportamiento dependiente del tiempo se prueba sin esperar.

---

## 7. Al modificar este modelo

- Nueva invariante → método de la entidad + prueba en `tests/domain/`.
- Nuevo campo persistido → migración nueva al final de `persistence/schema.py` y
  mapper actualizado. Ver [`DATA_AND_STORAGE.md`](DATA_AND_STORAGE.md).
- Nuevo hecho relevante → evento en `domain/events.py` y fila en
  [`EVENTS.md`](EVENTS.md).
