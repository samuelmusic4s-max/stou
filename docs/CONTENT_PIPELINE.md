# CONTENT_PIPELINE

El camino que recorre un archivo desde que el usuario lo arrastra hasta que aparece
abierto en la pantalla de estudio, partido en capítulos.

> **Módulo** CONTENT_PIPELINE · **Fuente** `src/stou/infrastructure/content/`, `src/stou/application/sectioning.py`, `src/stou/presentation/widgets/viewers.py` · **Verificado en** `c97ac40`

---

## 1. El recorrido completo

```
archivo del usuario
   │
   │ 1. detectar tipo          FileInspector.detect_kind (por extensión)
   │ 2. copiar a la biblioteca BlobStore.store (hash SHA-256, escritura atómica)
   │ 3. leer metadatos         FileInspector.inspect → InspectedMaterial
   │ 4. crear la entidad       Material.create
   │ 5. seccionar              sectioning.sections_from_outline / single_section
   │ 6. guardar y anunciar     commit_and_publish → MaterialImported, SectionsCreated
   ▼
material con secciones, listo para asignarse a una tarea

luego, al estudiar:
   ResolveMaterialSource → build_viewer → visor concreto en pantalla
```

Los pasos 1 a 6 ocurren dentro de `ImportMaterialFiles` (`use_cases/materials.py`), que
los coordina sin saber nada de PDF ni de EPUB: solo habla con los puertos
`MaterialInspector` y `FileStorage`.

Merece la pena notar el orden de 2 y 3: **la inspección se hace sobre la copia interna,
no sobre el original.** Es la razón por la que, si un PDF no trae título embebido, el
título que se usa es el nombre del archivo original (`path.stem`) y no el de la copia,
cuyo nombre es un hash.

---

## 2. Detección de tipo

Por extensión, con una tabla explícita en `infrastructure/content/inspector.py`:

| `MaterialKind` | Extensiones |
|---|---|
| `pdf` | `pdf` |
| `epub` | `epub` |
| `image` | `png`, `jpg`, `jpeg`, `gif`, `bmp`, `webp`, `svg` |
| `video` | `mp4`, `mkv`, `webm`, `avi`, `mov` |
| `audio` | `mp3`, `m4a`, `wav`, `ogg`, `flac`, `opus` |
| `note` | `md`, `txt` |
| `other` | cualquier otra cosa |

`web` y `youtube` no salen de aquí: nacen de `AddLinkMaterial`, que decide entre los dos
mirando el host de la URL.

Un material `other` se importa igual y se guarda igual; simplemente no tiene visor
interno y se abre con la aplicación del sistema.

---

## 3. Inspección: `InspectedMaterial`

Todo lo que sabe leer formatos vive en `infrastructure/content/inspector.py`. El resto del
sistema solo ve esta estructura:

```python
InspectedMaterial(
    kind, title=None, page_count=None, duration_seconds=None,
    outline=(OutlineEntry(title, start, end=None, level=0), ...),
)
```

**Ningún fallo de inspección impide importar.** Todo el bloque está envuelto en
`try/except` que registra una advertencia y devuelve un `InspectedMaterial` mínimo. Un
PDF corrupto entra a la biblioteca sin índice, que es mucho mejor que no entrar.

### PDF (pypdf)

Cuenta páginas, lee el título de los metadatos si existe, y convierte los marcadores en
`OutlineEntry` resolviendo cada destino a un número de página.

Detalle deliberado: **solo el primer nivel de marcadores se vuelve sección.** Los
subcapítulos producirían secciones demasiado pequeñas para asignar a una tarea. Si el PDF
solo tiene marcadores anidados y ninguno de nivel 0, se usan todos como último recurso.

### EPUB (zipfile + ElementTree, sin dependencias)

Un EPUB es un ZIP con XML dentro, así que se lee con la biblioteca estándar. El
procedimiento es el que dicta el formato: `META-INF/container.xml` apunta al `.opf`, el
`.opf` trae el título, el manifiesto y el **spine** (el orden de lectura).

El índice se busca en dos sitios, en este orden: el documento de navegación de EPUB 3
(el ítem del manifiesto con `properties="nav"`) y, si no hay, el `toc.ncx` de EPUB 2.
Cada entrada se resuelve a una **posición del spine**, que es la unidad de las secciones
de un EPUB. Si no hay índice alguno, se genera «Capítulo 1…N» a partir del spine.

Varias entradas del índice pueden apuntar al mismo archivo del spine; se conserva una por
posición para no crear secciones vacías.

### Video y audio (ffprobe, opcional)

La duración se obtiene con `ffprobe` si está instalado en el sistema. **No es una
dependencia:** sin él, `duration_seconds` queda en `None` y el visor la completa al abrir
el archivo. El binario se localiza con `shutil.which` (nunca `shell=True`) y la llamada
tiene un tiempo límite de 20 segundos.

---

## 4. Seccionado — `application/sectioning.py`

Aquí se decide dónde empieza y termina cada sección. Es **lógica pura**: recibe el índice
ya leído y no toca disco ni base de datos, lo que la hace trivial de probar.

### La unidad depende del tipo

| Tipo | `LocatorUnit` | Se mide en |
|---|---|---|
| PDF | `page` | páginas, empezando en 1 |
| EPUB | `location` | posición del spine, empezando en 0 |
| Video, audio, YouTube | `second` | segundos |
| Todo lo demás | `none` | — |

### Tres estrategias

**`sections_from_outline`** — la principal. Cada entrada del índice se vuelve una sección
que **termina donde empieza la siguiente**. La última llega hasta la extensión del
material (páginas o duración) si se conoce, o queda abierta (`end=None`) si no. En PDF se
resta 1 al inicio de la siguiente, porque las páginas son un intervalo cerrado: capítulo
1 son las páginas 1–3 si el capítulo 2 empieza en la 4.

**`single_section`** — una sola sección que cubre el material completo. Es lo que se crea
cuando no hay índice aprovechable, y es lo que hace que **todo material importado tenga al
menos una sección asignable**. Sin eso, un video sin capítulos no podría asignarse a una
tarea.

**`split_evenly`** — partir en N partes iguales, expuesto al usuario como
`SplitMaterialEvenly`. Necesita conocer la extensión y falla con un mensaje claro si no la
conoce. Reemplaza las secciones existentes. En PDF ajusta los cortes a páginas enteras y
la última parte siempre llega al final, para que no se pierdan páginas por redondeo.

---

## 5. Visualización

`ResolveMaterialSource` devuelve un `MaterialSource` (ruta, URL o cuerpo, más la posición
de lectura guardada) y `build_viewer` elige el visor:

| Tipo | Visor | Cómo informa la posición | ¿`media_playing`? |
|---|---|---|---|
| `pdf` | `PdfViewer` | página actual | no |
| `epub` | `EpubViewer` | índice del documento del spine | no |
| `web`, `youtube` | `WebViewer` | segundo del reproductor | **sí** |
| `video`, `audio` | `MediaViewer` | segundo | **sí** |
| `image` | `ImageViewer` | — | no |
| `note` | `NoteViewer` | — | no |
| `other` | `UnsupportedViewer` | — | no |

Todos cumplen el contrato de `BaseViewer`: señal `positionChanged`, propiedad
`media_playing`, `position()`, `go_to(position)` y `shutdown()`.

La propiedad `media_playing` no es un detalle: es lo que evita que un video de cuarenta
minutos se registre como cinco. Ver [`TIME_TRACKING.md`](TIME_TRACKING.md).

`UnsupportedViewer` no es un error: ofrece abrir el material con la aplicación del
sistema. STOU no pretende visualizar todo formato existente.

### EPUB en pantalla

`PrepareEpubReading` descomprime el libro a `cache/epub/<hash>/` y devuelve los documentos
del spine en orden. La extracción se hace **una sola vez**: un archivo marcador
`.stou_ok` señala que la caché está completa, así que reabrir el libro es instantáneo.
Al descomprimir se saltan las entradas con `..` en la ruta, que es la defensa estándar
contra un ZIP malicioso que intente escribir fuera del destino.

---

## 6. Agregar soporte para un formato nuevo

En orden, y cada paso en su capa:

1. **Tipo:** si hace falta, valor nuevo en `MaterialKind` (`domain/values.py`) y
   migración solo si algún índice depende de él; la columna `kind` ya es texto libre.
2. **Detección:** extensión → tipo en la tabla `EXTENSIONS` de `inspector.py`.
3. **Inspección:** rama nueva en `FileInspector.inspect` que devuelva un
   `InspectedMaterial` con lo que sepas leer. Envuelta en `try/except`.
4. **Unidad:** entrada en `_UNIT_BY_KIND` de `sectioning.py` si el material tiene
   estructura interna.
5. **Visor:** clase que herede `BaseViewer` en `widgets/viewers.py` y rama en
   `build_viewer`.
6. **Pruebas:** el seccionado se prueba puro; para la inspección, genera el archivo en una
   fixture como hace `sample_pdf` en `tests/conftest.py`.
7. **Documentación:** las tablas de §2, §4 y §5 de este archivo.

Si el formato necesita una dependencia nueva, eso se discute antes: el proyecto vive
intencionalmente con dos (PySide6 y pypdf), y EPUB es la prueba de que muchos formatos se
resuelven con la biblioteca estándar.
