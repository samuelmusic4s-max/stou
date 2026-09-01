# TESTING

Qué se prueba en STOU, con qué herramientas y por qué esas y no otras. Son 81 pruebas y
todas corren en segundos, sin base de datos externa ni pantalla.

> **Módulo** TESTING · **Fuente** `tests/` · **Verificado en** `c97ac40`

---

## 1. Correr las pruebas

```bash
uv run pytest                                  # todo
uv run pytest tests/domain                     # una capa
uv run pytest -k estudio                       # por nombre
uv run pytest tests/presentation -x            # parar en el primer fallo
uv run ruff check src tests
```

La configuración está en `pyproject.toml`: `testpaths = ["tests"]`,
`pythonpath = ["src"]`, `addopts = "-q"`. No hace falta instalar el paquete para
probarlo.

Las pruebas de interfaz corren **sin pantalla**: los `conftest.py` fijan
`QT_QPA_PLATFORM=offscreen`. Eso permite ejecutarlas en cualquier terminal o en
integración continua.

---

## 2. El reparto

| Archivo | Nº | Qué cubre |
|---|---|---|
| `tests/test_architecture.py` | 5 | Que la arquitectura siga siendo la que dice ser |
| `tests/domain/test_entities.py` | 9 | Invariantes de tarea, categoría y sección |
| `tests/domain/test_study_session.py` | 7 | El conteo de tiempo, caso por caso |
| `tests/domain/test_exam.py` | 6 | Archivado del temario y reintentos |
| `tests/application/test_study_flow.py` | 9 | Flujos completos: importar, estudiar, evaluar |
| `tests/infrastructure/test_persistence.py` | 8 | Transacciones, fechas en UTC, blob store |
| `tests/presentation/test_flows.py` | 30 | Recorridos de usuario de punta a punta |
| `tests/presentation/test_smoke.py` | 7 | Tema, tokens y formateo |

Los nombres de las pruebas están en español y describen la regla, no el método:
`test_una_sesion_sin_actividad_no_infla_el_tiempo`,
`test_eliminar_una_materia_con_submaterias_se_explica`. Leer la lista de nombres es una
forma legítima de aprender qué garantiza el sistema.

---

## 3. Las pruebas de arquitectura

`tests/test_architecture.py` es la pieza más inusual y la más valiosa. Parsea el AST de
todo `src/stou` y verifica cinco cosas que ninguna revisión humana sostiene a lo largo del
tiempo:

| Prueba | Qué impide |
|---|---|
| `test_las_capas_solo_importan_hacia_adentro` | Que `domain` importe `infrastructure`, o `application` importe `presentation` |
| `test_las_librerias_externas_se_quedan_en_su_capa` | PySide6 fuera de `presentation`/`composition`; `sqlite3` o `pypdf` fuera de `infrastructure` |
| `test_el_dominio_no_conoce_el_reloj_del_sistema` | `datetime.now(` o `time.time(` dentro de `domain/` |
| `test_los_eventos_son_inmutables` | Un evento sin `frozen=True` |
| `test_ninguna_senal_clicked_conecta_un_metodo_con_argumentos` | El botón muerto (ver §6) |

La regla de dependencia vive en dos sitios que deben coincidir: `ARCHITECTURE.md` (para
las personas) y el diccionario `ALLOWED` de este archivo (para la máquina). Si cambias
una, cambia la otra.

**Estas pruebas no se relajan para que un cambio pase.** Si una falla, el diagnóstico por
defecto es que el cambio está mal ubicado.

---

## 4. Fixtures

### Compartidas — `tests/conftest.py`

| Fixture | Qué da |
|---|---|
| `clock` | `FixedClock` fijado en el lunes 2026-03-02 14:00 UTC |
| `container` | `Container` real sobre `tmp_path`, con el reloj fijo y el historial del bus activado |
| `use_cases` | El diccionario de `container.build_use_cases()` |
| `sample_pdf` | PDF de 12 páginas con tres marcadores, generado con pypdf |

Dos decisiones que hacen que esto funcione bien:

**El reloj es fijo y avanza a mano.** `clock.advance(600)` mueve el tiempo diez minutos
sin esperar diez minutos. Es la razón por la que se puede probar la pausa por inactividad,
las rachas y los períodos del dashboard de forma determinista. Que el día de arranque sea
un **lunes** no es casual: hace predecible «esta semana».

**El contenedor es real, no simulado.** Se prueba contra SQLite y contra el sistema de
archivos de verdad, en un directorio temporal. A esta escala es rápido y detecta lo que un
doble de prueba escondería: un mapper mal escrito, una migración que no aplica, una
transacción que no revierte. No hay mocks de repositorio en este proyecto.

`sample_pdf` se genera en el momento en vez de guardarse como archivo binario en el
repositorio, así que se puede leer qué contiene: doce páginas y marcadores en la 1, la 5 y
la 9.

### De interfaz — `tests/presentation/conftest.py`

El problema: **los diálogos modales son el enemigo de un test.** `exec()` bloquea para
siempre. La solución aquí es un `Script`: un objeto con respuestas programadas que
sustituye a los diálogos y además **registra lo que se le mostró al usuario**.

```python
script.task_form = TaskFormAnswer(title="Estudiar integrales")
# ... el test pulsa el botón, el diálogo responde solo
assert any("ya estaba" in cuerpo for _t, cuerpo, _k in script.messages)
```

Eso permite recorrer un flujo completo —«pulsa Nueva tarea, escribe un título, acepta»— y
después afirmar sobre **el mensaje que vio el usuario**, no solo sobre el estado de la
base. Buena parte de las 30 pruebas de `test_flows.py` verifica precisamente eso: que
cuando algo no se puede hacer, la aplicación lo explica.

---

## 5. Qué probar según lo que escribas

| Escribiste | Prueba dónde | Verificando |
|---|---|---|
| Invariante de entidad | `tests/domain/` | Que el caso válido pase y el inválido lance con mensaje |
| Caso de uso | `tests/application/` | El efecto sobre el estado **y** los eventos publicados |
| Repositorio o mapper | `tests/infrastructure/` | Escribir y volver a leer, incluidos nulos y fechas |
| Vista o diálogo | `tests/presentation/test_flows.py` | El recorrido del usuario y lo que ve al fallar |
| Token de diseño o formateo | `tests/presentation/test_smoke.py` | Que la escala esté completa y el formato sea legible |

Para afirmar sobre eventos, usa el historial del bus:

```python
nombres = [e.event_name for e in container.bus.history]
assert "SectionsCreated" in nombres
```

---

## 6. Pruebas que existen por un error real

Estas no vienen de un manual: cada una nació de algo que se rompió.

**`test_ninguna_senal_clicked_conecta_un_metodo_con_argumentos`.** El botón «Nueva tarea»
quedó muerto porque `clicked` emite un `bool` que entraba como primer argumento del
método, este fallaba y Qt se comía la excepción. Ni un mensaje. La prueba recorre toda la
capa de presentación buscando ese patrón en `clicked`, `toggled`, `triggered` y `pressed`.

**`test_el_dialogo_de_tarea_aguanta_un_bool_como_fecha`.** La cara defensiva del mismo
bug.

**`test_los_eventos_se_publican_despues_del_commit`.** Publicar antes dejaría a un
suscriptor leyendo un estado que después se revierte.

**`test_una_sesion_abandonada_se_cierra_con_su_ultimo_tick`.** Un cierre anormal no debe
regalar el tiempo entre el último tick y el siguiente arranque.

**`test_una_sesion_sin_actividad_no_infla_el_tiempo`** y
**`test_reproducir_un_video_mantiene_el_conteo_sin_interaccion`.** Las dos direcciones en
que el conteo de tiempo puede mentir, una en cada prueba.

**`test_no_deja_archivos_a_medias_si_falla_la_copia`.** Un blob truncado en la biblioteca
sería un material corrupto para siempre.

**`test_cerrar_dos_veces_la_ventana_de_estudio_no_duplica_la_sesion`.**

Cuando arregles un fallo, la prueba que escribas se queda aquí. Esa lista es la memoria
del proyecto.

---

## 7. Criterios

- Una prueba nombra una **regla**, no un método. Si el nombre no se puede leer como una
  afirmación sobre el producto, probablemente prueba la implementación.
- Se prueba el comportamiento observable: estado resultante, eventos publicados, mensaje
  mostrado. No los internos privados.
- Nada de `sleep`. El tiempo se mueve con `FixedClock.advance`.
- Sin red y sin dependencias externas. `ffprobe` es opcional y su ausencia no rompe nada.
- Una prueba que falla intermitentemente se arregla o se borra; no se tolera.
