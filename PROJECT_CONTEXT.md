# PROJECT_CONTEXT

Punto de entrada de la documentación de **STOU**. Si eres una persona nueva en el
proyecto, o un modelo de lenguaje que va a trabajar sobre él, empieza aquí.

> **Módulo** PROJECT_CONTEXT · **Alcance** todo el proyecto · **Verificado en** `c97ac40`

---

## 1. Qué es STOU en cinco frases

1. Aplicación de escritorio **local y de un solo usuario** (PySide6 + SQLite). No hay
   cuentas, ni servidor, ni sincronización.
2. El material de estudio se importa **una vez**, se copia dentro de la biblioteca
   interna y se parte en **secciones** (capítulos de un libro, tramos de un video).
3. Las **tareas** no adjuntan archivos: apuntan a secciones concretas. Abrir una tarea
   abre el material ya servido y ordenado.
4. El **tiempo se cuenta solo** mientras hay trabajo real, y solo se reporta el tiempo
   que se midió.
5. Aprobar un **examen** archiva su temario: el material tiene un ciclo de vida con
   final, no se acumula activo para siempre.

Principio rector, tomado de la especificación original:

> «Cuando el usuario se sienta a estudiar, no debe tener que preparar nada: el material
> correcto ya está abierto delante de él.»

---

## 2. Mapa de la documentación

Cada archivo es un módulo independiente con un tema y una fuente de verdad en el
código. Se pueden leer por separado y crecer por separado.

| Documento | Responde a |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | **Normativo.** Capas, regla de dependencia, estructura de carpetas |
| [README.md](README.md) | Cómo correr y qué hay en v0.1 |
| [docs/AGENT_PLAYBOOK.md](docs/AGENT_PLAYBOOK.md) | Cómo trabajar en este repositorio (humano o LLM) |
| [docs/DOCS_GUIDE.md](docs/DOCS_GUIDE.md) | Cómo mantener y hacer crecer esta documentación |
| [docs/GLOSSARY.md](docs/GLOSSARY.md) | Vocabulario del dominio, inglés en código / español en pantalla |
| [docs/DOMAIN_MODEL.md](docs/DOMAIN_MODEL.md) | Entidades, value objects e invariantes |
| [docs/APPLICATION_SURFACE.md](docs/APPLICATION_SURFACE.md) | Catálogo completo de casos de uso y DTOs |
| [docs/EVENTS.md](docs/EVENTS.md) | Catálogo de eventos, quién los emite y quién reacciona |
| [docs/TIME_TRACKING.md](docs/TIME_TRACKING.md) | La regla exacta del conteo de tiempo |
| [docs/DATA_AND_STORAGE.md](docs/DATA_AND_STORAGE.md) | Esquema SQLite, migraciones, blob store, rutas de datos |
| [docs/CONTENT_PIPELINE.md](docs/CONTENT_PIPELINE.md) | Importar → inspeccionar → seccionar → visualizar |
| [docs/UI_MAP.md](docs/UI_MAP.md) | Vistas, navegación, atajos, tokens de diseño |
| [docs/TESTING.md](docs/TESTING.md) | Qué se prueba, cómo y con qué fixtures |
| [docs/CONVENTIONS.md](docs/CONVENTIONS.md) | Estilo, nombres, tipado, manejo de errores |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Registro de decisiones: qué se decidió y por qué |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Estado real de cada área y qué falta |

---

## 3. Qué leer según la tarea

Contextos mínimos recomendados. Cargar más de lo necesario diluye la atención tanto
en una persona como en un modelo.

| Voy a… | Leer |
|---|---|
| Agregar una regla de negocio | `ARCHITECTURE.md` §3 · `DOMAIN_MODEL.md` · `EVENTS.md` |
| Agregar un caso de uso | `APPLICATION_SURFACE.md` · `ARCHITECTURE.md` §3 · `EVENTS.md` |
| Tocar el conteo de tiempo | `TIME_TRACKING.md` · `DOMAIN_MODEL.md` (StudySession) |
| Cambiar el esquema de la base | `DATA_AND_STORAGE.md` · `TESTING.md` |
| Importar un formato nuevo | `CONTENT_PIPELINE.md` · `DATA_AND_STORAGE.md` |
| Tocar una vista o un atajo | `UI_MAP.md` · `CONVENTIONS.md` (§Qt) |
| Entender por qué algo es así | `DECISIONS.md` |
| Planear la siguiente versión | `ROADMAP.md` |
| Cualquier cambio, siempre | `AGENT_PLAYBOOK.md` |

---

## 4. Coordenadas técnicas

```
Lenguaje      Python >= 3.12 (el entorno actual usa 3.14)
GUI           PySide6 6.11.2
Persistencia  SQLite (stdlib, WAL, migraciones propias)
Lectura PDF   pypdf 6.16.2
Gestor        uv
Calidad       pytest 8.4.2 · pytest-qt 4.5.0 · ruff 0.14.4
Arranque      uv run python -m stou   /   script de consola: stou
Datos         $STOU_DATA_DIR  →  $XDG_DATA_HOME/stou  →  ~/.local/share/stou
```

Verificación completa:

```bash
uv run pytest              # 81 pruebas, incluye las de arquitectura
uv run ruff check src tests
```

---

## 5. Las cinco reglas que no se negocian

Están detalladas en `ARCHITECTURE.md` y las verifica `tests/test_architecture.py`.
Se repiten aquí porque son la frontera entre «cambio correcto» y «cambio que degrada
el proyecto».

1. **Las dependencias apuntan hacia adentro.** `domain` no conoce a nadie más que
   `shared`; `application` no conoce `infrastructure` ni `presentation`.
2. **PySide6 solo en `presentation` y `composition`. `sqlite3` y `pypdf` solo en
   `infrastructure`.**
3. **El dominio no lee el reloj.** El tiempo entra por argumento o por `Clock`.
4. **Los eventos se publican después del commit**, nunca antes.
5. **La presentación recibe DTOs**, nunca entidades de dominio ni repositorios.

---

## 6. Estado del proyecto

Versión `0.1.0`. Funcional de punta a punta: importar material, seccionarlo, crear
tareas, estudiar con conteo de tiempo, registrar exámenes y ver el historial.

Pendiente y explícitamente no implementado: búsqueda de texto dentro del material
(la tabla FTS5 existe pero nadie la llena), anotaciones persistentes, exportar
calendario, sincronización entre dispositivos, evaluación con LLM. Detalle y orden
sugerido en [docs/ROADMAP.md](docs/ROADMAP.md).
