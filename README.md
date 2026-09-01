<div align="center">
  <img src="src/stou/presentation/qt/assets/icon.svg" width="96" alt="STOU">
  <h1>STOU</h1>
  <p><strong>Gestor de tareas de estudio con el material integrado.</strong><br>
  Aplicación de escritorio local, de un solo usuario. Sin cuentas, sin servidor, sin nube.</p>
  <p>
    <code>v0.1.0</code> ·
    <code>Python ≥ 3.12</code> ·
    <code>PySide6 6.11.2</code> ·
    <code>SQLite</code> ·
    <code>Linux</code>
  </p>
</div>

---

## Tabla de contenido

- [La idea](#la-idea)
- [Instalación](#instalación)
- [Cómo se usa](#cómo-se-usa)
- [Atajos](#atajos)
- [Material que entiende](#material-que-entiende)
- [Conteo de tiempo](#conteo-de-tiempo)
- [Dónde viven los datos](#dónde-viven-los-datos)
- [Desarrollo](#desarrollo)
- [Estado de v0.1](#estado-de-v01)
- [Documentación](#documentación)

---

## De un vistazo

| | |
|---|---|
| **Qué es** | Aplicación de escritorio para gestionar tareas de estudio junto con el material que hay que estudiar |
| **Para quién** | Una persona, en su propio equipo. No hay usuarios, permisos ni roles |
| **Privacidad** | Nada sale del equipo: no hay peticiones de red salvo las que tú abras (un enlace web, un video de YouTube) |
| **Lenguaje** | Python ≥ 3.12 — el entorno actual corre 3.14 |
| **Interfaz** | PySide6 6.11.2, tema oscuro propio |
| **Persistencia** | SQLite de la biblioteca estándar, modo WAL, migraciones propias |
| **Lectura de PDF** | pypdf 6.16.2 |
| **Herramientas** | uv · pytest 8.4.2 · pytest-qt 4.5.0 · ruff 0.14.4 |

---

## La idea

> Cuando el usuario se sienta a estudiar, no debe tener que preparar nada: el material
> correcto ya está abierto delante de él.

De ese principio salen las cuatro decisiones que definen la aplicación:

| Decisión | Qué significa en la práctica |
|---|---|
| El material se importa **una vez** | Se copia dentro de una biblioteca interna, indexada por hash: el mismo archivo dos veces no ocupa el doble |
| Se parte en **secciones** | Capítulos de un libro, tramos de un video. El seccionado sale de los marcadores del PDF o del índice del EPUB, y se puede corregir a mano |
| Las tareas **apuntan** a secciones, no adjuntan archivos | Abrir una tarea abre su material ya servido y en orden |
| El tiempo **se cuenta solo** | Y solo se reporta el que se midió: el historial nunca estima |

Cuando apruebas un examen, su temario se archiva: deja de aparecer en el circuito activo
pero sigue consultable. El material tiene un ciclo de vida con final.

---

## Instalación

Requisitos: Linux con entorno de escritorio, Python 3.12 o superior y
[uv](https://docs.astral.sh/uv/).

```bash
git clone <este-repo> && cd proyecto_kiro
uv sync
uv run python -m stou      # o bien: uv run stou
```

No hay que crear ninguna base de datos ni configurar nada: al primer arranque la
aplicación crea su carpeta de datos y aplica sus migraciones.

### Lanzador de escritorio

Para abrir la aplicación con doble clic, sin pasar por la consola:

```bash
uv run python packaging/install_desktop_entry.py --shortcut
```

Instala tres cosas, todas dentro de `$HOME` y sin permisos de administrador:

```
~/.local/share/applications/stou.desktop          entrada del menú de aplicaciones
~/.local/share/icons/hicolor/<n>x<n>/apps/stou.*  el ícono en el tema del sistema
~/Escritorio/STOU.desktop                         copia en el escritorio (--shortcut)
```

El instalador apunta al intérprete de `.venv`, así que **si mueves el proyecto de carpeta
hay que volver a correrlo**. Para quitarlo todo: `--uninstall`.

---

## Los primeros cinco minutos

La aplicación arranca vacía y la propia pantalla de Inicio te lleva de la mano, un paso a
la vez. El recorrido completo es este:

1. **Crea una materia.** Es una categoría, y admite subtemas anidados.
2. **Sube material** con `Ctrl+I`: un PDF, un EPUB, un video, o pega un enlace.
3. **Revisa las secciones.** Si el PDF traía marcadores o el EPUB su índice, ya están los
   capítulos; si no, se crean por tramos o a mano.
4. **Crea una tarea** con `Ctrl+N` y asígnale las secciones que toca estudiar, en orden.
5. **Estudia.** Al abrir la tarea se abre el material y el contador empieza solo. Marca
   cada sección con `Ctrl+Intro`.
6. **Registra el examen.** Si lo apruebas, su temario se archiva.

A partir de ahí, Inicio deja de dar instrucciones y empieza a responder qué toca ahora.

---

## Cómo se usa

La navegación tiene cinco destinos y su orden cuenta una historia:

```
Inicio   →   Tareas   →   Biblioteca   →   Calendario   →   Historial
qué hago     el           el material      cuándo          qué hice
ahora        trabajo
```

**Inicio** responde a una sola pregunta: qué hacer ahora.

- La primera vez muestra tres pasos con **un solo botón a la vez**: crear una materia,
  subir material, crear la primera tarea.
- Después muestra la tarea que toca (la que está en progreso, o la más urgente), tus
  pendientes ordenados por urgencia, y tu ritmo: tiempo de hoy, de la semana, racha y el
  reparto por materia.

**Biblioteca** es el árbol de materias y su material: importar archivos, agregar enlaces,
crear notas, seccionar, archivar.

**Modo estudio** se abre desde una tarea: el visor del material a la izquierda, las
secciones y las notas al lado, y el contador corriendo. Una tarea puede llevar su
**solución** adjunta, que queda oculta hasta que la pides: consultarla antes de intentarlo
no es estudiar.

**Historial** fue la puerta de entrada y dejó de serlo — un tablero de cifras no le dice a
nadie qué hacer. Ahora va al final: tiempo por materia y por día, racha, atrasos y avance.

Ninguna lista aparece vacía sin explicación: cada estado vacío dice para qué sirve esa
pantalla y ofrece la acción que corresponde.

---

## Atajos

| Atajo | Qué hace |
|---|---|
| `Ctrl+1` … `Ctrl+5` | Ir a Inicio, Tareas, Biblioteca, Calendario, Historial |
| `Ctrl+N` | Nueva tarea, desde cualquier pantalla |
| `Ctrl+I` | Subir material |
| `Ctrl+F` | Enfocar el buscador de la vista actual (busca por título; buscar *dentro* del material está pendiente) |

Dentro del modo estudio:

| Atajo | Qué hace |
|---|---|
| `F11` | Modo sin distracciones: esconde todo menos el material |
| `Ctrl+Intro` | Marcar la sección actual como estudiada |
| `Ctrl+W` | Cerrar el modo estudio |

---

## Material que entiende

| Tipo | Formatos | Seccionado automático |
|---|---|---|
| PDF | `pdf` | Sí, por los marcadores del documento |
| Libro | `epub` | Sí, por el índice |
| Video | `mp4` `mkv` `webm` `avi` `mov` | Por duración, en tramos |
| Audio | `mp3` `m4a` `wav` `ogg` `flac` `opus` | Por duración, en tramos |
| Imagen | `png` `jpg` `jpeg` `gif` `bmp` `webp` `svg` | No aplica |
| Nota | `md` `txt`, o escrita dentro de la aplicación | No aplica |
| Enlace | Página web, y YouTube con el reproductor oficial embebido | No aplica |

Todo lo importado se copia a la biblioteca interna con el nombre de su hash de contenido.
El original queda donde estaba; borrarlo no rompe nada.

---

## Conteo de tiempo

La regla completa está en [docs/TIME_TRACKING.md](docs/TIME_TRACKING.md). En corto:

**El contador avanza mientras haya interacción reciente (umbral de 5 minutos) _o_ mientras
un medio esté reproduciéndose.**

La segunda condición no es un detalle: sin ella, ver un video de 40 minutos sin tocar el
teclado se registraría como 5. Cuando ninguna de las dos se cumple, la sesión se pausa por
inactividad y el tiempo deja de sumar.

El historial solo suma sesiones medidas. Nunca rellena huecos con estimaciones.

---

## Dónde viven los datos

La carpeta se resuelve en este orden: `$STOU_DATA_DIR`, luego `$XDG_DATA_HOME/stou`, y si
ninguna está definida, `~/.local/share/stou`. Definir `STOU_DATA_DIR` es la forma cómoda
de probar con datos desechables:

```
stou.db        base SQLite en modo WAL, con migraciones propias
library/       copias internas del material, por hash de contenido
cache/epub/    libros descomprimidos para leer
```

Todo el tiempo se guarda en UTC y se convierte a hora local solo al mostrarlo. Los
identificadores son UUIDv7: ordenables por tiempo y aptos para una sincronización futura.

Para empezar de cero basta borrar esa carpeta: no hay estado en ningún otro sitio, aparte
del lanzador de escritorio si lo instalaste.

---

## Desarrollo

```bash
uv run pytest                    # 90 pruebas, incluye las de arquitectura
uv run ruff check src tests
```

Las pruebas de Qt corren sin pantalla (`QT_QPA_PLATFORM=offscreen` se fija en
`tests/conftest.py`), así que funcionan por SSH o en CI.

### Arquitectura

Clean Architecture con cuatro capas, un kernel compartido y un composition root. Las
dependencias apuntan **hacia adentro** y nunca al revés:

```
shared          sin dependencias, solo stdlib
domain          depende de shared
application     depende de domain, shared
infrastructure  depende de application, domain, shared
presentation    depende de application, domain, shared
composition     depende de todas — es el único que puede
```

Las cinco reglas que no se negocian, todas verificadas por `tests/test_architecture.py`:

1. Las dependencias apuntan hacia adentro.
2. `PySide6` solo en `presentation` y `composition`; `sqlite3` y `pypdf` solo en
   `infrastructure`.
3. El dominio no lee el reloj: el tiempo entra por argumento o por `Clock`.
4. Los eventos se publican **después** del commit, nunca antes.
5. La presentación recibe DTOs, nunca entidades de dominio ni repositorios.

El detalle normativo está en [ARCHITECTURE.md](ARCHITECTURE.md).

### Estructura del repositorio

```
src/stou/
├── __main__.py       entrypoint: python -m stou
├── shared/           EntityId (UUIDv7), Clock
├── domain/           entidades, value objects, eventos, puertos de repositorio
├── application/      casos de uso, DTOs, seccionado, métricas, períodos
├── infrastructure/   SQLite, blob store, inspección de contenido, bus de eventos
├── presentation/     AppServices, vistas Qt, widgets, tema
└── composition/      cableado de dependencias y suscripciones
tests/                una carpeta por capa, más test_architecture.py
packaging/            instalador del lanzador de escritorio
docs/                 un módulo de documentación por tema
```

Convención de idioma: nombres de dominio **en inglés** en el código, textos de interfaz
**en español**.

---

## Estado de v0.1

Funcional de punta a punta: importar un libro, partirlo en capítulos, crear una tarea que
apunte a tres de ellos, estudiarla con el tiempo contándose solo, marcar lo estudiado,
registrar el examen y ver el historial.

### Listo

| Área | Nota |
|---|---|
| Categorías jerárquicas | Materias y subtemas anidados |
| Importar PDF, EPUB, video, audio, imagen, notas | Con copia interna y deduplicación por hash |
| Enlaces web y YouTube embebido | Reproductor oficial dentro de la aplicación |
| Seccionado automático y manual | Marcadores del PDF, índice del EPUB, tramos de tiempo |
| Tareas con material asignado y orden de estudio | Con prioridad, fecha y estado |
| Solución adjunta a la tarea | Oculta hasta que se pide |
| Modo estudio con visor, notas y `F11` | Superficie de lectura en papel para nota, EPUB, PDF e imagen |
| Conteo automático de tiempo | Con pausa por inactividad; ver la regla arriba |
| Calendario de tareas y exámenes | |
| Historial | Tiempo por materia y por día, racha, atrasos, avance, gráfico de 14 días |
| Exámenes | Registro manual, archivado del temario al aprobar, reintento |
| Pantalla de Inicio con puesta en marcha guiada | Un solo botón a la vez hasta que el sistema deja de estar vacío |

### Pendiente

| Área | Situación |
|---|---|
| Búsqueda de texto dentro del material | A medio camino: la tabla FTS5 y el puerto `TextExtractor` existen, falta quien los llene |
| Anotaciones y resaltados persistentes | No empezado; el visor de PDF es el caso difícil |
| Exportar el calendario a `.ics` | No empezado; mejor relación valor/esfuerzo de lo que queda |
| Sincronización entre dispositivos | El modelo de datos está preparado, no hay código |
| Evaluación con LLM | Experimental y sin decidir: choca con «todo local» |
| Empaquetado distribuible (AppImage, instalador) | No empezado; hoy depende del repositorio y su `.venv` |

Orden sugerido y deuda técnica conocida en [docs/ROADMAP.md](docs/ROADMAP.md).

---

## Documentación

[PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) es el punto de entrada: dice qué es el proyecto,
dónde está cada cosa y qué leer según lo que vayas a hacer. De ahí salen los módulos de
`docs/`, uno por tema.

| Documento | Responde a |
|---|---|
| [ARCHITECTURE](ARCHITECTURE.md) | **Normativo.** Capas, regla de dependencia, estructura |
| [AGENT_PLAYBOOK](docs/AGENT_PLAYBOOK.md) | Cómo se trabaja en este repositorio |
| [DOMAIN_MODEL](docs/DOMAIN_MODEL.md) | Entidades, value objects e invariantes |
| [APPLICATION_SURFACE](docs/APPLICATION_SURFACE.md) | Todo lo que la aplicación sabe hacer |
| [EVENTS](docs/EVENTS.md) | Qué eventos hay y quién reacciona |
| [TIME_TRACKING](docs/TIME_TRACKING.md) | La regla exacta del conteo de tiempo |
| [DATA_AND_STORAGE](docs/DATA_AND_STORAGE.md) | Esquema, migraciones, biblioteca de archivos |
| [CONTENT_PIPELINE](docs/CONTENT_PIPELINE.md) | Importar, seccionar y visualizar material |
| [UI_MAP](docs/UI_MAP.md) | Pantallas, atajos y estilo |
| [TESTING](docs/TESTING.md) | Qué se prueba, cómo y con qué fixtures |
| [CONVENTIONS](docs/CONVENTIONS.md) | Estilo, nombres, tipado, manejo de errores |
| [DECISIONS](docs/DECISIONS.md) | Por qué está así |
| [ROADMAP](docs/ROADMAP.md) | Qué falta y qué va a doler |
| [GLOSSARY](docs/GLOSSARY.md) | Qué significa cada palabra |
| [DOCS_GUIDE](docs/DOCS_GUIDE.md) | Cómo mantener esta documentación |
