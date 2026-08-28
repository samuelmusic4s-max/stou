# Arquitectura de STOU

Documento normativo. Define la estructura fija del proyecto y las reglas que todo
cambio debe respetar. Si algo aquí estorba, se cambia este documento primero.

## 1. Capas

Cuatro capas más un kernel compartido y un composition root.

```
shared      →  sin dependencias (solo stdlib)
domain      →  depende de shared
application →  depende de domain, shared
infrastructure → depende de application, domain, shared
presentation   → depende de application, domain, shared
composition    → depende de todas (es el único que puede)
```

**Regla de dependencia:** las flechas apuntan hacia adentro y nunca al revés.

- `domain` no importa `application`, `infrastructure` ni `presentation`.
- `application` no importa `infrastructure` ni `presentation`.
- `infrastructure` y `presentation` no se importan entre sí.
- Nadie importa `composition` salvo el entrypoint.
- `PySide6` solo puede aparecer en `presentation` y en `composition`.
- `sqlite3` y el sistema de archivos solo pueden aparecer en `infrastructure`.

## 2. Estructura de carpetas

```
src/stou/
├── __main__.py                 entrypoint: python -m stou
├── shared/                     kernel sin dominio
│   ├── ids.py                  EntityId (UUIDv7 ordenable por tiempo)
│   └── clock.py                Clock, SystemClock, FixedClock
├── domain/
│   ├── entities/               una entidad por módulo, con su invariante
│   │   ├── base.py             identidad y registro de eventos
│   │   ├── category.py  material.py  section.py  task.py
│   │   ├── study_session.py    el conteo de tiempo efectivo
│   │   └── exam.py             el archivado del material
│   ├── values.py               enums y value objects (Locator)
│   ├── events.py               eventos de dominio (inmutables)
│   └── ports/repositories.py   interfaces de repositorio (Protocol)
├── application/
│   ├── ports/                  event_bus, unit_of_work, content
│   ├── use_cases/              un módulo por agregado
│   │   ├── _shared.py          commit_and_publish, NotFound
│   │   ├── categories.py  materials.py  sections.py  tasks.py
│   │   ├── study.py  exams.py
│   │   └── dashboard.py  calendar.py
│   ├── dto.py                  objetos de salida para la UI
│   ├── mapping.py              entidades → DTOs, índice de categorías
│   ├── sectioning.py           índice de un material → secciones
│   └── periods.py              períodos (día local → UTC)
├── infrastructure/
│   ├── persistence/            database, schema, mappers, repositories, unit_of_work
│   ├── storage/blob_store.py   archivos por hash de contenido
│   ├── content/                inspector (PDF/EPUB/medios), epub (extracción)
│   └── events/in_memory_bus.py
├── presentation/
│   ├── services.py             AppServices: la frontera que recibe la UI
│   ├── qt/                     app, main_window, events (relay), theme, worker
│   ├── views/                  library, tasks, calendar, dashboard, study, viewer
│   └── widgets/                viewers.py, dialogs.py
└── composition/
    ├── container.py            cableado de dependencias
    └── subscriptions.py        registro de suscriptores de eventos
```

`tests/test_architecture.py` verifica estas reglas leyendo los imports. Si una capa
importa hacia afuera, o PySide6 aparece fuera de la presentación, el test falla.

## 3. Reglas por capa

### domain

- Entidades como `@dataclass`. Nada de herencia profunda.
- Las entidades registran sus eventos en `self._events` mediante `record()`.
  No publican nada por sí mismas.
- Sin I/O, sin `datetime.now()`, sin `uuid4()` dentro de los métodos: el tiempo y
  los identificadores entran como argumentos o vienen del `Clock` del kernel.
- Los puertos de repositorio se declaran como `typing.Protocol`.

### application

- Un caso de uso es una clase con un único método público `execute()`. Los casos de
  uso se agrupan por agregado en un módulo (`tasks.py`, `materials.py`, …).
- Recibe sus dependencias por constructor. Nunca las construye.
- El caso de uso abre la transacción con `UnitOfWork`, y **publica los eventos
  después del commit**, nunca antes (`_shared.commit_and_publish`).
- Devuelve DTOs, nunca entidades de dominio, a la presentación.

### infrastructure

- Un repositorio implementa un puerto del dominio y traduce filas a entidades.
- El esquema se versiona en `persistence/migrations.py` y solo se agregan
  migraciones al final de la lista. Nunca se edita una migración ya publicada.
- Los archivos del usuario se guardan por hash de contenido en el blob store.

### presentation

- Las vistas no conocen SQLite, ni repositorios, ni el bus directamente: reciben
  casos de uso y un `UiEvents` que ya entrega los eventos en el hilo de la GUI.
- Ninguna vista consulta la base de datos en el hilo de la GUI para trabajo
  pesado: eso va a un worker.
- Las vistas se refrescan reaccionando a eventos, no llamándose entre ellas.

## 4. Eventos

El sistema es orientado a eventos hacia adentro y reactivo hacia la UI.

1. El caso de uso muta el estado y hace commit.
2. Recoge los eventos de las entidades y los publica en el `EventBus`.
3. Los suscriptores registrados en `composition/subscriptions.py` reaccionan
   (indexar texto, invalidar métricas, etc.).
4. `QtUiEvents` reenvía los eventos al hilo de la GUI mediante una señal Qt, y las
   vistas se actualizan.

Reglas:

- Un evento es un hecho ya ocurrido, en pasado: `TaskCreated`, no `CreateTask`.
- Los eventos son inmutables y solo llevan datos serializables e IDs.
- El nombre del hecho se lee con `event.event_name`, no `event.name`: varios eventos
  llevan un campo `name` propio que taparía la propiedad.
- Un suscriptor que falla no puede tumbar al publicador: el bus aísla errores.
- Nada de lógica de negocio esencial dentro de un suscriptor. Los suscriptores
  hacen trabajo derivado (índices, cachés, notificaciones).

## 5. Convenciones

- Todo el tiempo se guarda en UTC. La conversión a hora local ocurre solo al
  presentar.
- Los identificadores son UUIDv7 en texto: ordenables por tiempo y aptos para una
  sincronización futura entre dispositivos.
- Toda tabla lleva `created_at` y `updated_at`. Los borrados que deban propagarse
  a otros dispositivos son lógicos.
- Nombres de dominio en inglés en el código, textos de interfaz en español.
