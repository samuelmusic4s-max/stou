# UI_MAP

Las pantallas de STOU, cómo se navega entre ellas, qué atajos existen y con qué piezas
están construidas.

> **Módulo** UI_MAP · **Fuente** `src/stou/presentation/` · **Verificado en** `c97ac40`

---

## 1. La idea que ordena la interfaz

La navegación tiene cinco destinos y su orden cuenta una historia:

```
Inicio  →  Tareas  →  Biblioteca  →  Calendario  →  Historial
qué hago    el         el material     cuándo        qué hice
ahora      trabajo
```

El Dashboard fue la puerta de entrada y dejó de serlo: **un tablero de cifras no le dice
a nadie qué hacer.** Pasó al final, renombrado «Historial», y su lugar lo ocupó Inicio,
que responde una sola pregunta.

Tres reglas que atraviesan todas las pantallas:

- **Ninguna lista aparece vacía sin explicación.** Cada estado vacío dice para qué sirve
  esa pantalla y ofrece la acción que corresponde.
- **Una acción principal a la vez.** Durante la puesta en marcha se muestra un solo
  botón: crear materia, luego subir material, luego crear la primera tarea.
- **Las vistas se refrescan por evento**, no llamándose entre ellas.

---

## 2. Las pantallas

### Inicio — `views/home_view.py`

Responde dos preguntas y nada más: **qué toca ahora** y **cómo voy**. Tres bloques, en
este orden:

1. **La banda de lo siguiente.** Una fila, no una caja alta: glifo, tarea, sus datos en
   una línea y la acción a la derecha. Toda la banda es clicable.
2. **Pendientes.** Cinco filas ordenadas por urgencia. Cada fila aprovecha el ancho —
   avance del material, tiempo dedicado y fecha, en columnas de ancho fijo para que
   queden a plomo entre filas. El total va en el subtítulo y la lista completa en Tareas.
3. **Tu ritmo.** Tres cifras sueltas, el gráfico de catorce días y el reparto por
   materia, todo en una sola tarjeta.

Dos decisiones de tamaño: se muestran **cinco** pendientes (`VISIBLE_PENDING`) y la
materia lleva tiempo y capítulos en la misma línea, porque la pantalla tiene que caber de
una vez a 1080p — si hay que desplazarse, deja de servir para decidir de un vistazo.

La guía de puesta en marcha solo aparece cuando el sistema está de verdad vacío. La
lógica de qué tarea proponer no está aquí, está en el caso de uso
([`APPLICATION_SURFACE.md`](APPLICATION_SURFACE.md) §10). La vista solo pinta.

Señales: `studyRequested(task_id)`, `navigateRequested(clave)`, `importRequested()`,
`newTaskRequested()`, `newCategoryRequested()`.

### Tareas — `views/tasks_view.py`

Lista filtrable de tareas con su material asignado, progreso y tiempo dedicado. Desde
aquí se crean, editan, reprograman, se les asigna material y se entra a estudiar.
Señales: `studyRequested(task_id)`, `importRequested()`.

### Biblioteca — `views/library_view.py`

Árbol de materias a la izquierda, material a la derecha. Importar archivos, agregar
enlaces, crear notas, seccionar, archivar. Señal: `openMaterialRequested(material_id,
posición)`.

### Calendario — `views/calendar_view.py`

Mes con tareas y exámenes por día local, desde `GetCalendarMonth`. Señal:
`studyRequested(task_id)`.

### Historial — `views/dashboard_view.py`

Tiempo por materia y por día, tareas completadas, atrasos, próximos exámenes, avance y
racha, con selector de período (`today`, `week`, `month`, `last30`). El período lo
resuelve el caso de uso, no la vista. Señal: `studyRequested(task_id)`.

### Modo estudio — `views/study_view.py`

Ventana aparte, no una pestaña. Está construida alrededor de una idea: cuando el usuario
se sienta, lo único que debe ver es su material. El cronómetro es la segunda pieza más
visible porque es la prueba de que el trabajo quedó registrado; todo lo demás se esconde
con F11.

Contiene la lista de material de la tarea, el visor, un panel de notas, y el conteo de
tiempo con un tick cada 5 segundos. Al cerrarse cierra la sesión y emite
`sessionFinished(task_id, segundos)`, que la ventana principal traduce a un aviso en la
barra de estado.

### Visor suelto — `views/viewer_window.py`

Abrir un material sin estudiar una tarea: consultar algo sin arrancar el cronómetro.

---

## 3. Atajos

### Globales (ventana principal)

| Atajo | Acción |
|---|---|
| `Ctrl+1` … `Ctrl+5` | Inicio, Tareas, Biblioteca, Calendario, Historial |
| `Ctrl+N` | Nueva tarea (desde cualquier parte) |
| `Ctrl+I` | Subir material |
| `Ctrl+F` | Enfocar el buscador de la vista actual |

`Ctrl+N` e `Ctrl+I` no abren un diálogo suelto: navegan a la vista que corresponde y
lanzan la acción allí, para que el usuario sepa dónde quedó lo que creó.

### En modo estudio

| Atajo | Acción |
|---|---|
| `F11` | Modo sin distracciones |
| `Ctrl+Intro` | Marcar la sección actual como estudiada |
| `Ctrl+W` | Cerrar la ventana (cierra la sesión) |

---

## 4. Cómo está cableada la capa

```
AppServices  ──►  vistas        casos de uso + UiEvents, nada más
UiEvents     ──►  vistas        eventos ya en el hilo de la GUI
run_async    ──►  worker        todo lo que pueda tardar
```

**`AppServices`** (`presentation/services.py`) es un dataclass congelado con un campo por
caso de uso. Es la frontera: una vista que necesita algo pide `self._s.<lo_que_sea>`. No
hay acceso a repositorios ni a la base.

**`UiEvents`** (`qt/events.py`) se suscribe a todo el bus y lo reemite con una señal Qt.
Una vista se suscribe así:

```python
self._s.events.on((TaskCreated, TaskUpdated), lambda _e: self.refresh())
```

**`run_async`** (`qt/worker.py`) manda una función a un hilo del pool y entrega el
resultado en el hilo de la GUI. La regla de la capa es que **la interfaz nunca se
congela**: importar archivos, leer índices o guardar la posición de lectura pasan por
aquí.

**Refresco al navegar:** `MainWindow._show` llama a `refresh()` de la vista que entra, si
lo tiene. Una vista no necesita estar al día mientras está oculta.

---

## 5. Componentes y estilo

### Componentes reutilizables — `widgets/components.py`

`Card`, `SectionHeader`, `ActionCard`, `MetricTile`, `EmptyState`, `StepRow`, `ListRow`,
más ayudas (`label`, `pill`, `divider`, `spacer`).

`ActionCard` tiene dos disposiciones: la alta, para una rejilla de tres, y `compact=True`,
una sola fila para bandas de ancho completo. La alta como banda dejaba un hueco enorme
entre el glifo y el título. Ya no lleva sombra: un `QGraphicsEffect` sobre un widget que
cambia de tamaño es la misma familia de problema que dejó bandas detrás del texto, y el
tema dice que la profundidad se logra por elevación de superficie. El objetivo es que ninguna pantalla
tenga que explicar dos veces cómo se ve una acción, una métrica o un estado vacío.

Los iconos son **glifos monocromos** (`GLYPH`: `◈ ▶ ▤ ◎ ▦ ◔ ↥ ⚯ ✎ ⌂ ★ ◴ ⟡ ○ → ✓`), no
emoji: se ven dibujados, no pegados.

### La superficie de lectura — «papel»

El marco de la aplicación es oscuro; **el material se lee sobre papel**. No es
decoración: leer treinta páginas de texto claro sobre fondo oscuro cansa más que
leerlas sobre papel, y esta aplicación existe para leer treinta páginas. Un PDF además
ya trae páginas blancas, así que el marco casi negro creaba un salto de contraste
violento justo alrededor de lo que se está mirando.

Los tokens viven en `COLORS` con prefijo `paper_*` (hoja, paspartú, tinta, línea,
enlace, selección) y se aplican en tres sitios:

| Visor | Qué recibe |
|---|---|
| Nota | Hoja de papel centrada, con la medida acotada a `READING_MEASURE` (820 px) |
| EPUB | `theme.reading_css()` inyectado en cada documento del libro |
| PDF, imagen | Paspartú cálido alrededor; la página se acota a `PAGE_MEASURE` (1080 px) |

**Sobre el EPUB.** Un EPUB trae la hoja de estilos de su editorial, pensada para una
página de libro y no para una ventana de 1400 px. La inyección arregla tres cosas: la
**medida** (34 em, unos 70 caracteres: una línea de 1400 px hace perder el renglón al
volver), el **papel**, y la **alineación a la izquierda** — muchos EPUB vienen
justificados, y en columna estrecha el justificado abre ríos de espacio en blanco.

Va con `!important` a propósito: las hojas de editorial usan selectores más específicos
(`body p.calibre1`) y ganarían sin eso. Se inyecta con un `QWebEngineScript` en lugar de
reescribir el HTML para no romper las rutas relativas del libro: sus imágenes y fuentes
siguen resolviéndose desde su carpeta.

**Cómo se verifica.** QtWebEngine no pinta sin GPU, así que una captura sin pantalla
sale en blanco y no prueba nada; hay que mirarlo en una pantalla real. Lo que sí cubre
la suite es que el CSS no quede con tokens sin resolver y que papel y tinta contrasten
al menos 4.5:1 (`tests/presentation/test_smoke.py`).

### Gráficos — `widgets/charts.py`

`ActivityChart` (barras de tiempo por día, con hoy marcado y los días en cero
dibujados) y `SubjectBars` / `SubjectRow` (comparar materias por longitud, no leyendo
cifras). Los usan Inicio y el Historial, con los mismos datos de `application/metrics.py`.

### Calendario — `widgets/month_grid.py`

`MonthGrid` sustituye a `QCalendarWidget`, que estiraba las celdas hasta dejar cajones
enormes con un número diminuto, no podía mostrar qué hay cada día, y empezaba la semana
en domingo pintando el fin de semana en rojo —el color de «examen» y «atrasado» en esta
aplicación. La altura de fila está acotada en el widget: el mes ocupa lo que necesita y
devuelve el resto del espacio a la pantalla.

### Diálogos — `widgets/dialogs.py`

`TaskDialog`, `AssignSectionsDialog`, `ExamDialog`, `RecordExamDialog`,
`ManualSessionDialog`, `LinkDialog`, y `category_combo` como selector compartido.

### Tema — `qt/theme.py`

Tres decisiones gobiernan todo lo demás:

1. La jerarquía se construye con **espacio y tamaño**, no con cajas. Un borde por todas
   partes convierte la pantalla en una hoja de cálculo.
2. La profundidad se logra por **elevación de superficie** (fondos cada vez más claros),
   no por líneas.
3. **Un solo acento.** Si todo resalta, nada resalta y el usuario no sabe dónde hacer
   clic.

Tokens: `COLORS` (tema oscuro, acento `#5B8DEF`), `SPACE` (`xs` 4 → `3xl` 48), `TYPE`
(`display` 32 → `caption` 11), `RADIUS`, `MOTION` (`fast` 140, `base` 220, `slow` 360 ms).
Todo margen y separación sale de `SPACE`; nada de números mágicos en las vistas.

Formateo para pantalla: `format_duration`, `format_duration_short`, `format_clock`,
`format_size`, `relative_day`.

### Ícono — `qt/assets/`

Dos SVG y una función. `icon.svg` es un libro abierto sobre el lienzo del tema, con el
lomo en el color de acento como único color. `icon-small.svg` es el mismo libro con menos
renglones y trazo más grueso, para que a 22 px siga leyéndose.

Antes el ícono grande llevaba un anillo de progreso al 72 % alrededor del libro. Se quitó:
un arco incompleto sobre un círculo de fondo es el lenguaje visual de un indicador de
carga, y el ícono se leía como una aplicación que nunca termina de arrancar. El progreso
se muestra dentro de la aplicación, no en su ícono.

`theme.app_icon()` rasteriza cada variante a los tamaños de `ICON_VARIANTS` y devuelve un
`QIcon` con todos ellos; `__main__.py` lo pasa a `setWindowIcon`, que es lo que hace que
la barra de tareas muestre el ícono de STOU y no el genérico de Python. El mismo SVG es el
que usa el lanzador `STOU.desktop` del escritorio.

### Movimiento — `qt/motion.py`

El movimiento no es decoración: explica de dónde viene lo que apareció y a dónde fue lo
que se fue. Reglas: nada por encima de 360 ms, una sola propiedad a la vez (opacidad o
posición) con `OutCubic`, y **nunca bloquea** — si la animación no corre, la interfaz
queda igual de usable.

Funciones: `fade_in`, `rise_in`, `stagger`, `cross_fade`, `pulse`, `count_up`,
`hover_lift`. `is_alive` comprueba que el objeto C++ detrás del envoltorio de Python
todavía exista, que es la causa habitual de un cierre inesperado al animar algo que ya se
cerró.

---

## 6. Las dos trampas de Qt en este proyecto

### Los renglones detrás del texto

Un selector `QWidget { background: … }` en la hoja de estilos pinta también **cada
QLabel**, y una etiqueta que se estira con la ventana dibuja una banda opaca del ancho
de la tarjeta detrás de su texto. Al maximizar, la pantalla se llenaba de renglones.

La regla que queda: **el fondo se declara en la ventana y en las superficies con
nombre, nunca sobre `QWidget`.** Las etiquetas son explícitamente transparentes.

### Los bloques invisibles

`QGraphicsOpacityEffect` guarda un mapa de bits de lo que envuelve. Si el widget cambia
de tamaño con el efecto puesto, se dibuja desactualizado; si la animación no llega a
correr, el widget se queda en opacidad cero y desaparece. Y animar `pos` de un widget
que gobierna un layout es peor: el layout lo recoloca en cada relayout y pelea con la
animación.

`qt/motion.py` ya no anima posiciones y retira el efecto siempre: al terminar, al
cambiar de tamaño (con un filtro de eventos) y por un temporizador de seguridad.

### El botón muerto

`clicked` emite un `bool`. Conectarlo directo a un método que recibe argumentos hace que
ese `bool` entre como primer argumento, el método falle y **Qt se coma la excepción**: un
botón que no hace nada, sin un solo mensaje. Ya pasó una vez.

```python
boton.clicked.connect(lambda: self._crear_tarea())   # sí
boton.clicked.connect(self._crear_tarea)             # no, si acepta argumentos
```

Lo impide `test_ninguna_senal_clicked_conecta_un_metodo_con_argumentos`, que revisa
`clicked`, `toggled`, `triggered` y `pressed` en toda la capa.

### Los errores silenciosos en general

`__main__._install_error_reporting()` instala un `sys.excepthook` que convierte cualquier
excepción no controlada en un `QMessageBox` visible, con el tipo, el mensaje y el final del
traceback. La aplicación sigue abierta. Que ningún fallo quede en silencio es una decisión
de producto, no una comodidad de desarrollo.

---

## 7. Agregar una vista o un widget

1. Vista nueva en `views/`, que reciba `AppServices` en el constructor.
2. Si es un destino de navegación: entrada en `SECTIONS` de `qt/main_window.py`
   (clave, etiqueta, glifo) y en `_build_views`. El atajo `Ctrl+N` sale de la posición.
3. Comunicación hacia arriba por **señal**, nunca llamando a otra vista. El cableado se
   hace en `MainWindow._wire`.
4. Refresco: implementa `refresh()` y suscríbete a los eventos que te afecten.
5. Trabajo que pueda tardar: `run_async`.
6. Espacios y colores desde `SPACE` y `COLORS`.
7. Prueba en `tests/presentation/test_flows.py` (o `test_smoke.py` si solo verificas que
   se construye).
8. Actualiza §2 y §3 de este documento.
