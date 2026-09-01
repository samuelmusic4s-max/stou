# DECISIONS

Las decisiones que dieron forma a STOU, con su motivo y lo que se descartó. Sirve para
responder «¿por qué está así?» sin arqueología en el historial de git.

> **Módulo** DECISIONS · **Fuente** código y comentarios del proyecto · **Verificado en** `c97ac40`

**Nota sobre el origen.** Las decisiones D-01 a D-14 se reconstruyeron leyendo el código,
sus comentarios y las pruebas de `c97ac40`; no se escribieron en el momento de tomarlas.
Reflejan lo que el proyecto hace hoy y el motivo que el propio código declara. A partir de
D-15, cada decisión se anota cuando se toma.

**Formato.** Una entrada por decisión, numerada y en orden. No se reescriben ni se borran:
si una decisión se revierte, se añade una nueva que la reemplaza y se marca la anterior
como *superada por D-NN*. El valor de este archivo es el rastro, no la foto.

---

## D-01 · Aplicación local de un solo usuario

**Decisión.** Sin cuentas, sin servidor, sin sincronización. Todo en el disco del usuario.

**Por qué.** El producto es una herramienta de estudio personal. Un servidor introduce
autenticación, privacidad de material posiblemente con derechos de autor, costos y una
dependencia de red que rompe el caso de uso central: sentarse a estudiar.

**Consecuencia.** No hay capa de red que probar ni proteger, y el material del usuario
nunca sale de su máquina. El modelo de datos sí se dejó preparado para sincronizar
(ver D-06).

---

## D-02 · Clean Architecture con cuatro capas, verificada por pruebas

**Decisión.** `shared → domain → application → {infrastructure, presentation} →
composition`, con la regla de dependencia comprobada por `tests/test_architecture.py`.

**Por qué.** Cuatro capas son más ceremonia de la que una aplicación de escritorio
necesita, en apariencia. El motivo real es que el proyecto va a mutar: cambiar de Qt a otra
interfaz, o de SQLite a otro motor, no debería tocar una sola regla de negocio. Y una
arquitectura que solo vive en un documento se degrada en semanas.

**Lo descartado.** Estructura por características (`features/tasks/…`): más cómoda al
principio, pero la lógica de negocio y el SQL acaban conviviendo en el mismo archivo.

**Consecuencia.** Hay que tocar tres archivos para agregar un caso de uso. En cambio, el
dominio se prueba sin base de datos y sin pantalla, y la degradación falla en CI en lugar
de descubrirse tarde.

---

## D-03 · La sección, no el material, es la unidad de trabajo

**Decisión.** Las tareas apuntan a secciones. Importar un material lo parte
automáticamente en secciones.

**Por qué.** «Estudiar el libro» no es una tarea ejecutable; «estudiar el capítulo 4» sí.
Y el progreso solo se puede medir sobre unidades que se completan.

**Consecuencia.** Todo material importado tiene al menos una sección, incluso si no hay
índice aprovechable (`single_section`). Sin eso, un video sin capítulos no podría asignarse
a una tarea.

---

## D-04 · El material se copia a una biblioteca interna, direccionada por contenido

**Decisión.** `BlobStore` guarda cada archivo con su SHA-256 como nombre.

**Por qué.** Referenciar la ruta original hace que la biblioteca se rompa cuando el usuario
reorganiza sus carpetas. El hash resuelve además la deduplicación y las colisiones de
nombres de un golpe.

**Lo descartado.** Guardar rutas y avisar cuando falten. Traslada al usuario un problema
que el programa puede evitar.

**Consecuencia.** El disco se duplica: el material vive dos veces si el usuario conserva el
original. Se aceptó a cambio de una biblioteca que no se rompe.

---

## D-05 · Migraciones propias, solo hacia adelante

**Decisión.** Una lista de pares `(versión, sql)` en `persistence/schema.py`. Solo se
agrega al final; nunca se edita una migración publicada.

**Por qué.** Un ORM con migraciones automáticas sería una dependencia grande para un
esquema de nueve tablas. Editar una migración ya aplicada produce esquemas divergentes
entre la máquina del desarrollador y la de un usuario con datos previos, y el síntoma
aparece semanas después.

**Consecuencia.** El SQL se escribe a mano y se lee entero de un vistazo.

---

## D-06 · UUIDv7 en texto como identificadores

**Decisión.** Identificadores generados localmente, ordenables por tiempo de creación,
guardados como texto.

**Por qué.** Un autoincremental impide fusionar datos de dos dispositivos, y esa puerta se
quería dejar abierta (D-01). UUIDv7 además ordena por creación, lo que ahorra un `ORDER BY`
en varias consultas.

**Consecuencia.** Claves de 36 caracteres en vez de un entero. Irrelevante a esta escala.

---

## D-07 · El conteo de tiempo tiene dos condiciones, no una

**Decisión.** El tiempo cuenta si hay interacción reciente (umbral de 5 minutos) **o** si
un medio está reproduciéndose.

**Por qué.** Con solo la primera condición, un video de 40 minutos visto sin tocar el
teclado se registraría como 5. Con solo la ventana abierta, una cena de una hora contaría
como estudio. Las dos formas de mentir importan por igual.

**Consecuencia.** `tick()` es la lógica más compleja del dominio y necesitó su propio
documento ([`TIME_TRACKING.md`](TIME_TRACKING.md)) y siete pruebas dedicadas.

---

## D-08 · El dashboard nunca estima

**Decisión.** Solo se suman sesiones medidas. No se infiere tiempo a partir de tareas
completadas.

**Por qué.** Una cifra que mezcla medición con estimación no se puede interpretar. El
usuario deja de confiar en ella y vuelve a apuntar su tiempo aparte, que es justo el
trabajo que STOU debería quitarle.

**Consecuencia.** Si el usuario estudió sin la aplicación abierta, debe registrarlo a mano
(`AddManualSession`), y esa sesión queda marcada como manual.

---

## D-09 · El reloj se inyecta

**Decisión.** `Clock` como puerto, `SystemClock` en producción, `FixedClock` en pruebas. El
dominio no llama a `datetime.now()`, y una prueba lo verifica.

**Por qué.** Sin esto, probar la pausa por inactividad exigiría esperar cinco minutos, y
probar una racha de siete días sería imposible.

**Consecuencia.** Un argumento `now` recorre casi toda la capa de dominio. Es ruido visual
a cambio de que todo el comportamiento temporal sea determinista.

---

## D-10 · Bus de eventos en memoria, síncrono, con errores aislados

**Decisión.** Los casos de uso publican hechos; los suscriptores reaccionan. Un suscriptor
que falla no tumba al publicador.

**Por qué.** Sin bus, importar un material acabaría conociendo el dashboard, la biblioteca,
el inicio y la barra de estado. Con bus, agregar un consumidor no toca al productor.

**Lo descartado.** Bus asíncrono con cola: complejidad innecesaria para una aplicación de
un solo usuario donde ninguna reacción es costosa.

**Consecuencia.** Un `print` de más en un suscriptor no rompe una importación, pero un
suscriptor puede fallar en silencio. De ahí la regla de que la lógica esencial nunca vive
en un suscriptor.

---

## D-11 · Los eventos se publican después del commit

**Decisión.** `commit_and_publish` hace commit y solo entonces publica.

**Por qué.** Publicando antes, un suscriptor podría leer un estado que después se revierte
por un error, y actuar sobre algo que nunca ocurrió.

**Consecuencia.** Las entidades registran eventos (`record`) pero no publican; el caso de
uso los recoge con `pull_events()`. Hay una prueba dedicada
(`test_los_eventos_se_publican_despues_del_commit`).

---

## D-12 · Aprobar un examen archiva su temario

**Decisión.** Registrar un examen aprobado archiva las secciones del temario: salen del
circuito activo pero siguen consultables.

**Por qué.** El material de estudio tiene un final. Sin archivado, la biblioteca crece
indefinidamente y las sugerencias se llenan de cosas ya superadas hace un semestre.

**Consecuencia.** El examen deja de ser un registro pasivo y se vuelve el mecanismo que
cierra el ciclo de vida del material. Reprobar mantiene todo activo y habilita un reintento
que hereda el temario.

---

## D-13 · Inicio desplazó al Dashboard como puerta de entrada

**Decisión.** La aplicación abre en Inicio, que responde «qué hago ahora». El Dashboard pasó
al final de la navegación, renombrado «Historial».

**Por qué.** Un tablero de cifras no le dice a nadie qué hacer. Abrir en métricas obliga al
usuario a decidir antes de haber empezado.

**Consecuencia.** `GetHomeOverview` concentra una regla de decisión explícita (puesta en
marcha → en progreso → más urgente → más antigua) y una guía de tres pasos con un solo
botón visible a la vez.

---

## D-14 · Que ningún fallo quede en silencio

**Decisión.** `sys.excepthook` convierte cualquier excepción no controlada en un aviso
visible, y una prueba de arquitectura prohíbe el patrón de conexión que produce botones
muertos.

**Por qué.** Qt atrapa las excepciones dentro de un slot: escribe el traceback en la
consola y sigue como si nada. Para el usuario eso es un botón que no hace nada y ni un
mensaje. Ya ocurrió con «Nueva tarea» (commit `c97ac40`).

**Consecuencia.** Los fallos son ruidosos. Es intencional: un error visible se arregla, uno
silencioso se acumula.

---

## D-15 · La solución de una tarea es un ítem con otro rol

**Decisión.** Una tarea puede llevar su solución. Se guarda como un `TaskItem` más, con
`role = solution`, no como entidad ni tabla aparte.

**Por qué.** Estudiar con el solucionario delante no es estudiar. Hacía falta que la
respuesta estuviera *dentro* de la tarea —para no buscarla cuando toca corregir— pero
separada del enunciado, para que el modo estudio no la abra por su cuenta.

**Lo descartado.** Una entidad `Solution` propia: comparte todo con el material asignado
(archivo, sección, orden) y solo cambia para qué sirve. Y un campo booleano en la tarea:
no admitiría más de una solución ni soluciones por capítulo.

**Consecuencia.** El progreso de la tarea cuenta solo `material_items`; si contara la
solución, una tarea nunca llegaría al 100 %. En el modo estudio la solución vive detrás
de un botón que dice cuántas hay y recuerda intentarlo antes.

---

## D-16 · Paleta cálida y el fondo fuera de `QWidget`

**Decisión.** El lienzo deja de ser casi negro y pasa a una pizarra con calidez, con
texto blanco cálido y dos acentos con trabajos distintos: índigo para «esto se pulsa»,
ámbar para «esto es tiempo». Y el fondo se declara solo en la ventana y en superficies
con nombre, nunca sobre `QWidget`.

**Por qué.** Lo segundo era un fallo de verdad: un fondo sobre `QWidget` alcanza a cada
`QLabel`, que al estirarse dibuja una banda detrás de su texto. Al maximizar, la
aplicación se llenaba de renglones. Lo primero es comodidad y carácter: un negro puro
contra texto claro cansa a las once de la noche, que es cuando esta aplicación se usa, y
hace que cualquier interfaz parezca la misma.

**Consecuencia.** Cada superficie nueva tiene que declarar su fondo explícitamente. En
cambio ninguna etiqueta vuelve a pintar una caja que nadie pidió.

---

## D-17 · El material se lee sobre papel, el marco sigue oscuro

**Decisión.** La aplicación mantiene su marco oscuro, pero toda superficie donde se lee
material —nota, EPUB, PDF, imagen— pasa a papel cálido con tinta oscura, y la columna
de texto se acota a unos 70 caracteres.

**Por qué.** Un tema oscuro total es cómodo para navegar y malo para leer largo. Y era
incoherente: un PDF ya trae páginas blancas, así que el marco casi negro solo añadía un
salto de contraste alrededor de lo que se está leyendo. La medida importa igual que el
color: una línea de 1400 px hace perder el renglón al volver.

**Lo descartado.** Un interruptor claro/oscuro global: duplica el trabajo de tema y no
resuelve el problema real, que no es la aplicación sino el texto largo.

**Consecuencia.** Hay dos paletas que mantener, y los estilos del papel no pueden
heredar de los del marco. A cambio, el EPUB deja de depender de la hoja de su editorial
y todo el material se lee igual, venga de donde venga.

---

## D-18 · El lanzador se instala; no es un archivo suelto en el Escritorio

**Decisión.** La integración con el escritorio la hace un instalador,
`packaging/install_desktop_entry.py`: escribe `stou.desktop` en
`~/.local/share/applications`, rasteriza el ícono dentro del tema `hicolor` bajo el
nombre `stou`, y refresca las cachés del sistema. La aplicación, por su parte, declara
`app.setDesktopFileName("stou")`.

**Por qué.** El escritorio empareja una ventana con su lanzador por el nombre del
archivo `.desktop`, y solo lo busca en los directorios estándar. Sin declararlo, Qt
anunciaba el del intérprete (`_KDE_NET_WM_DESKTOP_FILE = "python3"`): no existe
`python3.desktop`, no había nada que resolver, y la barra de tareas mostraba el ícono de
«aplicación desconocida». Un `.desktop` que vive solo en el Escritorio abre la
aplicación, pero es invisible para ese emparejamiento.

**Lo descartado.** Seguir con `Icon=` apuntando a la ruta absoluta del SVG: funciona en
el lanzador, pero deja de resolver si el proyecto cambia de carpeta, y el nombre del
tema de íconos es lo que consultan las demás superficies. También se descartó instalar
en `/usr/share`: la aplicación es de un solo usuario y no tiene por qué pedir permisos
de administrador.

**Consecuencia.** Mover el proyecto de carpeta ya no obliga a editar un archivo a mano,
pero sí a volver a correr el instalador, porque el `Exec` guarda la ruta del intérprete
del entorno.

**Corolario: la copia del Escritorio no sirve para anclar a la barra de tareas.** Si se
arrastra `~/Escritorio/STOU.desktop` al panel, Plasma guarda el anclaje como
`file:///home/…/Escritorio/STOU.desktop`, mientras que la ventana se anuncia como
`stou` y Plasma la resuelve contra `~/.local/share/applications/stou.desktop`. Son dos
identidades distintas para el mismo programa, así que aparecen dos íconos: el anclado y
el de la ventana abierta. Se ancla desde el menú de inicio o con clic derecho sobre la
ventana ya abierta; la copia del Escritorio es solo para el doble clic.

**Corolario: el nombre de instancia se declara con `RESOURCE_NAME`.** En X11 la ventana
lleva un par `WM_CLASS` (instancia, clase). La clase sale de `setApplicationName`, pero
la instancia la deduce Qt del nombre del programa, y con `python -m stou` eso era
`__main__.py`. `_claim_window_identity()` en `__main__.py` pone `RESOURCE_NAME=stou`
antes de crear la `QApplication`, y el par queda `("stou", "STOU")`, que es lo que
esperan tanto `StartupWMClass` como cualquier escritorio que no lea
`_KDE_NET_WM_DESKTOP_FILE`.

---

## Plantilla para la siguiente

```markdown
## D-19 · Título en una línea

**Decisión.** Qué se hará.

**Por qué.** El problema que resuelve.

**Lo descartado.** Alternativas consideradas y por qué no. (Opcional pero recomendable.)

**Consecuencia.** Qué se vuelve más fácil y qué más difícil.
```
