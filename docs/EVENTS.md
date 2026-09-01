# EVENTS

Cómo se comunican las partes de STOU sin conocerse. Catálogo completo de eventos, quién
los emite y quién reacciona.

> **Módulo** EVENTS · **Fuente** `src/stou/domain/events.py`, `src/stou/composition/subscriptions.py`, `src/stou/infrastructure/events/`, `src/stou/presentation/qt/events.py` · **Verificado en** `c97ac40`

---

## 1. Para qué sirve todo esto

Imagina que importar un material tuviera que, además de guardarlo: refrescar la
biblioteca, actualizar el contador del inicio, invalidar las métricas del dashboard y
avisar en la barra de estado. El caso de uso «importar material» acabaría conociendo
media aplicación, y cada función nueva le agregaría una línea.

La alternativa que usa STOU es que el caso de uso solo anuncie lo que pasó —«se importó
un material»— y quien tenga algo que hacer al respecto se entere por su cuenta. El
importador no sabe que existe un dashboard. El dashboard no sabe quién importó nada.

Eso es todo lo que hace el bus de eventos. El precio es una indirección; el beneficio es
que agregar un consumidor nuevo no toca ni una línea del productor.

---

## 2. El recorrido de un evento

```
1. Entidad de dominio          task.complete(now) → self.record(TaskCompleted(...))
2. Caso de uso                 uow.commit()
3. Caso de uso                 bus.publish_all(task.pull_events())
4. InMemoryEventBus            llama a los suscriptores, aislando sus errores
5. subscriptions.register      trabajo derivado (índices, cachés, registro en log)
6. QtUiEvents                  reemite en el hilo de la GUI mediante una señal Qt
7. Vistas                      se refrescan
```

Cuatro decisiones gobiernan este flujo:

**El evento se registra en el paso 1 pero se publica en el 3.** La entidad no publica
nada por sí misma; solo deja constancia. Quien decide cuándo el hecho es público es el
caso de uso, y lo hace **después del commit**. Si publicara antes, un suscriptor podría
leer un estado que después se revierte. Lo garantiza `commit_and_publish` en
`use_cases/_shared.py`.

**Un suscriptor que falla no tumba al publicador** (paso 4). El bus atrapa la excepción
y la escribe en el log. Si el registro de una métrica se rompe, el usuario no pierde su
importación.

**Los eventos cruzan al hilo de la GUI por una señal** (paso 6). Un suscriptor puede ser
invocado desde un worker, y tocar widgets desde otro hilo rompe Qt. `UiEvents` se
suscribe a todo y lo reemite con `Signal(object)`, que Qt entrega en el hilo del
receptor.

**Las vistas se refrescan reaccionando a eventos**, no llamándose entre ellas. Una vista
que llama a otra crea un grafo que nadie puede seguir a los tres meses.

---

## 3. Anatomía de un evento

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class TaskCompleted(DomainEvent):
    task_id: EntityId
```

Reglas:

- **Un evento es un hecho ya ocurrido, en pasado.** `TaskCreated`, no `CreateTask`.
- **Inmutable** (`frozen=True`). Lo verifica `test_los_eventos_son_inmutables`.
- **Solo IDs y datos serializables.** Nunca una entidad. Quien reacciona vuelve a
  consultar lo que necesite.
- Hereda `event_id` (UUIDv7 propio) y `occurred_at`, que `Entity.record()` rellena con
  el instante del hecho si viene vacío.

### El nombre se lee con `event_name`

```python
event.event_name    # sí
event.name          # no: CategoryCreated tiene un campo 'name' propio
```

`DomainEvent.event_name` es una propiedad que devuelve `type(self).__name__`. No se
llama `name` porque varios eventos llevan un campo `name` que la taparía. Es un error
que ya se cometió una vez.

---

## 4. Catálogo

Los eventos marcados **(caso de uso)** los publica la capa de aplicación en lugar de la
entidad, porque para cuando ocurren la entidad ya no existe o el hecho abarca un lote.

### Categorías

| Evento | Datos | Emitido por |
|---|---|---|
| `CategoryCreated` | `category_id`, `parent_id`, `name` | `Category.create` |
| `CategoryRenamed` | `category_id`, `name` | `Category.rename` |
| `CategoryMoved` | `category_id`, `parent_id` | `Category.move_to` |
| `CategoryDeleted` | `category_id` | `DeleteCategory` **(caso de uso)** |

### Material

| Evento | Datos | Emitido por |
|---|---|---|
| `MaterialImported` | `material_id`, `category_id`, `kind`, `title` | `Material.create` |
| `MaterialUpdated` | `material_id` | `rename`, `move_to_category`, `edit_body` |
| `MaterialArchived` | `material_id` | `Material.archive` |
| `MaterialReactivated` | `material_id` | `Material.reactivate` |
| `ReadingPositionSaved` | `material_id`, `position` | `Material.save_reading_position` |
| `MaterialDeleted` | `material_id` | `DeleteMaterial` **(caso de uso)** |

### Secciones

| Evento | Datos | Emitido por |
|---|---|---|
| `SectionsCreated` | `material_id`, `section_ids` (tupla) | `ImportMaterialFiles`, `CreateSection`, `SplitMaterialEvenly` **(caso de uso)** |
| `SectionStudied` | `section_id`, `material_id` | `Section.mark_studied` |
| `SectionArchived` | `section_id`, `material_id` | `Section.archive` |

`SectionsCreated` es un evento de **lote** a propósito: seccionar un libro produce
decenas de secciones, y un evento por cada una sería ruido sin información añadida.

### Tareas

| Evento | Datos | Emitido por |
|---|---|---|
| `TaskCreated` | `task_id`, `category_id`, `title` | `Task.create` |
| `TaskUpdated` | `task_id` | `Task.edit`, `Task.reorder` |
| `TaskStatusChanged` | `task_id`, `status` | cualquier transición de estado |
| `TaskCompleted` | `task_id` | `Task.complete` |
| `TaskScheduled` | `task_id`, `due_at` | `Task.reschedule` |
| `TaskMaterialAssigned` | `task_id`, `material_id`, `section_id`, `role` | `Task.assign` |
| `TaskMaterialUnassigned` | `task_id`, `item_id` | `Task.unassign` |
| `TaskDeleted` | `task_id` | `DeleteTask` **(caso de uso)** |

Completar una tarea emite **dos** eventos: `TaskStatusChanged` y `TaskCompleted`. El
primero interesa a quien pinta listas; el segundo, a quien cuenta logros.

### Sesiones de estudio

| Evento | Datos | Emitido por |
|---|---|---|
| `StudySessionStarted` | `session_id`, `task_id` | `StudySession.start`, `create_manual` |
| `StudySessionPaused` | `session_id`, `reason` | `StudySession.tick` (inactividad) |
| `StudySessionResumed` | `session_id` | `StudySession.tick` (vuelve la actividad) |
| `StudySessionClosed` | `session_id`, `task_id`, `effective_seconds` | `StudySession.close`, `create_manual` |

Una sesión manual emite `Started` y `Closed` juntos: nace completa.

### Exámenes

| Evento | Datos | Emitido por |
|---|---|---|
| `ExamCreated` | `exam_id`, `category_id`, `title` | `Exam.create` |
| `ExamRecorded` | `exam_id`, `result`, `archived_section_ids` | `Exam.record_result` |

---

## 5. Quién escucha hoy

### Suscriptores del dominio — `composition/subscriptions.py`

Ahí se registra el trabajo derivado. Hoy es solo registro en el log, deliberadamente
mínimo:

| Evento | Reacción |
|---|---|
| `MaterialImported` | Log informativo con título y tipo |
| `StudySessionClosed` | Log con la tarea y los segundos efectivos |
| `ExamRecorded` | Log con el resultado y cuántas secciones se archivaron |

Cuando la búsqueda de texto entre en funcionamiento, el suscriptor de
`MaterialImported` que llena la tabla FTS5 irá aquí.

**Un suscriptor hace trabajo derivado, no negocio.** Índices, cachés, notificaciones. Si
una regla es esencial, va en el caso de uso: un suscriptor puede fallar en silencio.

### La barra de estado — `presentation/qt/main_window.py`

`MainWindow` escucha **todos** los eventos y traduce a español los que el usuario
reconoce como consecuencia de lo que acaba de hacer. El diccionario `_HUMAN` mapea
`event_name` → mensaje: `TaskCreated` → «Tarea creada», `StudySessionPaused` → «Conteo
en pausa por inactividad».

Los eventos que no están en `_HUMAN` no producen aviso. Avisar de todo es no avisar de
nada.

---

## 6. Suscribirse desde una vista

`UiEvents` ofrece dos formas:

```python
# Solo ciertos tipos
self._s.events.on((TaskCreated, TaskUpdated, TaskDeleted), lambda _e: self.refresh())

# Todos
self._s.events.on_any(self._on_event)
```

La vista recibe la llamada ya en el hilo de la GUI, así que puede tocar widgets sin
precauciones.

---

## 7. El bus en pruebas

`InMemoryEventBus` puede grabar historial:

```python
container.bus.record_history(True)
...
nombres = [e.event_name for e in container.bus.history]
```

La fixture `container` de `tests/conftest.py` ya lo activa, lo que permite afirmar sobre
los hechos publicados sin espiar el interior de los casos de uso. Ver
[`TESTING.md`](TESTING.md).

---

## 8. Agregar un evento

1. Dataclass `frozen=True, slots=True, kw_only=True` en `domain/events.py`, nombre en
   pasado.
2. `self.record(...)` en el método de la entidad que produce el hecho.
3. Fila en el catálogo de este documento.
4. Si el usuario debe verlo, entrada en `_HUMAN` de `main_window.py`.
5. Si algo debe pasar como consecuencia, suscriptor en `composition/subscriptions.py`.
