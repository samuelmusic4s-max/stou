# DOCS_GUIDE

Reglas de la propia documentación. Existe para que este conjunto de archivos siga
siendo útil cuando el proyecto haya mutado tres veces.

> **Módulo** DOCS_GUIDE · **Fuente** este directorio · **Verificado en** `c97ac40`

---

## 1. Por qué está partida en módulos

Un solo documento gigante tiene dos problemas. Para una persona, obliga a leer sobre
SQLite cuando lo que quiere es tocar un botón. Para un modelo de lenguaje, gasta
contexto en material irrelevante y diluye la atención sobre lo que sí importa.

De ahí la forma: **un archivo por tema, con una fuente de verdad en el código**, y un
índice único ([`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md)) que dice qué leer según
la tarea.

---

## 2. Convención de nombres

`SCREAMING_SNAKE_CASE.md`, sin numeración.

- **Mayúsculas** porque estos archivos no son prosa opcional: son la referencia. Se
  distinguen de un vistazo del código y de cualquier nota suelta.
- **Sin números de orden** porque el orden cambia y renumerar quince archivos por
  insertar uno es fricción pura. El orden vive en el índice, no en el nombre.
- **Nombre por tema, no por herramienta.** No hay `AGENTS.md` ni `CLAUDE.md`: el tema
  «cómo se trabaja aquí» se llama [`AGENT_PLAYBOOK.md`](AGENT_PLAYBOOK.md) y sirve
  igual para cualquier modelo y para cualquier persona.
- Un nombre debe poder responderse con «esto trata de ___». Si necesitas «y» para
  describirlo, probablemente son dos módulos.

Los dos documentos de la raíz están ahí a propósito: `README.md` es la puerta del
repositorio y `ARCHITECTURE.md` es normativo. `PROJECT_CONTEXT.md` los acompaña como
índice. Todo lo demás vive en `docs/`.

---

## 3. Anatomía de un módulo

```markdown
# NOMBRE_DEL_MODULO

Una o dos frases: de qué trata y para quién.

> **Módulo** NOMBRE · **Fuente** `ruta/en/el/codigo` · **Verificado en** `hash`

## 1. …
```

La línea de metadatos es obligatoria y tiene tres funciones:

| Campo | Para qué sirve |
|---|---|
| **Módulo** | Identidad estable, aunque el archivo se mueva |
| **Fuente** | Dónde está la verdad. Si el documento y el código discrepan, gana el código |
| **Verificado en** | Contra qué commit se leyó el código al escribirlo |

Cuando revises un documento contra el código, actualiza `Verificado en` al commit
actual. Un módulo con un hash viejo es una advertencia, no un error: dice «esto puede
haber envejecido».

---

## 4. Qué va y qué no va en un módulo

**Sí:**

- Reglas, invariantes y decisiones con su motivo.
- Tablas de catálogo (eventos, casos de uso, atajos) que ahorran rastrear el código.
- Errores ya cometidos y la regla que los previene. Son lo más valioso que hay aquí.
- Enlaces cruzados a otros módulos.

**No:**

- Copias de código que van a divergir. Cita la ruta y, si hace falta, el nombre de la
  función. Solo se transcribe un fragmento cuando la forma exacta *es* la regla.
- Tutoriales de Python, Qt o SQLite. Se asume el oficio.
- Resúmenes de otros módulos. Enlaza en su lugar.
- Estado transitorio («estoy trabajando en…»). Eso es del historial de git.

---

## 5. Cómo crece

**Extender un módulo** es la opción por defecto: una sección nueva al final del área
que corresponda.

**Crear un módulo** se justifica cuando aparece un tema que un lector podría querer
sin querer nada más. Al crearlo:

1. Ponle nombre según §2.
2. Añade el encabezado de §3.
3. Regístralo en la tabla de [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) §2 y, si
   corresponde a un tipo de tarea, en la tabla §3.
4. Enlázalo desde los módulos vecinos.

**Retirar un módulo:** si un área desaparece del código, el documento se borra en el
mismo cambio. Documentación sobre algo que ya no existe es peor que ninguna.

---

## 6. Módulos previstos que aún no existen

Se listan para que quien los necesite sepa que el hueco es conocido, no un olvido:

- `SEARCH.md` — cuando se llene la tabla FTS5 y la búsqueda funcione.
- `SYNC.md` — cuando haya sincronización entre dispositivos.
- `PACKAGING.md` — cuando exista distribución (AppImage, wheel, instalador).
- `LLM_EVALUATION.md` — si la evaluación con modelos pasa de experimento a función.

---

## 7. Idioma

Todo en español, igual que la interfaz y los comentarios del código. Los nombres de
clases, campos y eventos se citan en inglés porque así están en el código; el
vocabulario equivalente está en [`GLOSSARY.md`](GLOSSARY.md).
