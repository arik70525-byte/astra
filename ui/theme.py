"""Dark AURA visual theme."""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

ACCENT = "#ffd54a"
ACCENT_HOVER = "#ffe27a"
BG = "#0b0b0e"
PANEL = "#111216"
SURFACE = "#17181e"
SURFACE_2 = "#1e2028"
BORDER = "#272932"
TEXT = "#f4f4f6"
MUTED = "#9295a3"
DANGER = "#ff6b7a"
SUCCESS = "#5bdd9a"

QSS = f"""
* {{
    outline: none;
}}
QWidget {{
    background: {BG};
    color: {TEXT};
    font-family: "Segoe UI", "Segoe UI Variable Text", sans-serif;
    font-size: 13px;
}}
QMainWindow, QDialog {{
    background: {BG};
}}
QFrame#Sidebar {{
    background: #08090b;
    border-right: 1px solid #1c1d24;
}}
QFrame#PlayerBar {{
    background: #0f1014;
    border-top: 1px solid #23252d;
}}
QFrame#Card, QFrame#SettingsCard {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}
QFrame#SoftCard {{
    background: #14151a;
    border: 1px solid #20222b;
    border-radius: 14px;
}}
QFrame#Hero {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #242017, stop:0.52 #17191f, stop:1 #13141a);
    border: 1px solid #343025;
    border-radius: 22px;
}}
QFrame#Banner {{
    background: #191a20;
    border: 1px solid #2a2c36;
    border-left: 3px solid {ACCENT};
    border-radius: 10px;
}}
QLabel {{
    background: transparent;
}}
QLabel#Logo {{
    font-size: 23px;
    font-weight: 800;
    letter-spacing: 3px;
    color: {TEXT};
}}
QLabel#LogoDot {{
    color: {ACCENT};
    font-size: 26px;
    font-weight: 900;
}}
QLabel#PageTitle {{
    font-size: 30px;
    font-weight: 750;
    color: {TEXT};
}}
QLabel#SectionTitle {{
    font-size: 18px;
    font-weight: 650;
    color: {TEXT};
}}
QLabel#Muted {{
    color: {MUTED};
}}
QLabel#Tiny {{
    color: {MUTED};
    font-size: 11px;
}}
QLabel#Accent {{
    color: {ACCENT};
    font-weight: 600;
}}
QLabel#Danger {{
    color: {DANGER};
}}
QLabel#Success {{
    color: {SUCCESS};
}}
QLabel#HeroTitle {{
    font-size: 38px;
    font-weight: 800;
    color: #ffffff;
}}
QLabel#HeroText {{
    font-size: 14px;
    color: #c4c1b7;
}}
QLabel#TrackTitle {{
    font-weight: 600;
}}
QPushButton {{
    background: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 8px 14px;
    min-height: 18px;
}}
QPushButton:hover {{
    background: {SURFACE_2};
    border-color: #3a3d49;
}}
QPushButton:pressed {{
    background: #262832;
}}
QPushButton:disabled {{
    color: #5d606c;
    background: #14151a;
    border-color: #20222a;
}}
QPushButton#Accent {{
    background: {ACCENT};
    color: #17140b;
    border: none;
    font-weight: 700;
}}
QPushButton#Accent:hover {{
    background: {ACCENT_HOVER};
}}
QPushButton#Ghost {{
    background: transparent;
    border: 1px solid transparent;
    color: {MUTED};
}}
QPushButton#Ghost:hover {{
    background: #1a1b22;
    color: {TEXT};
}}
QPushButton#Icon {{
    background: transparent;
    border: none;
    border-radius: 18px;
    padding: 0;
    color: #d9dae0;
    font-size: 18px;
}}
QPushButton#Icon:hover {{
    background: #22242c;
}}
QPushButton#Icon:checked {{
    color: {ACCENT};
}}
QPushButton#Play {{
    background: {ACCENT};
    color: #15120a;
    border: none;
    border-radius: 22px;
    font-size: 20px;
    font-weight: 900;
}}
QPushButton#Play:hover {{
    background: {ACCENT_HOVER};
}}
QPushButton#Nav {{
    background: transparent;
    border: none;
    border-radius: 10px;
    padding: 10px 12px;
    text-align: left;
    color: #aeb0ba;
    font-size: 13px;
}}
QPushButton#Nav:hover {{
    background: #14151a;
    color: {TEXT};
}}
QPushButton#Nav:checked {{
    background: #1b1c22;
    color: {TEXT};
    font-weight: 600;
}}
QPushButton#Chip {{
    background: #17181e;
    border: 1px solid #2a2c35;
    border-radius: 15px;
    padding: 6px 12px;
    color: #c7c9d1;
}}
QPushButton#Chip:checked {{
    background: #2a2516;
    border-color: #6c5b1e;
    color: {ACCENT};
}}
QLineEdit, QPlainTextEdit, QTextEdit, QTextBrowser, QSpinBox, QDoubleSpinBox {{
    background: #111217;
    border: 1px solid #2a2c35;
    border-radius: 10px;
    padding: 9px 11px;
    selection-background-color: #5d4b13;
    selection-color: #fff;
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: #6e5b1c;
}}
QLineEdit#Search {{
    background: #15161b;
    border-radius: 16px;
    padding: 12px 16px;
    font-size: 14px;
}}
QComboBox {{
    background: #14151b;
    border: 1px solid #2a2c35;
    border-radius: 10px;
    padding: 8px 12px;
    min-height: 20px;
}}
QComboBox:hover {{
    border-color: #3a3d49;
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background: #17181e;
    border: 1px solid #2f313b;
    selection-background-color: #2b2615;
    selection-color: {ACCENT};
    padding: 4px;
}}
QSpinBox, QDoubleSpinBox {{
    padding: 6px 8px;
}}
QCheckBox {{
    spacing: 9px;
    color: #d1d3db;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1px solid #3a3d49;
    background: #111217;
}}
QCheckBox::indicator:hover {{
    border-color: #6e5b1c;
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QTabWidget::pane {{
    border: none;
    background: transparent;
}}
QTabBar::tab {{
    background: transparent;
    color: {MUTED};
    padding: 9px 16px;
    margin-right: 4px;
    border-radius: 9px;
    border: none;
}}
QTabBar::tab:hover {{
    color: {TEXT};
    background: #17181e;
}}
QTabBar::tab:selected {{
    color: #15120a;
    background: {ACCENT};
    font-weight: 700;
}}
QTableWidget {{
    background: transparent;
    border: none;
    gridline-color: transparent;
    selection-background-color: #24220f;
    selection-color: {TEXT};
    alternate-background-color: #101116;
}}
QTableWidget::item {{
    padding: 7px 8px;
    border-bottom: 1px solid #191a20;
}}
QTableWidget::item:selected {{
    background: #2a2613;
    color: {TEXT};
}}
QHeaderView::section {{
    background: transparent;
    color: {MUTED};
    border: none;
    border-bottom: 1px solid #292b34;
    padding: 8px;
    font-size: 11px;
    text-transform: uppercase;
}}
QListWidget {{
    background: transparent;
    border: none;
    padding: 2px;
}}
QListWidget::item {{
    padding: 9px 10px;
    border-radius: 9px;
    color: #c9cbd3;
}}
QListWidget::item:hover {{
    background: #17181e;
}}
QListWidget::item:selected {{
    background: #24210f;
    color: {ACCENT};
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #30323c;
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #464956;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
}}
QScrollBar::handle:horizontal {{
    background: #30323c;
    border-radius: 5px;
    min-width: 30px;
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: #2c2e37;
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: #fff;
    width: 12px;
    margin: -4px 0;
    border-radius: 6px;
}}
QSlider::handle:horizontal:hover {{
    background: {ACCENT};
}}
QProgressBar {{
    background: #1b1c23;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 4px;
}}
QMenu {{
    background: #17181e;
    border: 1px solid #30323c;
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{
    padding: 8px 24px 8px 12px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: #2b2716;
    color: {ACCENT};
}}
QToolTip {{
    background: #20222a;
    color: {TEXT};
    border: 1px solid #3a3d49;
    padding: 6px;
}}
QSplitter::handle {{
    background: #23252d;
}}
QMessageBox {{
    background: {PANEL};
}}
QDialogButtonBox QPushButton {{
    min-width: 88px;
}}
QTextBrowser#ChatView {{
    background: #0d0e12;
    border: 1px solid #21232b;
    border-radius: 14px;
    padding: 10px;
}}
QPlainTextEdit#CodeEditor, QPlainTextEdit#TerminalView {{
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12px;
    background: #0a0b0e;
    border: 1px solid #252731;
    border-radius: 12px;
}}
QPlainTextEdit#TerminalView {{
    color: #c8f7d4;
}}
QLabel#Cover {{
    background: #1a1b21;
    border-radius: 10px;
}}
QToolButton {{
    background: transparent;
    border: none;
    color: {MUTED};
    padding: 4px;
}}
QToolButton:hover {{
    color: {TEXT};
}}
"""


PALETTES: dict[str, dict[str, str]] = {
    "sunset": {
        "name": "Sunset", "accent": "#ff8a4c", "hover": "#ffab7d",
        "glow": "#ff5d7d", "description": "тёплый закат · оранжевый и коралловый",
    },
    "amber": {
        "name": "Amber", "accent": "#ffd54a", "hover": "#ffe27a",
        "glow": "#ff9f43", "description": "классический янтарь AURA",
    },
    "aurora": {
        "name": "Aurora", "accent": "#55e6c1", "hover": "#8bf5da",
        "glow": "#43b7ff", "description": "полярное сияние · мята и голубой",
    },
    "cyan": {
        "name": "Cyber Cyan", "accent": "#4cd8ff", "hover": "#8ce7ff",
        "glow": "#7b6cff", "description": "неон · электрический голубой",
    },
    "magenta": {
        "name": "Neon Magenta", "accent": "#ff59cf", "hover": "#ff92df",
        "glow": "#8b5cff", "description": "неоновая ночь · розовый и фиолетовый",
    },
    "violet": {
        "name": "Violet", "accent": "#b596ff", "hover": "#ccb8ff",
        "glow": "#ff74c8", "description": "мягкий фиолетовый с розовым свечением",
    },
    "lime": {
        "name": "Lime", "accent": "#b6ff5c", "hover": "#d0ff96",
        "glow": "#45e0a1", "description": "кислотный лайм · энергия и контраст",
    },
    "sakura": {
        "name": "Sakura", "accent": "#ffb3d9", "hover": "#ffd1e8",
        "glow": "#ff6fae", "description": "сакура · мягкий розовый и жемчуг",
    },
    "steel": {
        "name": "Steel", "accent": "#c9d6e8", "hover": "#e6eef9",
        "glow": "#7aa7ff", "description": "графит · холодный металл и синий",
    },
}

_ACCENT_PAIRS = {
    "#ffd54a": "accent",
    "#ffe27a": "hover",
    "#6e5b1c": "border",
    "#6c5b1e": "border",
    "#5d4b13": "border",
    "#2b2615": "tint",
    "#2a2516": "tint",
    "#2b2716": "tint",
    "#2a2613": "tint",
    "#24220f": "tint",
    "#24210f": "tint",
    "#242017": "tint",
    "#343025": "border",
    "#17140b": "deep",
    "#15120a": "on_accent",
    "#c4c1b7": "soft_text",
}


def _mix(first: str, second: str, amount: float) -> str:
    """Mix two hex colours (amount = share of the first colour)."""
    a = QColor(first)
    b = QColor(second)
    amount = max(0.0, min(1.0, float(amount)))
    return QColor(
        round(a.red() * amount + b.red() * (1 - amount)),
        round(a.green() * amount + b.green() * (1 - amount)),
        round(a.blue() * amount + b.blue() * (1 - amount)),
    ).name()


def accent_colors(accent: str = "sunset") -> dict[str, str]:
    chosen = PALETTES.get(str(accent or "sunset"), PALETTES["sunset"])
    base = chosen["accent"]
    return {
        **chosen,
        "accent": base,
        "hover": chosen["hover"],
        "glow": chosen["glow"],
        "tint": _mix(base, BG, 0.16),
        "border": _mix(base, BG, 0.34),
        "deep": _mix(base, BG, 0.07),
        "on_accent": _mix(base, "#050506", 0.12),
        "soft_text": _mix(base, TEXT, 0.28),
    }


def styled_qss(accent: str = "sunset") -> str:
    colors = accent_colors(accent)
    text = QSS
    for old, key in _ACCENT_PAIRS.items():
        text = text.replace(old, colors[key])
    return text


def apply_theme(app: QApplication, accent: str = "sunset") -> None:
    """Apply the dark theme and a runtime-selectable accent palette."""
    global ACCENT, ACCENT_HOVER
    colors = accent_colors(accent)
    ACCENT = colors["accent"]
    ACCENT_HOVER = colors["hover"]
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor("#111217"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#15161b"))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(SURFACE))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(colors["on_accent"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#20222a"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT))
    app.setPalette(palette)
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    app.setProperty("auraAccent", str(accent or "sunset"))
    app.setStyleSheet(styled_qss(accent))
