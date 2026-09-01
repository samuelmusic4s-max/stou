"""Sistema visual de STOU.

Tres decisiones que gobiernan todo lo demás:

1. La jerarquía se construye con **espacio y tamaño**, no con cajas. Un borde por
   todas partes convierte la pantalla en una hoja de cálculo.
2. La profundidad se logra por **elevación de superficie** (fondos cada vez más
   claros), no por líneas.
3. Solo hay **un acento**. Si todo resalta, nada resalta, y el usuario no sabe
   dónde hacer clic.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

ASSETS = Path(__file__).parent / "assets"

# Tamaños que se rasterizan de cada variante del ícono. La variante pequeña existe
# porque a 22 px el anillo de progreso del ícono grande se confunde con el borde.
ICON_VARIANTS: tuple[tuple[str, tuple[int, ...]], ...] = (
    ("icon-small.svg", (16, 22, 24, 32)),
    ("icon.svg", (48, 64, 128, 256)),
)

# --- Tokens -------------------------------------------------------------------

# Paleta «tinta cálida». Tres decisiones que la separan de un tema oscuro genérico:
#
# 1. El lienzo no es negro. Un negro puro contra texto claro cansa la vista y hace
#    que cualquier interfaz parezca la misma. Aquí el fondo es una pizarra con algo
#    de calidez, y las superficies suben en pasos que se distinguen de verdad.
# 2. El texto es un blanco cálido, no blanco puro: menos deslumbramiento a las once
#    de la noche, que es cuando esta aplicación se usa.
# 3. Hay dos acentos con trabajos distintos: el índigo es «esto se puede pulsar» y
#    el ámbar es «esto es tiempo o progreso». Nunca compiten en el mismo sitio.
COLORS = {
    "bg": "#1A1C22",          # lienzo
    "bg_deep": "#15171C",     # barra lateral y zonas de fondo
    "surface": "#222530",     # tarjeta
    "surface_2": "#2B2F3B",   # tarjeta elevada / hover
    "surface_3": "#343945",   # control
    "line": "#333845",        # solo para separar, nunca para encajonar
    "text": "#F2F0EB",        # blanco cálido
    "text_dim": "#AAAEB9",
    "text_faint": "#878C99",
    "accent": "#7B9DF0",      # acción
    "accent_soft": "#293557",
    "accent_text": "#101319",
    "warm": "#E8A44C",
    "warm_soft": "#3B2F1F",
    "ok": "#4FC08D",
    "ok_soft": "#173729",
    "warn": "#E9B44C",
    "warn_soft": "#3B3220",
    "danger": "#EB6B7C",
    "danger_soft": "#3D242B",
    "violet": "#8B79F0",
    # --- Superficie de lectura ---
    # El marco de la aplicación es oscuro; el material se lee sobre papel. No es un
    # capricho estético: leer treinta páginas de texto claro sobre fondo oscuro cansa
    # más que leerlas sobre papel, y esta aplicación existe para leer treinta páginas.
    # Un PDF ya trae páginas blancas, así que el marco oscuro de siempre creaba además
    # un salto de contraste violento justo alrededor de lo que se está mirando.
    "paper": "#F6F1E6",        # la hoja
    "paper_mat": "#E5DDCB",    # el margen alrededor de la hoja
    "paper_ink": "#23262C",    # texto sobre papel
    "paper_ink_dim": "#5B606A",
    "paper_line": "#D8CFBD",
    "paper_link": "#2E58A6",   # el índigo del tema no rinde sobre fondo claro
    "paper_mark": "#C9D8F2",   # selección
}

# Escala de espacio: todo margen y separación sale de aquí.
SPACE = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "2xl": 32, "3xl": 48}

# Escala tipográfica. Subida respecto a la primera versión: a 1080p y más, 12 px de
# cuerpo obliga a acercarse a la pantalla.
TYPE = {
    "display": 34,
    "h1": 25,
    "h2": 18,
    "h3": 15,
    "body": 13,
    "caption": 12,
}

# Duraciones de animación, en milisegundos.
MOTION = {"fast": 140, "base": 220, "slow": 360}

RADIUS = {"card": 16, "control": 10, "pill": 999}


STYLESHEET = """
* {{ outline: 0; }}

/* El fondo NO se declara sobre QWidget.
 *
 * Ese era el origen de los «renglones»: un selector QWidget con background pinta
 * también cada QLabel, y una etiqueta que se estira con la ventana dibuja una banda
 * opaca del ancho de la tarjeta detrás de su texto. Al maximizar, las bandas se
 * vuelven evidentes. El fondo va en la ventana y en las superficies con nombre; todo
 * lo demás es transparente. */
QWidget {{
    color: {text};
    font-size: {body}px;
}}
QMainWindow, QDialog {{ background: {bg}; }}
QLabel, QCheckBox, QRadioButton {{ background: transparent; }}
QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
QSplitter {{ background: transparent; }}

/* --- Tipografía ------------------------------------------------------------ */
QLabel#Display {{ font-size: {display}px; font-weight: 700; }}
QLabel#H1      {{ font-size: {h1}px; font-weight: 700; }}
QLabel#H2      {{ font-size: {h2}px; font-weight: 600; }}
QLabel#H3      {{ font-size: {h3}px; font-weight: 600; }}
QLabel#Title   {{ font-size: {h1}px; font-weight: 700; }}
QLabel#Subtitle {{ color: {text_dim}; font-size: {body}px; }}
QLabel#Dim     {{ color: {text_dim}; }}
QLabel#Faint   {{ color: {text_faint}; font-size: {caption}px; }}
QLabel#Eyebrow {{
    color: {text_faint}; font-size: {caption}px; font-weight: 700;
    letter-spacing: 1.4px;
}}
QLabel#MetricBig    {{ font-size: 42px; font-weight: 700; }}
QLabel#MetricMedium {{ font-size: 26px; font-weight: 700; }}
QLabel#MetricWarm   {{ font-size: 42px; font-weight: 700; color: {warm}; }}
QLabel#Glyph        {{ font-size: 26px; color: {accent}; }}
QLabel#GlyphWarm    {{ font-size: 26px; color: {warm}; }}
QLabel#GlyphLarge   {{ font-size: 46px; color: {text_faint}; }}

/* --- Superficies ----------------------------------------------------------- */
QFrame#Card {{
    background: {surface};
    border: none;
    border-radius: {radius_card}px;
}}
QFrame#CardQuiet {{
    background: transparent;
    border: none;
    border-radius: {radius_card}px;
}}
QFrame#CardAccent {{
    background: {accent_soft};
    border: none;
    border-radius: {radius_card}px;
}}
QFrame#Divider {{ background: {line}; border: none; max-height: 1px; }}

/* Tarjeta de acción: el hover se anima en código, aquí solo el reposo. */
QFrame#ActionCard {{
    background: {surface};
    border: none;
    border-radius: {radius_card}px;
}}
QFrame#ActionCardHot {{
    background: {surface_2};
    border: none;
    border-radius: {radius_card}px;
}}

/* --- Botones --------------------------------------------------------------- */
QPushButton {{
    background: {surface_3};
    color: {text};
    border: none;
    border-radius: {radius_control}px;
    padding: 9px 16px;
    font-weight: 500;
}}
QPushButton:hover {{ background: #2C323F; }}
QPushButton:pressed {{ background: {surface_2}; }}
QPushButton:disabled {{ background: {surface}; color: {text_faint}; }}

QPushButton#Primary {{
    background: {accent}; color: {accent_text}; font-weight: 700;
    padding: 11px 20px;
}}
QPushButton#Primary:hover {{ background: #6F9BF2; }}
QPushButton#Primary:pressed {{ background: #4E7BD8; }}

QPushButton#PrimaryLarge {{
    background: {accent}; color: {accent_text}; font-weight: 700;
    padding: 15px 26px; font-size: {h3}px;
}}
QPushButton#PrimaryLarge:hover {{ background: #6F9BF2; }}

QPushButton#Ghost {{
    background: transparent; color: {text_dim}; padding: 8px 12px;
}}
QPushButton#Ghost:hover {{ background: {surface_2}; color: {text}; }}

QPushButton#Link {{
    background: transparent; color: {accent}; padding: 4px 2px; font-weight: 600;
}}
QPushButton#Link:hover {{ color: #8AB0F5; }}

QPushButton#Danger {{ background: transparent; color: {danger}; }}
QPushButton#Danger:hover {{ background: {danger_soft}; }}

/* Paso de mes: cuadrado y discreto, para que no compita con la acción principal. */
QPushButton#Step {{
    background: {surface_2}; color: {text_dim};
    min-width: 30px; max-width: 30px; padding: 6px 0;
    font-size: {h2}px; font-weight: 700;
}}
QPushButton#Step:hover {{ background: {surface_3}; color: {text}; }}

/* --- Entradas -------------------------------------------------------------- */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox,
QDateTimeEdit, QDateEdit {{
    background: {surface_3};
    border: 1px solid transparent;
    border-radius: {radius_control}px;
    padding: 9px 12px;
    selection-background-color: {accent};
    selection-color: {accent_text};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QDateTimeEdit:focus {{
    border-color: {accent};
    background: {surface_2};
}}
QLineEdit#Search {{
    background: {surface};
    padding: 10px 14px;
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {surface_2}; border: none; border-radius: {radius_control}px;
    padding: 4px; selection-background-color: {accent};
    selection-color: {accent_text};
}}
QCheckBox {{ spacing: 8px; color: {text_dim}; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 5px; background: {surface_3};
}}
QCheckBox::indicator:checked {{ background: {accent}; }}

/* --- Listas y tablas ------------------------------------------------------- */
QTreeWidget, QListWidget, QTreeView, QListView, QTableView {{
    background: transparent;
    border: none;
    outline: 0;
}}
QTreeWidget::item, QListWidget::item {{
    padding: 10px 8px;
    border-radius: {radius_control}px;
    color: {text};
}}
QTreeWidget::item:hover, QListWidget::item:hover {{ background: {surface_2}; }}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background: {accent_soft}; color: {text};
}}
QHeaderView::section {{
    background: transparent;
    color: {text_faint};
    border: none;
    border-bottom: 1px solid {line};
    padding: 8px 8px;
    font-size: {caption}px;
    font-weight: 700;
    letter-spacing: 0.8px;
}}
QTreeWidget#Panel, QListWidget#Panel {{
    background: {surface};
    border-radius: {radius_card}px;
    padding: 6px;
}}

/* --- Navegación ------------------------------------------------------------ */
QWidget#Sidebar {{ background: {bg_deep}; }}
QListWidget#Nav {{ background: transparent; border: none; font-size: {h3}px; }}
QListWidget#Nav::item {{
    padding: 12px 14px; margin: 2px 10px; border-radius: {radius_control}px;
    color: {text_dim};
}}
QListWidget#Nav::item:hover {{ background: {surface}; color: {text}; }}
QListWidget#Nav::item:selected {{ background: {accent_soft}; color: {text}; }}

/* --- Píldoras -------------------------------------------------------------- */
QLabel#Pill {{
    background: {surface_3}; color: {text_dim};
    border-radius: {radius_pill}px; padding: 4px 11px; font-size: {caption}px;
    font-weight: 600;
}}
QLabel#PillAccent {{ background: {accent_soft}; color: #A9C3F7; }}
QLabel#PillOk     {{ background: {ok_soft}; color: {ok}; }}
QLabel#PillWarn   {{ background: {warn_soft}; color: {warn}; }}
QLabel#PillDanger {{ background: {danger_soft}; color: {danger}; }}

/* --- Calendario propio ----------------------------------------------------- */
/* Las celdas tienen altura acotada en el widget; aquí solo el color y el estado. */
QFrame#DayCell, QFrame#DayCellBusy, QFrame#DayCellOutside, QFrame#DayCellSelected {{
    border-radius: {radius_control}px;
    border: 1px solid transparent;
}}
QFrame#DayCell {{ background: {bg}; }}
QFrame#DayCellBusy {{ background: {surface_2}; }}
QFrame#DayCellOutside {{ background: transparent; }}
QFrame#DayCellSelected {{ background: {accent_soft}; border: 1px solid {accent}; }}
QFrame#DayCell:hover, QFrame#DayCellBusy:hover, QFrame#DayCellOutside:hover {{
    border: 1px solid {surface_3};
}}

QLabel#DayNumber      {{ font-size: {h2}px; font-weight: 600; color: {text}; }}
QLabel#DayNumberMuted {{ font-size: {h2}px; font-weight: 500; color: {text_faint}; }}
QLabel#DayNumberToday {{
    font-size: {h2}px; font-weight: 800; color: {accent};
}}

/* Chips de actividad dentro de una celda del mes. */
QLabel#Chip, QLabel#ChipExam, QLabel#ChipLate {{
    border-radius: 5px; padding: 2px 6px; font-size: {caption}px; font-weight: 600;
}}
QLabel#Chip     {{ background: {accent_soft}; color: #C3D3F8; }}
QLabel#ChipExam {{ background: {warn_soft}; color: {warn}; }}
QLabel#ChipLate {{ background: {danger_soft}; color: {danger}; }}

/* --- Superficie de lectura ------------------------------------------------- */
/* El material se lee sobre papel; el marco sigue siendo oscuro. */
QWidget#Paper {{ background: {paper_mat}; }}
QScrollArea#Paper, QScrollArea#Paper > QWidget, QScrollArea#Paper > QWidget > QWidget {{
    background: {paper_mat};
}}
QTextEdit#PaperSheet {{
    background: {paper};
    color: {paper_ink};
    border: none;
    border-radius: {radius_card}px;
    padding: 30px 36px;
    font-size: 15px;
    selection-background-color: {paper_mark};
    selection-color: {paper_ink};
}}
QLabel#PaperNote {{ color: {paper_ink_dim}; font-size: {caption}px; }}

/* --- Varios ---------------------------------------------------------------- */
QProgressBar {{
    background: {surface_3}; border: none; border-radius: 4px; height: 6px;
    text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {accent}; border-radius: 4px; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px; }}
QScrollBar::handle:vertical {{
    background: {surface_3}; border-radius: 5px; min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{ background: {text_faint}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 4px; }}
QScrollBar::handle:horizontal {{
    background: {surface_3}; border-radius: 5px; min-width: 40px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QSplitter::handle {{ background: transparent; width: {space_lg}px; }}
QStatusBar {{ background: {bg}; border: none; color: {text_faint}; }}
QStatusBar::item {{ border: none; }}
QToolTip {{
    background: {surface_2}; color: {text}; border: 1px solid {line};
    border-radius: 8px; padding: 6px 9px;
}}
QMenu {{
    background: {surface_2}; border: 1px solid {line}; border-radius: 12px;
    padding: 6px;
}}
QMenu::item {{ padding: 8px 24px 8px 14px; border-radius: 8px; }}
QMenu::item:selected {{ background: {accent}; color: {accent_text}; }}
QMenu::separator {{ height: 1px; background: {line}; margin: 5px 8px; }}

QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    background: transparent; color: {text_dim}; padding: 9px 16px;
    border-radius: {radius_control}px; margin-right: 4px;
}}
QTabBar::tab:selected {{ background: {surface_2}; color: {text}; }}

QCalendarWidget {{ background: {surface}; border-radius: {radius_card}px; }}
QCalendarWidget QWidget {{ background: {surface}; }}
QCalendarWidget QToolButton {{
    background: transparent; color: {text}; border-radius: 8px; padding: 6px 10px;
    font-size: {h3}px; font-weight: 600;
}}
QCalendarWidget QToolButton:hover {{ background: {surface_2}; }}
QCalendarWidget QAbstractItemView {{
    background: {surface}; outline: 0; selection-background-color: {accent};
    selection-color: {accent_text}; font-size: {body}px;
}}
QCalendarWidget QAbstractItemView:disabled {{ color: {text_faint}; }}
"""


# CSS que se inyecta en los documentos de un EPUB.
#
# Un EPUB trae la hoja de estilos de su editorial, pensada para una página de libro, no
# para una ventana de 1400 px. Los tres arreglos que más se notan:
#
# 1. **Medida.** Una línea de 1400 px es ilegible: el ojo pierde el renglón al volver.
#    Se limita a ~34 em, que son unos 70 caracteres.
# 2. **Papel.** Fondo cálido y tinta oscura, en lugar del blanco puro del navegador.
# 3. **Alineación a la izquierda.** Muchos EPUB vienen justificados; en una columna
#    estrecha el justificado abre ríos de espacio en blanco.
#
# Va con `!important` a propósito: la hoja de la editorial suele tener selectores más
# específicos (`body p.calibre1`) y ganaría sin eso.
READING_CSS = """
html {{ background: {paper_mat} !important; }}
body {{
    background: {paper} !important;
    color: {paper_ink} !important;
    max-width: 34em !important;
    margin: 0 auto !important;
    padding: 3.4rem 2.6rem 5rem !important;
    font-family: Georgia, "Liberation Serif", "Times New Roman", serif !important;
    font-size: 1.06rem !important;
    line-height: 1.68 !important;
    text-align: left !important;
    hyphens: auto;
}}
p, li {{
    color: {paper_ink} !important;
    line-height: 1.68 !important;
    text-align: left !important;
}}
p {{ margin: 0 0 1.05em !important; }}
h1, h2, h3, h4, h5, h6 {{
    color: {paper_ink} !important;
    font-family: "Segoe UI", system-ui, sans-serif !important;
    line-height: 1.25 !important;
    margin: 2em 0 0.6em !important;
    text-align: left !important;
}}
a, a:visited {{ color: {paper_link} !important; }}
img, svg, figure {{ max-width: 100% !important; height: auto !important; }}
blockquote {{
    border-left: 3px solid {paper_line} !important;
    margin-left: 0 !important;
    padding-left: 1.1em !important;
    color: {paper_ink_dim} !important;
    font-style: italic;
}}
code, pre, kbd {{
    font-family: ui-monospace, "DejaVu Sans Mono", monospace !important;
    font-size: 0.92em !important;
}}
pre {{ overflow-x: auto; }}
hr {{ border: none !important; border-top: 1px solid {paper_line} !important; }}
table {{ max-width: 100% !important; }}
::selection {{ background: {paper_mark}; color: {paper_ink}; }}
"""


def reading_css() -> str:
    """El CSS de lectura con los colores del tema ya puestos."""
    return READING_CSS.format(**_tokens())


def _tokens() -> dict[str, object]:
    values: dict[str, object] = dict(COLORS)
    values.update(TYPE)
    values.update({f"space_{k}": v for k, v in SPACE.items()})
    values.update({f"radius_{k}": v for k, v in RADIUS.items()})
    return values


def app_icon() -> QIcon:
    """Ícono de la aplicación, con un mapa de bits por tamaño.

    Se rasteriza a mano en vez de dejarle el SVG a Qt porque así se elige qué variante
    usa cada tamaño: el libro solo para los pequeños, el libro con el anillo para los
    grandes. Requiere que exista una QApplication, porque construye QPixmap.
    """
    icon = QIcon()
    for name, sizes in ICON_VARIANTS:
        path = ASSETS / name
        if not path.is_file():
            continue
        renderer = QSvgRenderer(str(path))
        for size in sizes:
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            icon.addPixmap(pixmap)
    return icon


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(COLORS["bg"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(COLORS["surface"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLORS["surface_2"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(COLORS["surface_3"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(COLORS["accent"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(COLORS["accent_text"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(COLORS["surface_2"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(COLORS["text_faint"]))
    app.setPalette(palette)

    font = QFont(app.font())
    font.setPointSizeF(max(font.pointSizeF(), 10.0))
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    app.setFont(font)

    app.setStyleSheet(STYLESHEET.format(**_tokens()))


# --- Formato ------------------------------------------------------------------


def format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours} h {minutes:02d} min"
    if minutes:
        return f"{minutes} min"
    return f"{secs} s"


def format_duration_short(seconds: int) -> str:
    """Versión compacta para métricas grandes: 1h 20m."""
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    if minutes:
        return f"{minutes}m"
    return "0m"


def format_clock(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_size(size_bytes: int) -> str:
    value = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit in ("B", "KB") else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def relative_day(target, reference) -> str:  # noqa: ANN001 - date o datetime
    """«hoy», «mañana», «en 3 días»: fechas que se entienden sin calcular."""
    from datetime import date, datetime

    def as_date(value):  # noqa: ANN001, ANN202
        return value.astimezone().date() if isinstance(value, datetime) else value

    day: date = as_date(target)
    today: date = as_date(reference)
    delta = (day - today).days
    if delta == 0:
        return "hoy"
    if delta == 1:
        return "mañana"
    if delta == -1:
        return "ayer"
    if delta < 0:
        return f"hace {abs(delta)} días"
    if delta < 7:
        return f"en {delta} días"
    return day.strftime("%d/%m")
