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

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

# --- Tokens -------------------------------------------------------------------

COLORS = {
    "bg": "#0E1014",          # lienzo
    "surface": "#15181E",     # tarjeta
    "surface_2": "#1C2029",   # tarjeta elevada / hover
    "surface_3": "#242935",   # control
    "line": "#242A36",        # solo para separar, nunca para encajonar
    "text": "#EDEFF3",
    "text_dim": "#8B93A1",
    "text_faint": "#5C6472",
    "accent": "#5B8DEF",
    "accent_soft": "#22314F",
    "accent_text": "#0B0D11",
    "ok": "#35C48D",
    "ok_soft": "#123A2A",
    "warn": "#E9B949",
    "warn_soft": "#3A3020",
    "danger": "#E5646E",
    "danger_soft": "#3A2126",
    "violet": "#7C5CFF",
}

# Escala de espacio: todo margen y separación sale de aquí.
SPACE = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "2xl": 32, "3xl": 48}

# Escala tipográfica.
TYPE = {
    "display": 32,
    "h1": 23,
    "h2": 17,
    "h3": 14,
    "body": 12,
    "caption": 11,
}

# Duraciones de animación, en milisegundos.
MOTION = {"fast": 140, "base": 220, "slow": 360}

RADIUS = {"card": 16, "control": 10, "pill": 999}


STYLESHEET = """
* {{ outline: 0; }}

QWidget {{
    background: {bg};
    color: {text};
    font-size: {body}px;
}}
QMainWindow, QDialog {{ background: {bg}; }}

/* --- Tipografía ------------------------------------------------------------ */
QLabel#Display {{ font-size: {display}px; font-weight: 700; }}
QLabel#H1      {{ font-size: {h1}px; font-weight: 700; }}
QLabel#H2      {{ font-size: {h2}px; font-weight: 600; }}
QLabel#H3      {{ font-size: {h3}px; font-weight: 600; }}
QLabel#Dim     {{ color: {text_dim}; }}
QLabel#Faint   {{ color: {text_faint}; font-size: {caption}px; }}
QLabel#Eyebrow {{
    color: {text_faint}; font-size: {caption}px; font-weight: 700;
    letter-spacing: 1.4px;
}}
QLabel#MetricBig    {{ font-size: 40px; font-weight: 700; }}
QLabel#MetricMedium {{ font-size: 24px; font-weight: 700; }}
QLabel#Glyph        {{ font-size: 26px; color: {accent}; }}
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
QWidget#Sidebar {{ background: {surface}; }}
QListWidget#Nav {{ background: transparent; border: none; font-size: {h3}px; }}
QListWidget#Nav::item {{
    padding: 12px 14px; margin: 2px 10px; border-radius: {radius_control}px;
    color: {text_dim};
}}
QListWidget#Nav::item:hover {{ background: {surface_2}; color: {text}; }}
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


def _tokens() -> dict[str, object]:
    values: dict[str, object] = dict(COLORS)
    values.update(TYPE)
    values.update({f"space_{k}": v for k, v in SPACE.items()})
    values.update({f"radius_{k}": v for k, v in RADIUS.items()})
    return values


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
