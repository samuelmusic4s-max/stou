# ROADMAP

Estado real de cada área y qué falta. Es el documento que más va a cambiar, y el sitio
donde mirar antes de decidir en qué trabajar.

> **Módulo** ROADMAP · **Fuente** estado del código · **Verificado en** `c97ac40` (v0.1.0)

---

## 1. Qué funciona hoy

STOU está completo de punta a punta: se puede importar un libro, partirlo en capítulos,
crear una tarea que apunte a tres de ellos, estudiarla con el tiempo contándose solo,
marcar lo estudiado, registrar el examen y ver el historial. Eso no es un prototipo.

| Área | Estado | Dónde vive |
|---|---|---|
| Categorías jerárquicas | listo | `use_cases/categories.py` |
| Importar PDF, EPUB, video, audio, imagen, notas | listo, con copia interna y deduplicación | `use_cases/materials.py`, `content/inspector.py` |
| Enlaces web y YouTube embebido | listo | `AddLinkMaterial`, `widgets/viewers.py` |
| Seccionado automático y manual | listo | `application/sectioning.py` |
| Tareas con material asignado y orden de estudio | listo | `use_cases/tasks.py` |
| Modo estudio con visor, notas y F11 | listo | `views/study_view.py` |
| Conteo de tiempo con pausa por inactividad | listo | `entities/study_session.py` |
| Calendario de tareas y exámenes | listo | `use_cases/calendar.py` |
| Historial: tiempo por materia y día, racha, atrasos, avance | listo | `use_cases/dashboard.py` |
| Exámenes: registro, archivado del temario, reintento | listo | `use_cases/exams.py` |
| Solución adjunta a una tarea, oculta hasta pedirla | listo | `domain/values.py` (`ItemRole`), `views/study_view.py` |
| Gráfico de actividad y estadísticas por materia | listo | `application/metrics.py`, `widgets/charts.py` |
| Superficie de lectura en papel (nota, EPUB, PDF, imagen) | listo | `qt/theme.py` (`reading_css`), `widgets/viewers.py` |
| Pantalla de inicio con puesta en marcha guiada | listo | `use_cases/home.py`, `views/home_view.py` |

---

## 2. Lo que falta

Ordenado por lo que más cambiaría el uso diario.

### 2.1 Búsqueda de texto dentro del material — *a medio camino*

Es el hueco más visible: hay una biblioteca de material y no se puede buscar dentro de
ella.

Lo que ya existe:

- La tabla FTS5 `material_text`, creada desde la migración 1, con tokenizador
  `unicode61 remove_diacritics 2` (buscar «cálculo» escribiendo «calculo»).
- El puerto `TextExtractor` en `application/ports/content.py`, con el contrato definido:
  devolver pares `(posición, texto)`.
- La bandera `Material.text_indexed` y el método `mark_indexed`.
- El atajo `Ctrl+F`, que hoy enfoca el buscador por título de la vista actual.

Lo que falta:

1. Implementar `TextExtractor` en `infrastructure/content/` (pypdf ya extrae texto de PDF;
   EPUB es XHTML y se puede limpiar con la biblioteca estándar).
2. Suscribir a `MaterialImported` en `composition/subscriptions.py` para indexar en
   segundo plano, marcando `text_indexed` al terminar.
3. Un caso de uso `SearchText` que consulte FTS5 y devuelva resultados con material,
   sección y posición.
4. Una vista o panel de resultados que salte a la posición encontrada.
5. Reindexar lo ya importado la primera vez.

Cuando exista, merece su propio `docs/SEARCH.md`.

### 2.2 Anotaciones y resaltados persistentes — *no empezado*

Hoy el panel de notas del modo estudio guarda texto asociado a la sección, pero no hay
resaltados sobre el material ni anotaciones ancladas a una posición.

Necesita: entidad `Annotation` (material, posición o rango, texto, color), tabla nueva,
casos de uso de CRUD, y soporte en cada visor para dibujar y capturar la selección. El
visor de PDF es el caso difícil.

### 2.3 Exportar el calendario — *no empezado*

Generar un `.ics` con tareas y exámenes. Es la función de mejor relación
valor/esfuerzo que queda: el modelo ya tiene todo lo necesario y no requiere esquema
nuevo.

### 2.4 Sincronización entre dispositivos — *preparado, no implementado*

El modelo de datos está listo para admitirla (UUIDv7, marcas de tiempo en todas las
tablas, borrados lógicos donde importa), pero no hay nada escrito. Es la función más
grande de la lista: implica transporte, resolución de conflictos y sincronizar también los
blobs del material.

Decisiones abiertas: ¿carpeta compartida o servidor propio? ¿el último en escribir gana o
fusión por campo? ¿se sincronizan los archivos o solo los metadatos?

Cuando se aborde, merece `docs/SYNC.md` **antes** de escribir código.

### 2.5 Evaluación con LLM — *experimental, sin decidir*

La idea: generar preguntas sobre una sección estudiada y evaluar las respuestas. Está
marcada como experimental por una razón de producto que conviene no olvidar: el proyecto
declara que «STOU organiza y sirve material de estudio, no lo genera ni lo resume por
iniciativa propia».

Antes de escribir código habría que resolver: ¿modelo local o remoto? Si es remoto, choca
con D-01 (todo local) y con la privacidad del material. ¿Qué pasa cuando el modelo evalúa
mal?

### 2.6 Empaquetado y distribución — *no empezado*

Hoy se corre con `uv run python -m stou`, o con doble clic en el `STOU.desktop` del
escritorio, que llama al intérprete del entorno del proyecto. Eso resuelve el arranque
cómodo en esta máquina, pero no es distribución: sigue dependiendo del repositorio y del
`.venv` en su ruta actual.

Falta un artefacto instalable (AppImage, wheel con dependencias, instalador) y, con él,
el ícono en el tema del sistema y la entrada en el menú de aplicaciones. Cuando exista,
`docs/PACKAGING.md`.

---

## 3. Deuda técnica conocida

Ninguna de estas cosas está rota; todas son sitios donde el atajo actual se va a notar
cuando crezca el uso.

| Punto | Situación | Cuándo dolerá |
|---|---|---|
| `GetHomeOverview` recorre todo el material para contar secciones no estudiadas | Correcto pero O(n) sobre la biblioteca completa | Con cientos de materiales |
| `_category_progress` del dashboard hace lo mismo | Igual | Igual |
| Búsqueda por título con `LIKE` | Suficiente para una biblioteca personal | Con miles de entradas, o si se quiere buscar sin acentos |
| Las listas hijas se reescriben completas al guardar el padre | Simple y correcto | Con tareas de decenas de ítems |
| `subscriptions.py` solo escribe en el log | Es el sitio previsto para el indexado | Cuando llegue la búsqueda |
| Sin registro de auditoría de cambios | No hay historial de ediciones | Si se quiere «deshacer» de verdad |

El patrón de las tres primeras es el mismo: consultas que agregan en Python lo que SQL
podría agregar en una sola sentencia. La solución cuando toque es una consulta con
`GROUP BY`, no una caché.

---

## 4. Cómo mantener este documento

- Al completar un área, muévela a §1 con su ruta en el código y ajusta la tabla del
  `README.md`.
- Al descubrir deuda, añádela a §3 con **cuándo va a doler**. Sin eso, una lista de deuda
  es una lista de deseos.
- Al empezar un área grande, escribe su documento en `docs/` antes del código: obliga a
  cerrar las decisiones abiertas.
- Al tomar una decisión de diseño, anótala en [`DECISIONS.md`](DECISIONS.md).
