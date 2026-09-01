# AGENT_PLAYBOOK

Cómo trabajar dentro de STOU. Escrito para un modelo de lenguaje que va a modificar
el código, y útil igual para una persona que llega por primera vez.

> **Módulo** AGENT_PLAYBOOK · **Fuente** `ARCHITECTURE.md`, `tests/test_architecture.py` · **Verificado en** `c97ac40`

Este archivo cumple el papel que en otros proyectos cumplen `AGENTS.md` o `CLAUDE.md`.
Aquí no se usan esos nombres a propósito: la documentación no se organiza por
herramienta sino por tema, y este es el tema «cómo se trabaja».

---

## 1. Orden de lectura obligatorio

Antes de escribir una línea:

1. [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) — qué es el proyecto y dónde está cada cosa.
2. [`ARCHITECTURE.md`](../ARCHITECTURE.md) — es **normativo**. Si algo estorba, se
   discute y se cambia ese documento primero, no el código a escondidas.
3. El módulo de `docs/` que corresponda a tu tarea (tabla en `PROJECT_CONTEXT.md` §3).
4. El código de la capa que vas a tocar. Leer antes de escribir, siempre.

---

## 2. La forma de un cambio

### 2.1 Ubica la capa

Pregunta única: **¿de quién es esta responsabilidad?**

| Si el cambio es… | Va en |
|---|---|
| Una regla que sería verdad sin computadora | `domain` |
| Orquestación: leer, mutar, transaccionar, publicar | `application` |
| Hablar con SQLite, el disco o un formato de archivo | `infrastructure` |
| Mostrar, escuchar al usuario, dibujar | `presentation` |
| Cablear dependencias | `composition` |
| Utilidad sin dominio (ids, reloj) | `shared` |

Si un cambio parece necesitar dos capas a la vez, casi siempre está mal planteado.
Sepáralo.

### 2.2 Sigue el patrón de la capa

**Dominio.** Entidad `@dataclass`, método que valida su invariante, `self.record(Evento)`
para dejar constancia, `self.touch(now)` para la marca de tiempo. Nada de I/O ni de
`datetime.now()`.

**Aplicación.** Una clase por caso de uso, dependencias por constructor, un único
método público `execute()` con argumentos *keyword-only*, y el final canónico:

```python
class HacerAlgo:
    def __init__(self, uow: UnitOfWork, bus: EventBus, clock: Clock) -> None:
        self._uow, self._bus, self._clock = uow, bus, clock

    def execute(self, *, task_id: EntityId) -> None:
        now = self._clock.now()
        with self._uow as uow:
            task = uow.tasks.get(task_id)
            require(task, "La tarea no existe")
            assert task is not None       # para el verificador de tipos
            task.hacer_algo(now)
            uow.tasks.update(task)
            commit_and_publish(uow, self._bus, task)
```

`commit_and_publish` existe justamente para que nadie publique antes del commit.

**Infraestructura.** Implementa un puerto declarado en `domain/ports` o
`application/ports`. Traduce filas a entidades en `mappers.py`. Los formatos de
archivo se leen en `content/` y salen convertidos en `InspectedMaterial`.

**Presentación.** Recibe casos de uso y `UiEvents`. Trabajo pesado a
`worker.run_async`. Refresco por evento, no por llamadas entre vistas.

### 2.3 Registra el nuevo caso de uso en tres sitios

Si agregas un caso de uso, hay tres lugares que deben mencionarlo o la aplicación
arranca a medias:

1. `src/stou/composition/container.py` → `build_use_cases()`
2. `src/stou/presentation/services.py` → campo en `AppServices`
3. `docs/APPLICATION_SURFACE.md` → fila en el catálogo

### 2.4 Verifica

```bash
uv run pytest
uv run ruff check src tests
```

Ambos deben quedar limpios. `tests/test_architecture.py` no es opcional: es la
frontera de la arquitectura convertida en código.

---

## 3. Errores que este proyecto ya cometió

Cada uno dejó una prueba que lo impide. No los repitas.

**El botón muerto.** `QPushButton.clicked` emite un `bool`. Conectarlo directo a un
método que recibe argumentos hace que ese `bool` entre como primer argumento, el
método explote y Qt se coma la excepción. Resultado: un botón que no hace nada y ni
un mensaje. Envuelve siempre en lambda sin parámetros:

```python
boton.clicked.connect(lambda: self._crear_tarea())   # sí
boton.clicked.connect(self._crear_tarea)             # no, si acepta argumentos
```
Lo verifica `test_ninguna_senal_clicked_conecta_un_metodo_con_argumentos`.

**`event.name` en vez de `event.event_name`.** Varios eventos tienen un campo `name`
propio (`CategoryCreated.name`) que taparía la propiedad. El nombre del hecho se lee
con `event.event_name`.

**Contar tiempo solo por teclado.** Ver un video de 40 minutos sin tocar nada se
registraría como 5. Por eso el tick acepta `media_playing`. Ver `TIME_TRACKING.md`.

**Publicar antes del commit.** Un suscriptor leería un estado que después se
revierte. Por eso existe `commit_and_publish`.

---

## 4. Lo que no se hace sin hablarlo antes

- Editar una migración ya publicada en `persistence/schema.py`. Solo se agregan al
  final de la lista.
- Relajar una regla de `tests/test_architecture.py` para que un cambio pase.
- Introducir una dependencia nueva. El proyecto vive con dos: PySide6 y pypdf.
- Cambiar el modelo de datos de forma que rompa una sincronización futura (los IDs
  son UUIDv7 y los borrados propagables son lógicos por esa razón).
- Sustituir el enfoque de conteo de tiempo por estimaciones. El dashboard nunca
  inventa tiempo que no se midió.

---

## 5. Cómo se escribe aquí

- Nombres de dominio **en inglés** en el código; textos de interfaz **en español**.
- Comentarios que expliquen *por qué*, no *qué*. El código ya dice qué hace.
- Docstring de módulo en los archivos que contienen una decisión, explicando la
  decisión. Es el estilo dominante del repositorio y es deliberado.
- Mensajes de error dirigidos al usuario, en español y accionables:
  «La categoría tiene subcategorías: muévelas o bórralas primero».
- Ningún estado vacío sin explicación: cada lista vacía dice para qué sirve la
  pantalla y ofrece la acción que corresponde.

---

## 6. Al terminar

1. ¿Pasan `pytest` y `ruff`?
2. ¿Agregaste pruebas para lo que agregaste?
3. ¿Hay un documento en `docs/` que ahora dice algo falso? Corrígelo en el mismo
   cambio y actualiza su `Verificado en`. Ver [`DOCS_GUIDE.md`](DOCS_GUIDE.md).
4. ¿Tomaste una decisión con alternativas razonables? Anótala en
   [`DECISIONS.md`](DECISIONS.md).
5. ¿Cambió el estado de un área? Ajusta [`ROADMAP.md`](ROADMAP.md) y la tabla del
   `README.md`.
