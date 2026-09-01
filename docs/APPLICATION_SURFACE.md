# APPLICATION_SURFACE

Todo lo que STOU sabe hacer, expresado como casos de uso. Si buscas «¿ya existe algo
que haga esto?», la respuesta está aquí.

> **Módulo** APPLICATION_SURFACE · **Fuente** `src/stou/application/` · **Verificado en** `c97ac40`

---

## 1. Cómo leer este documento

La capa de aplicación es la lista de verbos del sistema. Cada acción que el usuario
puede realizar tiene una clase con un único método `execute()`, y no hay forma de
hacer nada que no esté en esta lista: la interfaz no habla con la base de datos, solo
llama a estos objetos.

Eso tiene una consecuencia práctica agradable. Para entender qué hace la aplicación no
hace falta leer las vistas ni el SQL: basta este catálogo. Y para agregar una función
nueva, el trabajo consiste en agregar un verbo, no en repartir lógica por la interfaz.

Las secciones 3 a 9 son el catálogo por agregado. La sección 2 cuenta un flujo completo
en prosa, que es la mejor entrada si es tu primera vez.

---

## 2. Un flujo completo, de principio a fin

Así se ve una jornada típica atravesando la aplicación. Cada paso nombra el caso de uso
que lo ejecuta.

**Preparar.** El usuario crea la materia «Cálculo» (`CreateCategory`) y arrastra un PDF
de 300 páginas (`ImportMaterialFiles`). Ese único paso hace bastante: copia el archivo a
la biblioteca interna con su hash como nombre, detecta que es un PDF, lee sus
marcadores, y crea una sección por capítulo. Si el PDF no tuviera marcadores, quedaría
una sola sección que cubre el libro entero, y el usuario podría partirlo en diez partes
iguales con `SplitMaterialEvenly`.

**Planear.** Crea la tarea «Estudiar integrales para el parcial»
(`CreateTask`, que acepta ya los `section_ids`) y le asigna los capítulos 4 al 6
(`AssignMaterialToTask`). El orden de estudio se ajusta con `ReorderTaskItems`.
Registra el parcial en el calendario con su temario (`CreateExam`).

**Estudiar.** Abre la tarea. La ventana de estudio llama a `GetTaskDetail` para saber
qué mostrar, `ResolveMaterialSource` para saber cómo abrir cada pieza, y
`StartStudySession` para arrancar el cronómetro. Cada cinco segundos manda un
`TickStudySession` con dos datos: si hubo interacción y si un medio está reproduciéndose.
Al terminar un capítulo pulsa Ctrl+Intro (`MarkSectionStudied`). Al cerrar la ventana,
`CloseStudySession` sella el tiempo.

**Cerrar el ciclo.** Da el parcial, lo aprueba y lo registra (`RecordExamResult`). Las
secciones del temario quedan archivadas: dejan de aparecer en el circuito activo, pero
siguen consultables. Al día siguiente, `GetHomeOverview` ya no le propone integrales
sino lo siguiente más urgente.

**Si algo se cae.** Si la aplicación se cierra de golpe con una sesión abierta, al
siguiente arranque `CloseAbandonedSessions` la cierra en su último tick conocido. No se
inventa tiempo.

---

## 3. Reglas que cumple todo caso de uso

Antes del catálogo, el patrón. Es siempre el mismo, y esa uniformidad es intencional:
quien lee un caso de uso ya sabe leer los demás.

- Recibe sus dependencias por constructor (`UnitOfWork`, `EventBus`, `Clock` y, si hace
  falta, un puerto de contenido). Nunca las construye.
- Un solo método público, `execute()`, con argumentos **keyword-only**.
- Abre la transacción con `with self._uow as uow:` y la cierra con
  `commit_and_publish(uow, bus, *entidades)`, que hace commit **y solo entonces**
  publica los eventos.
- Devuelve **DTOs** (`application/dto.py`) o identificadores. Nunca entidades de dominio.
- Si algo no existe, lanza `NotFound` a través de `require(entidad, "mensaje")`. Los
  mensajes están en español porque llegan al usuario.

La `UnitOfWork` es **reentrante**: si un caso de uso llama a otro, el bloque interno se
suma a la transacción abierta en lugar de abrir una segunda.

---

## 4. Categorías — `use_cases/categories.py`

| Caso de uso | Firma de `execute` | Devuelve |
|---|---|---|
| `GetCategoryTree` | `()` | `tuple[CategoryNode, ...]` |
| `CreateCategory` | `*, name, parent_id=None, color=None` | `EntityId` |
| `RenameCategory` | `*, category_id, name` | `None` |
| `MoveCategory` | `*, category_id, parent_id` | `None` |
| `DeleteCategory` | `*, category_id` | `None` |

Detalles que importan: `CreateCategory` valida que la categoría madre exista.
`MoveCategory` impide crear un ciclo (mover una categoría dentro de su propia
descendencia). `DeleteCategory` se niega si tiene subcategorías y dice qué hacer:
«muévelas o bórralas primero».

---

## 5. Material — `use_cases/materials.py`

| Caso de uso | Firma de `execute` | Devuelve |
|---|---|---|
| `ImportMaterialFiles` | `*, paths, category_id=None, auto_section=True` | `ImportOutcome` |
| `AddLinkMaterial` | `*, url, title=None, category_id=None, duration_seconds=None` | `EntityId` |
| `CreateNote` | `*, title, body="", category_id=None` | `EntityId` |
| `UpdateMaterial` | `*, material_id, title=None, category_id=None, body=None` | `None` |
| `SaveReadingPosition` | `*, material_id, position` | `None` |
| `SetMaterialState` | `*, material_id, archived` | `None` |
| `DeleteMaterial` | `*, material_id, delete_file=True` | `None` |
| `ListMaterials` | `*, category_id=None, include_subcategories=True, kinds=None, include_archived=False, search=None` | `list[MaterialRow]` |
| `ResolveMaterialSource` | `*, material_id` | `MaterialSource` |
| `PrepareEpubReading` | `*, material_id` | `list[Path]` |
| `SplitMaterialEvenly` | `*, material_id, parts` | `tuple[EntityId, ...]` |

**`ImportMaterialFiles` es el caso de uso más denso del proyecto.** Importa un lote y
un archivo malo no aborta el resto: devuelve `ImportOutcome` con tres listas —
`imported`, `duplicates` y `failed` (nombre y motivo). Detecta duplicados por hash de
contenido, así que reimportar el mismo libro no ocupa el disco dos veces ni crea una
segunda entrada. Y con `auto_section=True` crea las secciones a partir del índice del
material; si no hay índice aprovechable, crea una sola que lo cubre completo.

**`ResolveMaterialSource` existe para que la presentación no sepa dónde viven los
archivos.** Devuelve un `MaterialSource` con lo necesario para abrir: `path`, `url` o
`body`, según el tipo, más la posición de lectura guardada.

**`SplitMaterialEvenly` reemplaza** las secciones existentes, no las agrega. Necesita
conocer la extensión del material (páginas o duración) y falla si no la conoce.

---

## 6. Secciones — `use_cases/sections.py`

| Caso de uso | Firma de `execute` | Devuelve |
|---|---|---|
| `ListSections` | `*, material_id, include_archived=True` | `list[SectionRow]` |
| `CreateSection` | `*, material_id, title, start, end=None, parent_id=None` | `EntityId` |
| `UpdateSection` | `*, section_id, title=None, start=None, end=None` | `None` |
| `DeleteSection` | `*, section_id` | `None` |
| `MarkSectionStudied` | `*, section_id, studied=True` | `None` |

La unidad de `start` y `end` no se pasa: se deduce del tipo de material (página para
PDF, posición del spine para EPUB, segundo para medios). Esa correspondencia vive en
`application/sectioning.py` y está explicada en
[`CONTENT_PIPELINE.md`](CONTENT_PIPELINE.md).

---

## 7. Tareas — `use_cases/tasks.py`

| Caso de uso | Firma de `execute` | Devuelve |
|---|---|---|
| `CreateTask` | `*, title, description="", category_id=None, parent_id=None, priority=NORMAL, start_at=None, due_at=None, estimated_minutes=None, section_ids=None` | `EntityId` |
| `UpdateTask` | `*, task_id, title=None, description=None, category_id=None, priority=None, estimated_minutes=None` | `None` |
| `RescheduleTask` | `*, task_id, start_at=None, due_at=None` | `None` |
| `ChangeTaskStatus` | `*, task_id, status` | `None` |
| `DeleteTask` | `*, task_id` | `None` |
| `ListTasks` | `*, category_id=None, include_subcategories=True, statuses=None, due_from=None, due_to=None, search=None` | `list[TaskRow]` |
| `GetTaskDetail` | `*, task_id` | `TaskDetail` |
| `AssignMaterialToTask` | `*, task_id, material_id=None, section_ids=None, role=MATERIAL` | `None` |
| `UnassignTaskItem` | `*, task_id, item_id` | `None` |
| `ReorderTaskItems` | `*, task_id, item_ids` | `None` |
| `SuggestSections` | `*, category_id, limit=200` | `list[SectionRow]` |

`AssignMaterialToTask` con `role=ItemRole.SOLUTION` añade la **solución** de la tarea.
Es el mismo camino que el material normal a propósito: una solución es material de la
biblioteca, y así se puede subir el solucionario una vez y reutilizarlo. El progreso de
la tarea sigue contando solo el enunciado.

`CreateTask` acepta `section_ids` para crear la tarea y asignarle material en un solo
paso, que es como la usa el diálogo de nueva tarea. `AssignMaterialToTask` acepta un
material completo o una lista de secciones. `SuggestSections` es lo que alimenta el
diálogo de asignación: propone secciones activas y no estudiadas de la materia.

Los `TaskRow` que devuelven estos casos de uso ya vienen con el trabajo hecho:
`spent_seconds` (tiempo sumado de sus sesiones), `studied_items` y `overdue` calculado
contra el reloj inyectado. La vista no calcula nada.

---

## 8. Estudio y tiempo — `use_cases/study.py`

| Caso de uso | Firma de `execute` | Devuelve |
|---|---|---|
| `StartStudySession` | `*, task_id` | `EntityId` |
| `TickStudySession` | `*, session_id, had_activity=False, media_playing=False, material_id=None` | `SessionState \| None` |
| `CloseStudySession` | `*, session_id` | `int` (segundos efectivos) |
| `CloseAbandonedSessions` | `()` | `int` (cuántas cerró) |
| `AddManualSession` | `*, task_id, started_at, minutes` | `EntityId` |
| `AdjustSession` | `*, session_id, minutes` | `None` |
| `DeleteSession` | `*, session_id` | `None` |
| `ListSessions` | `*, start=None, end=None, task_id=None` | `list[SessionRow]` |

`StartStudySession` cierra cualquier otra sesión abierta antes de empezar y pone la
tarea en progreso: no puede haber dos cronómetros corriendo. `CloseAbandonedSessions`
solo se llama al arrancar, desde `Container`, y cierra las sesiones huérfanas en su
último tick conocido.

La mecánica del conteo está en [`TIME_TRACKING.md`](TIME_TRACKING.md).

---

## 9. Exámenes — `use_cases/exams.py`

| Caso de uso | Firma de `execute` | Devuelve |
|---|---|---|
| `CreateExam` | `*, title, category_id=None, scheduled_at=None, section_ids=None` | `EntityId` |
| `SetExamSyllabus` | `*, exam_id, section_ids` | `None` |
| `RecordExamResult` | `*, exam_id, passed, score=None, passed_section_ids=None` | `tuple[EntityId, ...]` |
| `CreateExamRetry` | `*, exam_id, scheduled_at=None` | `EntityId` |
| `ListExams` | `*, category_id=None, scheduled_from=None, scheduled_to=None, pending_only=False` | `list[ExamRow]` |
| `DeleteExam` | `*, exam_id` | `None` |

`RecordExamResult` devuelve los ids de las secciones que archivó. Es el único punto del
sistema donde el material sale del circuito activo por sí solo, y es la razón por la que
la biblioteca no crece indefinidamente.

---

## 10. Vistas agregadas

Tres casos de uso que no cambian nada: solo leen y componen. Cada uno resuelve una
pregunta distinta del usuario.

| Caso de uso | Pregunta que responde | Devuelve |
|---|---|---|
| `GetHomeOverview` (`home.py`) | «¿Qué hago ahora?» | `HomeOverview` |
| `GetDashboard` (`dashboard.py`) | «¿Qué hice y qué viene?» | `DashboardData` |
| `GetCalendarMonth` (`calendar.py`) | «¿Qué hay este mes?» | `dict[date, list[CalendarEntry]]` |

**`GetHomeOverview`** elige una sola tarea, con esta prioridad: si falta poner en marcha
el sistema (categoría → material → tarea), lo que toca es el siguiente paso de la puesta
en marcha (`onboarding_step` 1, 2 o 3); si hay una tarea en progreso, retomarla; si hay
tareas con fecha, la más próxima; si no, la abierta más antigua. Además trae tiempo de
hoy y de la semana, racha de días activos, atrasos y el próximo examen con los días que
faltan.

**`GetDashboard`** resuelve el período con el reloj inyectado: la vista pide «esta
semana» por nombre (`period_key`: `today`, `week`, `month`, `last30`) y no calcula
fechas. Si las calculara con el reloj del sistema, la interfaz y las métricas podrían
discrepar. Agrega tiempo por categoría y por día, tareas completadas y abiertas,
atrasos, próximas, plan de la semana, próximos exámenes, avance por materia y racha.
**Solo suma sesiones registradas: nunca estima tiempo que no se midió.**

**`GetCalendarMonth`** agrupa tareas con fecha límite y exámenes por **día local**, no
por día UTC.

---

## 11. Piezas de apoyo de la capa

| Módulo | Qué hace |
|---|---|
| `dto.py` | Los objetos que ve la interfaz: `TaskRow`, `MaterialRow`, `SectionRow`, `DashboardData`, `HomeOverview`… Todos inmutables |
| `mapping.py` | Entidad → DTO. Función pura, no toca repositorios. Aquí vive `CategoryIndex` |
| `metrics.py` | Agregación compartida: tiempo por día, por materia, avance y racha. Inicio y el Historial la usan para no dar dos cifras distintas de lo mismo |
| `sectioning.py` | Índice de un material → secciones: `sections_from_outline`, `single_section`, `split_evenly` |
| `periods.py` | Períodos de tiempo: `today`, `current_week`, `current_month`, `last_days`, `month_bounds`. Calculan sobre **días locales** y devuelven límites en UTC |
| `ports/` | Lo que la capa necesita del exterior: `UnitOfWork`, `EventBus`, `FileStorage`, `MaterialInspector`, `TextExtractor`, `EpubUnpacker` |
| `use_cases/_shared.py` | `commit_and_publish`, `NotFound`, `require` |

---

## 12. Agregar un caso de uso

1. Escríbelo en el módulo del agregado que corresponda (`tasks.py`, `materials.py`, …).
2. Regístralo en `composition/container.py` → `build_use_cases()`.
3. Añádelo a `presentation/services.py` → `AppServices`.
4. Agrega su fila al catálogo de este documento.
5. Cúbrelo con una prueba en `tests/application/` y, si tiene interfaz, en
   `tests/presentation/test_flows.py`.

Olvidar el paso 2 o el 3 produce el síntoma clásico: la función existe y nadie puede
llamarla.
