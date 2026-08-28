# Documento de Requisitos

## Introducción

STOU es una aplicación de escritorio para una sola persona que reúne en un mismo
lugar lo que debe estudiar, el material con el que va a estudiarlo y el registro
de lo que ya estudió. No es un gestor de tareas al que se le adjuntan archivos:
es un espacio de estudio donde la tarea y su material son la misma cosa.

El usuario ingresa su material una vez (libros en PDF, EPUBs, videos, páginas
web, imágenes, notas propias), lo divide en secciones manejables, y define tareas
que apuntan a esas secciones. Cuando llega el momento de estudiar, abre la tarea y
recibe todo el material servido y ordenado, sin buscar archivos ni cambiar de
aplicación. El tiempo se cuenta solo mientras trabaja.

Todo ocurre localmente en el dispositivo del usuario. No hay cuentas, servidor ni
sincronización en esta versión, pero el modelo de datos se diseña para admitir
interconexión entre dispositivos más adelante.

**Principio rector:** "Cuando el usuario se sienta a estudiar, no debe tener que
preparar nada: el material correcto ya está abierto delante de él."

---

## Identidad y límites del producto

- STOU organiza y sirve material de estudio. No lo genera ni lo resume por
  iniciativa propia.
- La unidad de valor de STOU es una sesión de estudio que empieza sin fricción y
  queda registrada, no una lista de tareas administrada.
- El material tiene un ciclo de vida con final: se estudia, se evalúa y se
  archiva. STOU no acumula material activo indefinidamente.
- STOU es de un solo usuario y funciona sin conexión, salvo el material que por
  naturaleza es remoto.
- STOU no reemplaza al criterio del usuario para decidir qué estudiar. Muestra
  qué está pendiente y qué queda cerca en el calendario.

---

## Prioridades del producto

1. Ingesta de material y seccionado en unidades estudiables.
2. Tareas de estudio que apuntan a secciones concretas de material.
3. Modo de estudio que sirve todo el material de la tarea en una interfaz cómoda.
4. Registro automático del tiempo dedicado, atribuido por categoría.
5. Calendario de actividades y exámenes.
6. Dashboard de lo realizado y de lo que viene.
7. Ciclo de vida del material regido por exámenes.
8. Exportación e interconexión entre dispositivos como capacidades posteriores.

---

## Glosario

- **STOU**: La aplicación de escritorio descrita en este documento.
- **Biblioteca**: Conjunto de todo el material que el usuario ha ingresado a
  STOU, gestionado internamente por la aplicación.
- **Material**: Una unidad de contenido de la Biblioteca. Puede ser un documento,
  un libro, un video, una página web, una imagen o una Nota.
- **Seccion**: Fragmento delimitado de un Material que constituye una unidad
  estudiable, por ejemplo un capítulo de un libro o un intervalo de un video.
- **Copia_Interna**: Archivo almacenado por STOU dentro de su propio
  almacenamiento, independiente de la ubicación original desde la que se importó.
- **Material_Remoto**: Material cuyo contenido reside fuera del dispositivo y
  requiere conexión para consumirse, como un video de YouTube o una página web.
- **Nota**: Material creado dentro de STOU con texto enriquecido.
- **Categoria**: Nodo de una jerarquía definida por el usuario que clasifica
  tareas y material, por ejemplo Matemáticas > Cálculo I > Derivadas.
- **Tarea**: Unidad de trabajo del usuario, con Estado, Categoria y un conjunto de
  Secciones o Materiales asignados.
- **Estado**: Situación de una Tarea dentro de un conjunto fijo definido por STOU.
- **Modo_Estudio**: Espacio de trabajo que se abre al iniciar una Tarea y presenta
  todo su material asignado.
- **Sesion_Estudio**: Intervalo registrado de trabajo sobre una Tarea, con
  Tiempo_Efectivo, Categoria y material consultado.
- **Tiempo_Efectivo**: Tiempo contabilizado a una Sesion_Estudio, excluyendo los
  períodos de Inactividad.
- **Inactividad**: Ausencia de interacción del usuario y de reproducción de medios
  durante más que el Umbral_Inactividad.
- **Umbral_Inactividad**: Duración configurable tras la cual STOU deja de
  acumular Tiempo_Efectivo.
- **Examen**: Evaluación asociada a una Categoria y a un conjunto de Secciones,
  con fecha y resultado registrable.
- **Temario**: Conjunto de Secciones que cubre un Examen.
- **Registro_Examen**: Resultado que el usuario asienta sobre un Examen, incluido
  el resultado por Seccion cuando corresponde.
- **Archivado**: Situación de una Seccion o Material que salió del circuito activo
  de estudio pero sigue siendo consultable y buscable.
- **Calendario**: Vista temporal de Tareas con fecha y de Exámenes.
- **Dashboard**: Vista que resume el trabajo realizado y el trabajo próximo.
- **Indice_Busqueda**: Índice local de texto extraído del material, que permite
  búsqueda por contenido.
- **Visor**: Componente que presenta un tipo de Material dentro de STOU.
- **Posicion_Lectura**: Último punto consultado de un Material, como página,
  ubicación de EPUB o instante de video.
- **Respaldo**: Archivo que contiene los datos y el material necesarios para
  restaurar STOU en otro dispositivo.

---

## Requisitos

### Requisito 1: Aplicación local de un solo usuario

**Historia de Usuario:** Como usuario, quiero que STOU funcione en mi computador
sin cuentas ni servicios en la nube, para que mi material y mi progreso sean míos
y estén disponibles sin conexión.

#### Criterios de Aceptación

1. THE STOU SHALL operar como aplicación de escritorio de un solo usuario sin
   requerir registro, autenticación ni servicio remoto.
2. THE STOU SHALL almacenar todos los datos y el material en el dispositivo del
   usuario.
3. WHILE el dispositivo no tiene conexión, THE STOU SHALL permitir usar todas sus
   funciones excepto el consumo de Material_Remoto.
4. THE STOU SHALL identificar cada entidad persistida con un identificador
   estable y único, y SHALL registrar sus marcas de tiempo de creación y
   modificación en UTC.
5. THE STOU SHALL NOT transmitir datos del usuario a servicios externos, salvo la
   comunicación que el propio consumo de Material_Remoto requiere.
6. THE STOU SHALL NOT recolectar telemetría ni estadísticas de uso.

---

### Requisito 2: Biblioteca gestionada internamente

**Historia de Usuario:** Como usuario, quiero que STOU se quede con una copia de
mi material, para que mi biblioteca no se rompa si muevo o borro los archivos
originales.

#### Criterios de Aceptación

1. WHEN el usuario importa un archivo, THE STOU SHALL crear una Copia_Interna en
   su propio almacenamiento y SHALL usar esa copia para todo consumo posterior.
2. WHEN el archivo original cambia de ubicación o se elimina, THE STOU SHALL
   seguir sirviendo el Material sin degradación.
3. THE STOU SHALL calcular un hash del contenido de cada Copia_Interna.
4. WHEN el usuario importa un archivo cuyo hash coincide con un Material
   existente, THE STOU SHALL advertirlo y SHALL permitir cancelar la importación o
   registrarlo como Material distinto.
5. THE STOU SHALL permitir importar varios archivos y carpetas completas en una
   sola operación.
6. WHILE una importación está en curso, THE STOU SHALL mostrar su progreso y SHALL
   permitir cancelarla.
7. WHEN el usuario elimina un Material, THE STOU SHALL advertir qué Tareas y
   Exámenes lo referencian antes de proceder.
8. THE STOU SHALL detectar Copias_Internas faltantes o corruptas y SHALL
   informarlo al usuario indicando qué Material está afectado.
9. THE STOU SHALL registrar para cada Material su origen, fecha de importación,
   tamaño y tipo.

---

### Requisito 3: Tipos de material admitidos

**Historia de Usuario:** Como usuario, quiero meter en STOU cualquier tipo de
material con el que estudio, para no depender de otras aplicaciones.

#### Criterios de Aceptación

1. THE STOU SHALL admitir como Material documentos PDF, libros EPUB, imágenes,
   archivos de video locales, archivos de audio locales, páginas web referenciadas
   por URL, videos de YouTube referenciados por URL y Notas creadas en STOU.
2. THE STOU SHALL presentar todo Material dentro de la propia aplicación y SHALL
   NOT requerir abrir una aplicación externa para consumirlo.
3. WHERE un tipo de archivo no cuenta con un Visor propio, THE STOU SHALL
   registrarlo igualmente como Material, SHALL indicar que no tiene vista previa y
   SHALL permitir abrirlo con la aplicación del sistema.
4. THE STOU SHALL clasificar cada Material en una o más Categorias.
5. THE STOU SHALL permitir asignar etiquetas libres a un Material además de su
   Categoria.
6. THE STOU SHALL conservar y restaurar la Posicion_Lectura de cada Material.

---

### Requisito 4: Seccionado del material

**Historia de Usuario:** Como usuario, quiero partir un libro de 800 páginas en
capítulos, para asignar a una tarea exactamente lo que debo estudiar y no el libro
entero.

#### Criterios de Aceptación

1. THE STOU SHALL permitir dividir un Material en Secciones.
2. WHEN el usuario solicita el seccionado automático de un PDF, THE STOU SHALL
   derivar las Secciones de sus marcadores o de su tabla de contenidos.
3. WHEN el usuario solicita el seccionado automático de un EPUB, THE STOU SHALL
   derivar las Secciones de su tabla de contenidos.
4. IF el Material no contiene información de estructura aprovechable, THEN THE
   STOU SHALL informarlo y SHALL ofrecer el seccionado manual.
5. THE STOU SHALL permitir crear, renombrar, reordenar, dividir, combinar y
   eliminar Secciones manualmente.
6. THE STOU SHALL delimitar una Seccion mediante un intervalo propio del tipo de
   Material: rango de páginas en un PDF, rango de ubicaciones en un EPUB, o
   intervalo de tiempo en un video o audio.
7. THE STOU SHALL permitir corregir manualmente las Secciones generadas de forma
   automática.
8. THE STOU SHALL representar las Secciones de un Material como una estructura
   ordenada que admita al menos dos niveles de anidamiento.
9. WHEN el usuario abre una Seccion, THE STOU SHALL posicionar el Visor en su
   punto de inicio y SHALL indicar visualmente dónde termina.
10. THE STOU SHALL permitir que una Seccion tenga notas y una descripción propias.

---

### Requisito 5: Lectura de documentos extensos

**Historia de Usuario:** Como usuario, quiero abrir un PDF de varios cientos de
megabytes y moverme por él sin esperas, para leer con la misma comodidad que en un
lector dedicado.

#### Criterios de Aceptación

1. THE Visor de PDF SHALL renderizar las páginas por demanda y SHALL NOT cargar el
   documento completo en memoria.
2. WHEN el usuario abre un PDF, THE STOU SHALL mostrar contenido consultable
   dentro de los 3 segundos en el perfil de hardware objetivo.
3. WHEN el usuario navega a otra página de un documento ya abierto, THE STOU SHALL
   presentarla dentro de los 300 milisegundos.
4. THE Visor de PDF SHALL ofrecer navegación por página, zoom, ajuste a ancho y a
   página, panel de miniaturas, panel de tabla de contenidos y búsqueda dentro del
   documento.
5. THE Visor de PDF SHALL permitir crear resaltados y anotaciones persistentes
   asociadas a una página y a una Seccion.
6. THE STOU SHALL conservar los resaltados y anotaciones como datos propios y
   SHALL NOT modificar la Copia_Interna del PDF.
7. THE Visor de EPUB SHALL ofrecer paginación, ajuste de tamaño de letra, tema de
   lectura y navegación por tabla de contenidos.
8. THE Visor de EPUB SHALL permitir resaltados y anotaciones persistentes
   asociadas a una ubicación del texto.
9. IF un documento está protegido, dañado o no puede abrirse, THEN THE STOU SHALL
   explicar la causa y SHALL NOT dejar la interfaz en un estado bloqueado.

---

### Requisito 6: Video de YouTube embebido

**Historia de Usuario:** Como usuario, quiero ver los videos de YouTube que forman
parte de mi material dentro de STOU, para no salir a un navegador y perder el
hilo.

#### Criterios de Aceptación

1. WHEN el usuario agrega una URL de YouTube, THE STOU SHALL registrarla como
   Material_Remoto y SHALL recuperar su título y duración cuando estén
   disponibles.
2. THE STOU SHALL reproducir el video mediante el reproductor embebido oficial de
   YouTube dentro de una vista integrada en la aplicación.
3. THE STOU SHALL NOT descargar ni almacenar localmente el contenido del video.
4. THE STOU SHALL permitir definir Secciones de un video de YouTube como
   intervalos de tiempo, y WHEN el usuario abre una de esas Secciones, THE STOU
   SHALL iniciar la reproducción en su instante de inicio.
5. WHILE el dispositivo no tiene conexión, THE STOU SHALL indicar que el
   Material_Remoto no está disponible y SHALL mantener accesibles sus Secciones,
   notas y metadatos.
6. IF el video no puede reproducirse por indisponibilidad o restricción del
   proveedor, THEN THE STOU SHALL informar la causa al usuario.
7. THE STOU SHALL advertir al usuario que reproducir Material_Remoto implica
   comunicación con servidores del proveedor.

---

### Requisito 7: Video, audio, imágenes y páginas web

**Historia de Usuario:** Como usuario, quiero consumir dentro de STOU el resto de
mi material, para que la aplicación sea el único lugar al que voy a estudiar.

#### Criterios de Aceptación

1. THE STOU SHALL reproducir video y audio locales con controles de reproducción,
   posición, velocidad y volumen.
2. WHEN el usuario reabre un video o audio local, THE STOU SHALL ofrecer retomar
   desde su Posicion_Lectura.
3. THE STOU SHALL permitir definir Secciones de video y audio locales como
   intervalos de tiempo.
4. THE STOU SHALL mostrar imágenes con zoom y desplazamiento.
5. WHEN el usuario agrega una URL de página web, THE STOU SHALL registrarla como
   Material_Remoto y SHALL permitir abrirla en una vista integrada.
6. THE STOU SHALL permitir guardar una copia local del texto de una página web
   para consulta sin conexión.
7. IF un formato de medio no puede reproducirse por falta de códec, THEN THE STOU
   SHALL informarlo indicando el formato afectado.

---

### Requisito 8: Notas enriquecidas

**Historia de Usuario:** Como usuario, quiero escribir mis propias notas dentro de
STOU y vincularlas al material, para que mis apuntes vivan junto a lo que estudié.

#### Criterios de Aceptación

1. THE STOU SHALL permitir crear Notas con texto enriquecido que incluya al menos
   encabezados, negrita, cursiva, listas, citas, bloques de código, enlaces e
   imágenes incrustadas.
2. THE STOU SHALL tratar una Nota como Material, clasificable en Categorias y
   asignable a Tareas.
3. THE STOU SHALL permitir vincular una Nota a una Seccion o a una posición
   concreta de otro Material.
4. WHEN el usuario abre un Material que tiene Notas vinculadas, THE STOU SHALL
   indicar su existencia y SHALL permitir consultarlas junto al contenido.
5. THE STOU SHALL guardar los cambios de una Nota automáticamente y SHALL NOT
   requerir una acción explícita de guardado.
6. THE STOU SHALL permitir exportar una Nota a un formato de texto abierto.

---

### Requisito 9: Categorías jerárquicas

**Historia de Usuario:** Como usuario, quiero organizar todo por materia y tema
anidados, para ver mi trabajo tanto por asignatura completa como por tema
puntual.

#### Criterios de Aceptación

1. THE STOU SHALL permitir crear Categorias en una jerarquía de profundidad
   arbitraria.
2. THE STOU SHALL permitir renombrar, mover y eliminar Categorias, y SHALL
   conservar la coherencia de las referencias existentes.
3. WHEN el usuario elimina una Categoria con descendientes o con elementos
   asociados, THE STOU SHALL exigir una decisión sobre esos elementos antes de
   proceder.
4. WHEN STOU agrega métricas o listados por una Categoria, THE STOU SHALL incluir
   los elementos de sus Categorias descendientes y SHALL permitir ver el valor
   propio de la Categoria por separado.
5. THE STOU SHALL permitir asignar un color e ícono a cada Categoria y SHALL
   usarlos de forma consistente en todas las vistas.
6. THE STOU SHALL NOT permitir ciclos en la jerarquía de Categorias.

---

### Requisito 10: Tareas de estudio

**Historia de Usuario:** Como usuario, quiero definir qué debo estudiar y cuándo,
para saber a qué sentarme sin decidirlo en el momento.

#### Criterios de Aceptación

1. THE STOU SHALL permitir crear una Tarea con título, descripción, Categoria,
   Estado, prioridad, fecha de inicio, fecha límite y duración estimada.
2. THE STOU SHALL definir los Estados Pendiente, En_Progreso, Completada y
   Cancelada, y SHALL NOT permitir al usuario definir Estados propios.
3. WHEN el usuario inicia una Sesion_Estudio de una Tarea Pendiente, THE STOU
   SHALL cambiar su Estado a En_Progreso.
4. WHEN el usuario marca una Tarea como Completada, THE STOU SHALL registrar la
   fecha de finalización.
5. THE STOU SHALL permitir subtareas anidadas dentro de una Tarea.
6. WHEN todas las subtareas de una Tarea están Completadas, THE STOU SHALL
   indicarlo y SHALL NOT completar la Tarea padre automáticamente.
7. THE STOU SHALL mostrar el progreso de una Tarea a partir de sus subtareas
   completadas y de sus Secciones asignadas ya estudiadas.
8. THE STOU SHALL ofrecer vistas de Tareas por lista, por Categoria, por fecha y
   por Estado, con filtros combinables.
9. THE STOU SHALL permitir marcar Secciones asignadas a una Tarea como estudiadas.

---

### Requisito 11: Asignación de material a las tareas

**Historia de Usuario:** Como usuario, quiero que una tarea lleve pegado su
material, para que al empezar a estudiar no tenga que buscar nada.

#### Criterios de Aceptación

1. THE STOU SHALL permitir asignar a una Tarea cualquier combinación de Secciones
   y Materiales completos.
2. THE STOU SHALL permitir ordenar el material asignado a una Tarea para definir
   la secuencia de estudio.
3. THE STOU SHALL permitir asignar la misma Seccion a varias Tareas.
4. WHEN el usuario asigna material a una Tarea, THE STOU SHALL sugerir Secciones
   de la Categoria de la Tarea que estén activas y no estudiadas.
5. WHEN el usuario elimina una Tarea, THE STOU SHALL conservar el material
   asignado en la Biblioteca.
6. THE STOU SHALL mostrar, para cada Seccion, en qué Tareas está asignada.
7. IF una Tarea no tiene material asignado, THEN THE STOU SHALL permitirla
   igualmente y SHALL indicarlo al abrirla.

---

### Requisito 12: Modo de estudio

**Historia de Usuario:** Como usuario, quiero que al empezar una tarea se me
presente todo su material listo para estudiar, para entrar en foco de inmediato.

#### Criterios de Aceptación

1. WHEN el usuario inicia una Tarea, THE STOU SHALL abrir el Modo_Estudio con todo
   el material asignado disponible en la secuencia definida.
2. THE Modo_Estudio SHALL abrir el primer elemento pendiente de la secuencia y
   SHALL permitir avanzar y retroceder entre elementos sin salir del modo.
3. THE Modo_Estudio SHALL mostrar simultáneamente el material y un panel de notas
   de la Tarea.
4. THE Modo_Estudio SHALL permitir ver dos materiales en paralelo.
5. THE Modo_Estudio SHALL mostrar el Tiempo_Efectivo acumulado de la
   Sesion_Estudio en curso.
6. THE Modo_Estudio SHALL ofrecer un modo sin distracciones que oculte los
   elementos de navegación ajenos al material.
7. THE Modo_Estudio SHALL permitir marcar una Seccion como estudiada sin salir del
   modo.
8. WHEN el usuario cierra el Modo_Estudio, THE STOU SHALL cerrar la
   Sesion_Estudio, SHALL persistir la Posicion_Lectura de cada material consultado
   y SHALL mostrar un resumen de lo trabajado.
9. WHEN el usuario reabre una Tarea, THE Modo_Estudio SHALL restaurar el material
   y las posiciones de la última sesión.

---

### Requisito 13: Registro automático del tiempo

**Historia de Usuario:** Como usuario, quiero que STOU cuente solo el tiempo que
dedico a cada materia, para saber en qué se me va el estudio sin llevar la cuenta
a mano.

#### Criterios de Aceptación

1. WHILE el Modo_Estudio está activo y hay material abierto, THE STOU SHALL
   acumular Tiempo_Efectivo a la Sesion_Estudio en curso.
2. THE STOU SHALL atribuir el Tiempo_Efectivo a la Tarea activa, a su Categoria y
   al material que estuvo abierto.
3. WHEN transcurre el Umbral_Inactividad sin interacción del usuario, THE STOU
   SHALL dejar de acumular Tiempo_Efectivo y SHALL descartar el tiempo posterior a
   la última interacción registrada.
4. WHILE un video o audio se está reproduciendo, THE STOU SHALL considerar la
   sesión activa aunque no haya interacción del usuario.
5. WHEN la ventana de STOU deja de estar en primer plano, THE STOU SHALL pausar la
   acumulación de Tiempo_Efectivo, excepto mientras se reproduce un medio.
6. WHEN el usuario vuelve a interactuar tras una pausa, THE STOU SHALL reanudar la
   acumulación sin crear una Sesion_Estudio nueva.
7. THE STOU SHALL permitir configurar el Umbral_Inactividad, con 5 minutos como
   valor predeterminado.
8. THE STOU SHALL permitir consultar, corregir manualmente y eliminar
   Sesiones_Estudio registradas.
9. THE STOU SHALL permitir registrar manualmente una Sesion_Estudio de trabajo
   hecho fuera de la aplicación.
10. IF la aplicación termina de forma anormal durante una sesión, THEN THE STOU
    SHALL conservar el Tiempo_Efectivo acumulado hasta la última interacción
    registrada.
11. THE STOU SHALL indicar visualmente cuándo el conteo está activo y cuándo está
    pausado.

---

### Requisito 14: Ciclo de vida del material y exámenes

**Historia de Usuario:** Como usuario, quiero que el material salga de mi circuito
activo cuando ya aprobé el examen que lo cubría, para que solo tenga delante lo
que todavía debo estudiar.

#### Criterios de Aceptación

1. THE STOU SHALL permitir crear un Examen con título, Categoria, fecha y un
   Temario compuesto por Secciones y Materiales.
2. THE STOU SHALL tratar toda Seccion como activa hasta que sea Archivada.
3. THE STOU SHALL permitir registrar el resultado de un Examen como aprobado o
   reprobado, con una nota o calificación opcional.
4. WHEN el usuario registra un Examen como aprobado, THE STOU SHALL Archivar las
   Secciones de su Temario.
5. WHEN el usuario registra un Examen como reprobado, THE STOU SHALL mantener
   activas las Secciones de su Temario y SHALL permitir crear un reintento que
   herede el Temario.
6. THE Registro_Examen SHALL permitir indicar el resultado por Seccion, y WHEN se
   registra de ese modo, THE STOU SHALL Archivar únicamente las Secciones
   aprobadas.
7. THE STOU SHALL excluir el material Archivado de las vistas de estudio activo,
   de las sugerencias de asignación y del plan de la semana.
8. THE STOU SHALL mantener el material Archivado consultable, buscable y accesible
   desde una vista de archivo, conservando sus Secciones, notas y anotaciones.
9. THE STOU SHALL permitir reactivar manualmente material Archivado.
10. THE STOU SHALL conservar el historial de Exámenes de cada Categoria con sus
    resultados y fechas.
11. THE STOU SHALL NOT eliminar material como consecuencia de archivarlo.

---

### Requisito 15: Evaluación asistida dentro de la aplicación

**Historia de Usuario:** Como usuario, quiero que más adelante STOU pueda
evaluarme sobre el material estudiado, para comprobar lo aprendido sin depender de
un examen externo.

#### Criterios de Aceptación

1. THE STOU SHALL admitir la administración de Exámenes dentro de la aplicación
   como una capacidad posterior y explícitamente experimental.
2. THE STOU SHALL mantener el registro manual del resultado descrito en el
   Requisito 14 como mecanismo válido y completo por sí mismo.
3. THE modelo de datos de Examen SHALL permitir asociar preguntas, respuestas del
   usuario y calificación sin requerir un cambio estructural cuando la capacidad
   se implemente.
4. WHERE la evaluación asistida esté disponible, THE STOU SHALL requerir que el
   usuario configure explícitamente un proveedor de modelo de lenguaje antes de
   usarla.
5. WHERE la evaluación asistida esté disponible, THE STOU SHALL identificar
   claramente qué contenido se enviaría al proveedor y SHALL requerir
   consentimiento antes de la primera transmisión.
6. THE STOU SHALL NOT hacer depender de un modelo de lenguaje ninguna función
   descrita en los demás requisitos de este documento.

---

### Requisito 16: Calendario de actividades

**Historia de Usuario:** Como usuario, quiero ver mis tareas y exámenes en un
calendario, para repartir el estudio antes de que se me junte todo.

#### Criterios de Aceptación

1. THE Calendario SHALL ofrecer vistas de mes, semana y día.
2. THE Calendario SHALL mostrar las Tareas con fecha y los Exámenes, diferenciados
   visualmente y coloreados por Categoria.
3. THE STOU SHALL permitir crear una Tarea directamente desde el Calendario en la
   fecha seleccionada.
4. THE STOU SHALL permitir reprogramar una Tarea arrastrándola a otra fecha en el
   Calendario.
5. THE STOU SHALL permitir abrir el Modo_Estudio de una Tarea desde el Calendario.
6. THE Calendario SHALL indicar los días cuya carga estimada excede un límite
   diario configurable.
7. THE Calendario SHALL permitir filtrar por Categoria.
8. THE Calendario SHALL destacar el día actual y los Exámenes próximos.
9. THE STOU SHALL permitir emitir recordatorios locales de Tareas y Exámenes
   mediante notificaciones del sistema.

---

### Requisito 17: Dashboard

**Historia de Usuario:** Como usuario, quiero ver cuánto he estudiado de cada
materia y qué me espera esta semana, para corregir el rumbo con datos y no con
sensaciones.

#### Criterios de Aceptación

1. THE Dashboard SHALL mostrar el Tiempo_Efectivo acumulado por Categoria en un
   período seleccionable.
2. THE Dashboard SHALL ofrecer al menos los períodos de hoy, semana actual, mes
   actual y un rango de fechas definido por el usuario.
3. THE Dashboard SHALL mostrar la evolución del tiempo estudiado a lo largo del
   período seleccionado.
4. THE Dashboard SHALL mostrar las Tareas próximas y los Exámenes próximos
   ordenados por fecha.
5. THE Dashboard SHALL mostrar el plan de la semana derivado de las Tareas con
   fecha en la semana y de los Exámenes cercanos.
6. THE Dashboard SHALL mostrar Tareas vencidas sin completar.
7. THE Dashboard SHALL mostrar el avance del material por Categoria en términos de
   Secciones estudiadas, activas y Archivadas.
8. THE Dashboard SHALL mostrar la cantidad de Tareas completadas en el período.
9. THE Dashboard SHALL mostrar los días consecutivos con al menos una
   Sesion_Estudio registrada.
10. WHEN el usuario selecciona un elemento del Dashboard, THE STOU SHALL navegar
    al detalle correspondiente.
11. WHERE no existen datos suficientes para una métrica, THE Dashboard SHALL
    indicarlo explícitamente y SHALL NOT mostrar un valor engañoso.
12. THE Dashboard SHALL calcular sus métricas únicamente a partir de
    Sesiones_Estudio registradas y SHALL NOT estimar tiempo no registrado.

---

### Requisito 18: Búsqueda global

**Historia de Usuario:** Como usuario, quiero buscar una palabra y encontrarla en
cualquier parte de mi material, para llegar al fragmento exacto sin recordar dónde
estaba.

#### Criterios de Aceptación

1. THE STOU SHALL ofrecer una búsqueda única sobre Tareas, Materiales, Secciones,
   Notas, anotaciones y Categorias.
2. THE STOU SHALL extraer el texto de los Materiales que lo permitan y SHALL
   incorporarlo al Indice_Busqueda.
3. WHEN un Material se importa, THE STOU SHALL indexarlo en segundo plano y SHALL
   informar el progreso sin bloquear la interfaz.
4. WHEN un resultado corresponde a contenido de un Material, THE STOU SHALL
   indicar la Seccion y la posición, y SHALL permitir abrir el Visor en ese punto.
5. THE búsqueda SHALL permitir filtrar por Categoria, tipo de Material, estado
   activo o Archivado, y rango de fechas.
6. THE STOU SHALL indicar en los resultados cuáles provienen de material
   Archivado.
7. IF un Material no permite extracción de texto, THEN THE STOU SHALL indicarlo en
   su ficha y SHALL indexar al menos sus metadatos, Secciones y notas.
8. THE STOU SHALL entregar resultados de búsqueda dentro de 1 segundo para una
   Biblioteca del tamaño objetivo.

---

### Requisito 19: Rendimiento y respuesta de la interfaz

**Historia de Usuario:** Como usuario, quiero que STOU no se congele al procesar
archivos pesados, porque voy a usarlo todos los días.

#### Criterios de Aceptación

1. THE STOU SHALL ejecutar la importación, la extracción de texto, la indexación,
   el seccionado automático y la generación de miniaturas fuera del hilo de la
   interfaz.
2. THE interfaz SHALL permanecer receptiva a la interacción del usuario durante
   cualquier operación en segundo plano.
3. WHILE una operación en segundo plano está en curso, THE STOU SHALL mostrar su
   progreso y SHALL permitir cancelarla cuando la operación sea cancelable.
4. THE STOU SHALL admitir Bibliotecas de al menos 1000 Materiales y 20 000
   Secciones sin degradación perceptible en la navegación.
5. THE STOU SHALL admitir documentos individuales de al menos 500 MB y 2000
   páginas.
6. WHEN STOU arranca, THE STOU SHALL presentar una interfaz utilizable dentro de
   los 5 segundos en el perfil de hardware objetivo.
7. THE STOU SHALL operar en un dispositivo con CPU moderno y 8 GB de RAM sin
   requerir GPU dedicada.
8. THE STOU SHALL liberar los recursos de los Visores cerrados y SHALL NOT
   incrementar su consumo de memoria de forma sostenida durante una sesión
   prolongada.
9. IF una operación en segundo plano falla, THEN THE STOU SHALL informar qué
   elemento falló y por qué, y SHALL continuar con los elementos restantes.

---

### Requisito 20: Interfaz de escritorio

**Historia de Usuario:** Como usuario que va a pasar horas dentro de STOU, quiero
una interfaz cómoda y navegable con el teclado, para trabajar sin fricción.

#### Criterios de Aceptación

1. THE STOU SHALL implementarse como aplicación de escritorio con PySide6.
2. THE STOU SHALL organizar la navegación principal entre Biblioteca, Tareas,
   Calendario, Dashboard y Archivo.
3. THE STOU SHALL ofrecer temas claro y oscuro, y SHALL permitir seguir el tema
   del sistema.
4. THE STOU SHALL persistir entre ejecuciones el tamaño y posición de la ventana,
   la disposición de paneles y la última vista abierta.
5. THE STOU SHALL ofrecer atajos de teclado para las acciones frecuentes y SHALL
   permitir reasignarlos.
6. THE STOU SHALL permitir operar la navegación principal, la búsqueda y el
   Modo_Estudio íntegramente con el teclado.
7. THE STOU SHALL respetar el orden de foco, las etiquetas accesibles y un
   contraste suficiente en sus controles.
8. THE STOU SHALL permitir ajustar el tamaño de la tipografía de la interfaz.
9. THE STOU SHALL presentar sus textos en español y SHALL permitir agregar otros
   idiomas sin modificar el código.
10. WHEN una acción del usuario falla, THE STOU SHALL explicar la causa en la
    interfaz y SHALL NOT limitarse a un mensaje técnico.

---

### Requisito 21: Persistencia, respaldo y portabilidad

**Historia de Usuario:** Como usuario, quiero poder respaldar y mover todo mi
STOU, para no perder años de material y de registro.

#### Criterios de Aceptación

1. THE STOU SHALL almacenar sus datos estructurados en una base de datos local
   embebida y las Copias_Internas como archivos en su almacenamiento propio.
2. THE STOU SHALL garantizar que una interrupción durante una escritura no deje la
   base de datos en un estado inconsistente.
3. THE STOU SHALL permitir generar un Respaldo completo que incluya los datos y el
   material.
4. THE STOU SHALL permitir restaurar un Respaldo en otro dispositivo y SHALL
   reproducir el estado de la Biblioteca, las Tareas y el historial.
5. THE STOU SHALL permitir exportar los datos del usuario en un formato abierto y
   documentado.
6. THE STOU SHALL versionar el esquema de datos y SHALL migrarlo automáticamente
   al actualizar la aplicación.
7. IF una migración de esquema falla, THEN THE STOU SHALL preservar los datos
   previos y SHALL informar la causa.
8. THE STOU SHALL permitir elegir la ubicación de su almacenamiento antes del
   primer uso.

---

### Requisito 22: Exportación e interconexión posteriores

**Historia de Usuario:** Como usuario, quiero que STOU pueda más adelante
exportar mi calendario y sincronizar con otro dispositivo, para no quedar
encerrado en un solo computador.

#### Criterios de Aceptación

1. THE STOU SHALL admitir la exportación del Calendario a un formato estándar
   interoperable como capacidad posterior.
2. THE STOU SHALL admitir la sincronización entre dispositivos del mismo usuario
   como capacidad posterior.
3. THE modelo de datos SHALL registrar identificadores estables, marcas de tiempo
   de modificación y borrados lógicos suficientes para reconciliar cambios entre
   dispositivos.
4. THE STOU SHALL separar la lógica de dominio del acceso a datos y de la interfaz,
   de modo que estas capacidades no requieran rediseñar el núcleo.
5. THE STOU SHALL NOT introducir dependencias de un servicio remoto en las
   funciones descritas en los demás requisitos.

---

### Requisito 23: Distribución

**Historia de Usuario:** Como usuario, quiero instalar STOU sin preparar un
entorno de Python, para empezar a usarlo de inmediato.

#### Criterios de Aceptación

1. THE STOU SHALL distribuirse como binario ejecutable para Linux y para Windows.
2. THE STOU SHALL operar en Linux Ubuntu 22.04 o superior y distribuciones
   principales, y en Windows 10 y 11.
3. THE paquete distribuido SHALL incluir todas las dependencias necesarias para
   los Visores admitidos.
4. WHEN STOU arranca por primera vez, THE STOU SHALL crear su almacenamiento y
   SHALL guiar al usuario en la creación de su primera Categoria y la importación
   de su primer Material.
5. WHEN se etiqueta una versión, THE flujo de integración continua SHALL construir
   y publicar los artefactos de Linux y Windows.
6. THE STOU SHALL informar su versión dentro de la aplicación.

---

## Decisiones pendientes

Estas cuestiones no están resueltas y no bloquean el diseño inicial, pero deben
cerrarse antes de implementar los requisitos que las mencionan.

1. **Resultado de examen por sección.** El Requisito 14.6 permite archivar solo
   las Secciones aprobadas. Falta confirmar si el registro por Seccion es el
   comportamiento habitual o una opción secundaria frente al registro global.
2. **Tareas recurrentes.** No están incluidas. Falta decidir si el estudio
   periódico se modela con recurrencia o creando Tareas nuevas.
3. **Repetición espaciada.** No está incluida. El archivado por examen cumple un
   rol parecido, pero no contempla repasos programados antes del examen.
4. **OCR de documentos escaneados.** El Requisito 18.7 admite Materiales sin texto
   extraíble. Falta decidir si STOU incorpora OCR local.
5. **Proveedor de modelo de lenguaje** para el Requisito 15, incluido si debe
   admitir modelos locales.
6. **Cifrado del almacenamiento local.** No está incluido.
