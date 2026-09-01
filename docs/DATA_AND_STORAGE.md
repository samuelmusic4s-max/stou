# DATA_AND_STORAGE

Dónde y cómo se guardan los datos: la base SQLite, sus migraciones y el almacén de
archivos del usuario. Lee este documento antes de cambiar el esquema.

> **Módulo** DATA_AND_STORAGE · **Fuente** `src/stou/infrastructure/persistence/`, `src/stou/infrastructure/storage/` · **Verificado en** `c97ac40`

---

## 1. Qué hay en el disco

STOU no ensucia el sistema: todo vive en un solo directorio.

```
$STOU_DATA_DIR  →  $XDG_DATA_HOME/stou  →  ~/.local/share/stou
├── stou.db          base SQLite en modo WAL
├── library/         copias internas del material, organizadas por hash
│   └── ab/abcdef…12.pdf
└── cache/epub/      libros descomprimidos para poder leerlos
```

La resolución de esa ruta está en `composition/container.py` → `default_data_dir()`, y
el orden de prioridad es el de arriba. `python -m stou /otra/ruta` también acepta el
directorio como primer argumento, que es lo que usan las pruebas.

Dos consecuencias prácticas: respaldar STOU es copiar una carpeta, y probar con datos
limpios es apuntar `STOU_DATA_DIR` a otro sitio.

---

## 2. La biblioteca: archivos por hash de contenido

`BlobStore` (`infrastructure/storage/blob_store.py`) guarda cada archivo del usuario con
el SHA-256 de su contenido como nombre, repartido en subdirectorios por los dos primeros
caracteres del hash.

Direccionar por contenido resuelve tres problemas a la vez:

- **La biblioteca deja de depender de dónde estaba el original.** Si el usuario mueve o
  borra el archivo que importó, STOU sigue funcionando.
- **Deduplicación gratis.** Importar el mismo libro dos veces no ocupa el disco dos
  veces; `MaterialRepository.find_by_hash` detecta el duplicado y el importador lo
  reporta en `ImportOutcome.duplicates`.
- **No hay colisiones de nombres.** Dos archivos distintos llamados `apuntes.pdf`
  conviven sin renombrar nada.

La escritura es atómica: se copia a un temporal en el mismo volumen calculando el hash al
paso, y solo al final se renombra al destino. Si algo falla a medio camino no queda un
blob truncado en la biblioteca. Si el destino ya existía, el temporal simplemente se
descarta.

`delete()` borra el archivo y limpia el subdirectorio si quedó vacío. Lo llama
`DeleteMaterial`, **después** de confirmar la transacción y solo si el llamador pidió
`delete_file=True`.

---

## 3. La base de datos

### 3.1 Conexión — `persistence/database.py`

- **Una conexión por hilo** (`threading.local`). Los workers de la GUI no pueden
  compartir la del hilo principal. Excepción: con `:memory:` se comparte una sola, porque
  cada conexión nueva a memoria sería una base distinta.
- `isolation_level=None`: el control transaccional es **explícito**, lo hace la
  `UnitOfWork`.
- PRAGMAs al abrir: `journal_mode=WAL` (leer no bloquea escribir), `foreign_keys=ON`,
  `busy_timeout=5000`, `synchronous=NORMAL`.
- `row_factory = sqlite3.Row`, para leer columnas por nombre.

### 3.2 Migraciones — `persistence/schema.py`

`MIGRATIONS` es una lista de pares `(versión, sql)` que se aplican en orden al abrir la
base. Lo aplicado se anota en `schema_migrations`.

> **Regla que no se negocia: solo se agregan migraciones al final. Nunca se edita una
> migración ya publicada.**

El motivo es directo: una base ya migrada no volverá a ejecutar la versión 1. Si la
editas, tu máquina y la de un usuario con datos previos tendrán esquemas distintos y la
diferencia aparecerá como un error incomprensible semanas después.

Cada migración se ejecuta envuelta en `BEGIN … COMMIT` dentro del propio script, porque
`executescript` hace commit implícito y sin eso una migración a medias dejaría la base
inconsistente.

### 3.3 Tablas (versión actual del esquema: 2)

| Tabla | Guarda | Notas |
|---|---|---|
| `categories` | Jerarquía de materias | `parent_id` con `ON DELETE SET NULL` |
| `materials` | Biblioteca | Índice **único parcial** sobre `blob_hash` cuando no es nulo: la deduplicación es una garantía del esquema, no solo del código |
| `sections` | Secciones estudiables | El `Locator` se aplana en `unit`, `range_start`, `range_end` |
| `tasks` | Tareas | `parent_id` con `ON DELETE CASCADE` (subtareas) |
| `task_items` | Asignaciones tarea↔material/sección | Ordenadas por `position`; `role` distingue enunciado de solución (migración 2) |
| `study_sessions` | Sesiones de estudio | `ended_at IS NULL` marca las abiertas, con índice propio |
| `exams` | Exámenes | `retry_of` apunta al examen original |
| `exam_sections` | Temario | Clave primaria compuesta `(exam_id, section_id)` |
| `material_text` | Índice de texto FTS5 | **Existe y está vacía.** Ver §6 |

Convenciones del esquema:

- Todas las claves son `TEXT`: son UUIDv7 en texto.
- Todas las fechas son `TEXT` en ISO-8601 **UTC**. La conversión la hacen `dt_in` y
  `dt_out` en `mappers.py`, que además asumen UTC si un valor viniera sin zona.
- Toda tabla de entidad lleva `created_at` y `updated_at`.
- Las etiquetas de `materials.tags` se guardan en una sola columna separadas por el
  carácter `\u001f` (unit separator), imposible de escribir por accidente.

### 3.4 Repositorios y mappers

`repositories.py` implementa los puertos del dominio; `mappers.py` traduce filas a
entidades y viceversa. Un repositorio devuelve **entidades completas**: cargar una
`Task` trae sus `task_items`, y cargar un `Exam` trae su temario.

La escritura pasa por un `_upsert` común, así que `add` y `update` comparten camino. Las
listas hijas (ítems de tarea, secciones de examen) se reemplazan por completo al
escribir el padre: es más simple y a esta escala no cuesta nada.

Los ordenamientos están en el SQL, no en Python: `ORDER BY position, name COLLATE
NOCASE` para categorías, tareas con fecha antes que las sin fecha, sesiones por
`started_at`. La búsqueda por texto es un `LIKE` sobre título (y descripción en tareas):
suficiente para una biblioteca personal, y distinto de la búsqueda *dentro* del material,
que aún no existe.

### 3.5 Transacciones — `persistence/unit_of_work.py`

`SqliteUnitOfWork` es **reentrante**: si un caso de uso llama a otro, el bloque interno se
suma a la transacción abierta en lugar de abrir una segunda. El anidamiento se lleva por
hilo, porque cada hilo tiene su propia conexión.

Dos comportamientos que conviene tener claros:

- `commit()` en un bloque interno no confirma nada: marca «pendiente de confirmar» y el
  commit real lo hace el bloque más externo. Partir la transacción por la mitad sería
  peor que no tenerla.
- Al salir del bloque más externo **sin** que nadie haya pedido commit, o con una
  excepción en curso, se hace `ROLLBACK`. Olvidar el commit no guarda a medias: no
  guarda.

---

## 4. Cambiar el esquema, paso a paso

1. Añade un par `(N+1, "…SQL…")` **al final** de `MIGRATIONS`.
2. Actualiza el mapper de la entidad afectada en `mappers.py` (lectura y escritura).
3. Actualiza el `_params` del repositorio correspondiente.
4. Si el campo es nuevo en el dominio, añádelo a la entidad y a su DTO si la interfaz lo
   necesita.
5. Añade una prueba en `tests/infrastructure/test_persistence.py` que escriba y vuelva a
   leer el campo.
6. Actualiza la tabla de §3.3 de este documento.

Para columnas nuevas, `ALTER TABLE … ADD COLUMN` con `DEFAULT` es suficiente y no
reescribe la tabla. Para cambios estructurales, el patrón de SQLite es crear la tabla
nueva, copiar, borrar la vieja y renombrar, todo dentro de la misma migración.

---

## 5. Pensando en la sincronización futura

No hay sincronización, pero el modelo está preparado para admitirla sin una migración
traumática:

- **UUIDv7 en texto** como identificadores: ordenables por tiempo de creación, generables
  sin coordinación con nadie y sin riesgo de colisión entre dispositivos.
- **`created_at` y `updated_at` en todas las tablas**: la base de cualquier
  reconciliación por marca de tiempo.
- **Los borrados que deban propagarse son lógicos**, no físicos. Un borrado físico es
  indistinguible de «este dispositivo nunca lo tuvo».

Si un cambio rompe alguna de estas tres propiedades, cierra la puerta a la
sincronización. Vale la pena decirlo en voz alta antes de hacerlo.

---

## 6. La tabla FTS5 vacía

`material_text` está creada desde la migración 1 con tokenizador `unicode61
remove_diacritics 2` (busca «cálculo» escribiendo «calculo»), y **nadie la llena**.

El hueco es conocido y está a mitad de camino: el puerto `TextExtractor`
(`application/ports/content.py`) ya define el contrato — devolver pares
`(posición, texto)` — pero no hay implementación ni suscriptor que la invoque, y
`Material.text_indexed` es una bandera que nunca se enciende.

Lo que falta para cerrarlo: implementar `TextExtractor` en `infrastructure/content/`,
suscribir a `MaterialImported` en `composition/subscriptions.py` para indexar en segundo
plano, y añadir un caso de uso de búsqueda. Ver [`ROADMAP.md`](ROADMAP.md).
