# STOU

Gestor de tareas de estudio con el material integrado. Aplicación de escritorio
(PySide6), de un solo usuario y local: no hay cuentas ni servidor.

La idea central: el material se importa una vez, se parte en **secciones**
(capítulos de un libro, tramos de un video), y las **tareas** apuntan a esas
secciones. Al abrir una tarea entras al **modo estudio** con todo su material
servido, y el tiempo se cuenta solo. Cuando apruebas un **examen**, su temario se
archiva y deja de aparecer en el circuito activo, pero sigue consultable.

## Correr

```bash
uv sync
uv run python -m stou
```

Los datos van a `~/.local/share/stou` (o a `$STOU_DATA_DIR`):

```
stou.db        base SQLite (WAL)
library/       copias internas del material, por hash de contenido
cache/epub/    libros descomprimidos para leer
```

## Verificar

```bash
uv run pytest              # incluye el test que hace cumplir las capas
uv run ruff check src tests
```

## Qué hay en v0.1

| Área | Estado |
|---|---|
| Categorías jerárquicas | listo |
| Importar PDF, EPUB, video, audio, imagen, notas | listo, con copia interna y deduplicación por hash |
| Enlaces web y YouTube embebido | listo (reproductor oficial dentro de la app) |
| Seccionado automático (marcadores del PDF, índice del EPUB) y manual | listo |
| Tareas con material asignado y orden de estudio | listo |
| Modo estudio con visor, notas y modo sin distracciones (F11) | listo |
| Conteo automático de tiempo, con pausa por inactividad | listo; ver nota abajo |
| Calendario de tareas y exámenes | listo |
| Dashboard: tiempo por categoría, por día, racha, atrasos, avance | listo |
| Exámenes: registro manual, archivado del temario, reintento | listo |
| Búsqueda de texto dentro del material | pendiente (la tabla FTS ya existe) |
| Anotaciones y resaltados persistentes | pendiente |
| Exportar calendario, sincronizar dispositivos | pendiente |
| Evaluación con LLM | pendiente y experimental |

**Sobre el conteo de tiempo:** cuenta mientras haya interacción reciente (umbral de
5 minutos) **o** mientras un medio esté reproduciéndose. Sin la segunda condición,
ver un video de 40 minutos sin tocar el teclado se registraría como 5. El dashboard
solo suma sesiones medidas: nunca estima tiempo que no se registró.

## Arquitectura

Clean Architecture con cuatro capas y un bus de eventos. Las reglas están en
[ARCHITECTURE.md](ARCHITECTURE.md) y las verifica `tests/test_architecture.py`.
