# GLOSSARY

El vocabulario de STOU. Importa porque el código está en inglés y la interfaz en español,
y porque algunas palabras tienen aquí un significado más estrecho que en el habla común.

> **Módulo** GLOSSARY · **Fuente** `src/stou/domain/`, textos de la interfaz · **Verificado en** `c97ac40`

---

## 1. Código en inglés, pantalla en español

| En el código | En pantalla | Qué es |
|---|---|---|
| `Category` | **materia** | Nodo del árbol que clasifica material y tareas |
| `Material` | **material** | Una unidad de contenido de la biblioteca |
| `Section` | **sección** | Fragmento estudiable de un material |
| `Task` | **tarea** | Trabajo a realizar, apuntando a secciones |
| `TaskItem` | (sin nombre propio) | Una asignación de material o sección a una tarea |
| `StudySession` | **sesión** | Un tramo de tiempo dedicado a una tarea |
| `Exam` | **examen** | Evaluación con un temario de secciones |
| `Locator` | **rango** | Intervalo que delimita una sección |
| `DashboardView` | **Historial** | La pantalla de métricas |

El caso de `Category` → «materia» es el que más confunde: en el código nunca aparece
`subject`. Y el Dashboard se llama «Historial» en pantalla desde que dejó de ser la puerta
de entrada (ver [`DECISIONS.md`](DECISIONS.md) D-13).

---

## 2. Términos con significado propio en STOU

**Sección.** No es una división cualquiera del material: es la **unidad de trabajo** del
sistema. Es lo que se asigna a una tarea, lo que se marca como estudiado y lo que un examen
archiva. Todo material tiene al menos una.

**Tiempo efectivo.** Los segundos que una sesión acumuló cumpliendo la regla de conteo
(interacción reciente o medio reproduciéndose). **No** es el tiempo que la ventana estuvo
abierta. Truncado a segundos enteros.

**Archivar.** Marcar material o secciones como fuera del circuito activo. **No es borrar:**
lo archivado sigue consultable, solo deja de aparecer en sugerencias y listas activas. Lo
provoca aprobar un examen, o el usuario a mano.

**Temario.** La lista de secciones que cubre un examen (`Exam.section_ids`). Es lo que se
archiva al aprobar y lo que hereda un reintento.

**Puesta en marcha** (*onboarding*). Los tres primeros pasos: crear una materia, subir
material, crear la primera tarea. `HomeOverview.onboarding_step` vale 0 cuando ya están los
tres; si no, indica el paso pendiente (1, 2 o 3).

**Racha.** Días locales consecutivos con al menos un segundo de tiempo efectivo. Empieza
hoy si hoy hubo actividad; si no, desde ayer, para no romperla a las 9 de la mañana.

**Modo estudio.** La ventana aparte que sirve el material de una tarea y cuenta el tiempo.
Distinto del **visor suelto**, que abre un material sin arrancar el cronómetro.

**Sin distracciones.** El modo de `F11`: esconde todo menos el material.

**Blob.** El archivo del usuario guardado en la biblioteca interna, nombrado con el SHA-256
de su contenido.

**Extensión** (de un material). Su última posición conocida: número de páginas para un PDF,
duración en segundos para un medio. Si no se conoce, no se puede dividir en partes iguales.

**Tick.** El pulso de 5 segundos que la ventana de estudio manda a la capa de aplicación
para que acumule o pause el conteo.

---

## 3. Términos de arquitectura

**Caso de uso** (*use case*). Una clase con un único método público `execute()` que
representa una acción del sistema. El catálogo completo está en
[`APPLICATION_SURFACE.md`](APPLICATION_SURFACE.md).

**Puerto** (*port*). Una interfaz declarada como `typing.Protocol` por la capa que
**necesita** algo. `UnitOfWork`, `EventBus`, `FileStorage`, `MaterialInspector`,
`TextExtractor`, `EpubUnpacker` y los repositorios son puertos.

**Adaptador.** La implementación concreta de un puerto, en `infrastructure`.
`SqliteTaskRepository` es el adaptador de `TaskRepository`.

**DTO.** Objeto inmutable que la capa de aplicación entrega a la presentación. Nunca sale
una entidad de dominio hacia la interfaz.

**Unidad de trabajo** (*Unit of Work*). El objeto que agrupa una transacción y da acceso a
todos los repositorios. Reentrante: un bloque anidado se suma a la transacción abierta.

**Evento de dominio.** Un hecho ya ocurrido, inmutable, nombrado en pasado. Se lee con
`event.event_name`, **nunca** `event.name`.

**Composition root.** `src/stou/composition/`: el único lugar del proyecto que conoce todas
las capas y arma el grafo de dependencias.

**Kernel compartido.** `src/stou/shared/`: utilidades sin dominio (identificadores, reloj)
que cualquier capa puede usar.

**Invariante.** Una condición que una entidad garantiza siempre. «Una tarea tiene título»,
«el fin de una sección no es anterior a su inicio».

---

## 4. Unidades y formatos

| Concepto | Unidad |
|---|---|
| Posición en un PDF | página, empezando en **1** |
| Posición en un EPUB | índice del spine, empezando en **0** |
| Posición en video o audio | segundos (`float`) |
| Tiempo de estudio | segundos enteros |
| Duración estimada de una tarea | minutos |
| Instantes guardados | ISO-8601 en **UTC** |
| Períodos de métricas | límites en UTC calculados sobre **días locales** |
| Identificadores | UUIDv7 en texto, 36 caracteres |
| Hash de contenido | SHA-256 en hexadecimal |
