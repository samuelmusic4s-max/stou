# TIME_TRACKING

Cómo cuenta STOU el tiempo de estudio y por qué está hecho así. Es la lógica más sutil
del proyecto: si vas a tocarla, lee este documento completo antes.

> **Módulo** TIME_TRACKING · **Fuente** `src/stou/domain/entities/study_session.py`, `src/stou/application/use_cases/study.py`, `src/stou/presentation/views/study_view.py` · **Verificado en** `c97ac40`

---

## 1. La promesa

STOU promete una cosa sobre el tiempo: **lo que aparece registrado se trabajó de verdad,
y lo que se trabajó de verdad aparece registrado.** Las dos direcciones importan y cada
una se rompe de una forma distinta.

Un cronómetro que cuenta desde que abres la ventana hasta que la cierras exagera: cuenta
la hora que la ventana quedó abierta mientras cenabas. Un cronómetro que cuenta solo
mientras tocas el teclado subestima: registra cinco minutos por un video de cuarenta que
viste sin mover un dedo.

Ninguna de las dos cifras sirve. Si el número exagera, deja de significar algo. Si
subestima, el usuario aprende a no confiar en él y termina apuntando su tiempo aparte,
que es exactamente el trabajo que STOU debería quitarle.

De ahí la regla, y de ahí que sea más complicada de lo que uno esperaría.

---

## 2. La regla

> El tiempo cuenta mientras haya **interacción reciente** (umbral de 5 minutos) **o**
> mientras un **medio esté reproduciéndose**.

Formalmente, para cada intervalo entre dos ticks:

```
cuenta el tramo hasta:
    ahora                                  si hay un medio reproduciéndose
    min(ahora, última_actividad + 300 s)    en cualquier otro caso
```

El umbral vive en `DEFAULT_IDLE_THRESHOLD_SECONDS = 300`
(`domain/entities/study_session.py`) y es inyectable en `TickStudySession`, lo que
permite probar el comportamiento con umbrales cortos sin esperar cinco minutos.

---

## 3. El mecanismo, capa por capa

### 3.1 La ventana de estudio detecta

`StudyWindow` (`presentation/views/study_view.py`) instala un filtro de eventos **sobre
la aplicación entera** y marca `_had_activity = True` cuando ve una tecla, un clic, un
movimiento de ratón o una rueda. Es un filtro global a propósito: el usuario puede estar
interactuando con el visor incrustado y no con el marco de la ventana.

Por separado, cada visor expone `media_playing`. La implementación base devuelve
`False`; el visor de medios locales y el reproductor oficial de YouTube incrustado lo
informan de verdad.

### 3.2 El tick

Un `QTimer` de **5 segundos** (`TICK_MS = 5000`) llama a `TickStudySession` con cuatro
datos: la sesión, si hubo actividad desde el tick anterior, si hay un medio
reproduciéndose y qué material está enfocado. Después de leerlo, `_had_activity` vuelve
a `False`.

```python
state = self._s.tick_session.execute(
    session_id=self._session_id,
    had_activity=had_activity,
    media_playing=media_playing,
    material_id=self._current_item.material_id if self._current_item else None,
)
```

El caso de uso traduce eso a llamadas al dominio: `note_activity(now)` si hubo
actividad, `focus_material(...)` si cambió el material, y `tick(...)`. Devuelve un
`SessionState` con los segundos efectivos y si está en pausa; la ventana pinta el
cronómetro con eso y nada más.

### 3.3 El dominio acumula — `StudySession.tick()`

Este es el corazón. En orden:

1. Si la sesión está cerrada, o `now` no avanzó respecto al último tick, no hace nada.
2. **Define el inicio de la ventana contable.** Normalmente es `last_tick_at`. Pero si
   veníamos en pausa, el tramo anterior a la primera interacción **no cuenta**: la
   ventana empieza en `min(last_activity_at, now)`. El usuario no estaba trabajando
   aunque la ventana siguiera abierta.
3. **Define hasta dónde cuenta.** Con medio reproduciéndose, hasta `now` (y además
   refresca `last_activity_at`, porque ver un video *es* actividad). Sin medio, hasta
   `last_activity_at + umbral`.
4. **Acumula** si hay algo que acumular. Si estábamos en pausa y ahora sí hay tiempo
   contable, sale de pausa y registra `StudySessionResumed`.
5. **Pausa** si el tramo contable terminó antes de `now`, registrando
   `StudySessionPaused(reason="inactividad")` una sola vez.
6. Actualiza `last_tick_at` y `updated_at`.

El paso 2 es el que suele olvidarse al reescribir esto. Sin él, salir de una pausa
regalaría todo el tiempo inactivo.

### 3.4 El cierre

`close(now)` hace un último `tick(now)` antes de sellar, para no perder el tramo desde el
tick anterior, y registra `StudySessionClosed` con los segundos efectivos.

`effective_seconds` es `int(accumulated_seconds)`: se trunca, no se redondea.

---

## 4. Casos límite y cómo se resuelven

| Situación | Comportamiento |
|---|---|
| Dos ventanas de estudio | Imposible: `StartStudySession` cierra toda sesión abierta antes de empezar |
| Cierre anormal de la aplicación | Al arrancar, `CloseAbandonedSessions` cierra las huérfanas **en su último tick conocido**. No se inventa tiempo |
| El usuario olvidó el cronómetro | La pausa por inactividad ya limitó el daño a 5 minutos |
| Estudió sin la aplicación abierta | `AddManualSession(task_id, started_at, minutes)`. Queda marcada `manual=True` y es distinguible en el historial |
| La cifra registrada está mal | `AdjustSession(session_id, minutes)` la corrige. Rechaza negativos |
| Sesión sin tiempo efectivo | Se cierra igual, y la barra de estado lo dice: «Sesión cerrada sin tiempo efectivo: no se registró nada» |

---

## 5. Cómo se agrega ese tiempo

`GetDashboard` y `GetHomeOverview` suman `effective_seconds` de las sesiones del período
y **descartan las de cero**. Atribuyen el tiempo a la categoría que la sesión guardó al
nacer (`category_id` copiado de la tarea), no a la categoría actual de la tarea: mover
una tarea de materia no reescribe el pasado.

Los períodos se calculan sobre **días locales** y se convierten a UTC
(`application/periods.py`). Un día del dashboard es el día que el usuario vivió, no el
día UTC. Con zona horaria negativa, la diferencia no es cosmética: sería medianoche a
las 7 de la tarde.

La **racha** cuenta días locales consecutivos con al menos un segundo efectivo, mirando
hacia atrás hasta 400 días. Empieza hoy si hoy hubo actividad; si no, desde ayer, para
no romper la racha a las 9 de la mañana antes de haber estudiado.

**Nunca se estima.** Si no hubo sesión medida, no hay tiempo. No hay heurística que
infiera «habrás estudiado una hora» a partir de una tarea completada.

---

## 6. Lo que está probado

`tests/domain/test_study_session.py` (7 pruebas) cubre el mecanismo con un reloj fijo:
acumulación normal, pausa al pasar el umbral, reanudación tras actividad, conteo con
medio reproduciéndose, sesión manual y ajuste.

`tests/application/test_study_flow.py` cubre el flujo completo, incluido el cierre de
sesiones abandonadas.

Si cambias `tick()`, estas pruebas son tu red. Si una falla, el que probablemente esté
mal es el cambio.

---

## 7. Si vas a modificar esto

Antes de tocar, contesta:

1. ¿Puede esta versión **exagerar** el tiempo? (contar ausencia como trabajo)
2. ¿Puede **subestimarlo**? (perder trabajo real, como el video sin teclado)
3. ¿Sigue siendo determinista con un `FixedClock`?
4. ¿Sigue el dominio sin leer el reloj del sistema?

Si alguna respuesta no es la deseada, el cambio está incompleto.

Ver también: [`DOMAIN_MODEL.md`](DOMAIN_MODEL.md) §4.5,
[`APPLICATION_SURFACE.md`](APPLICATION_SURFACE.md) §8, [`EVENTS.md`](EVENTS.md) §4.
