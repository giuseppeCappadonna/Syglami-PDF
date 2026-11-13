"""Aspetto: icone, cursori, conversioni immagine, stylesheet e tavolozza."""
import os

import pymupdf
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QCursor, QIcon, QImage, QPalette, QPixmap
from PyQt6.QtWidgets import QApplication

from sigla.config import APP_DIR

MIME_FIRMA = "application/x-firma-pdf"


ACCENT = "#3461f0"


def to_qimage(pix):
    fmt = QImage.Format.Format_RGBA8888 if pix.alpha else QImage.Format.Format_RGB888
    return QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()


_sig_cache = {}


def firma_pixmap(path, width_px=900):
    """Rende la firma (SVG o immagine) con trasparenza; restituisce (QPixmap, rapporto h/w)."""
    key = (path, width_px)
    if key not in _sig_cache:
        with pymupdf.open(path) as d:
            r = d[0].rect
            pix = d[0].get_pixmap(matrix=pymupdf.Matrix(width_px / r.width, width_px / r.width), alpha=True)
            _sig_cache[key] = (QPixmap.fromImage(to_qimage(pix)), r.height / r.width)
    return _sig_cache[key]


# icone a linea (stile Lucide), rese con PyMuPDF perché questo Qt non ha il plugin SVG
ICONS = {
    "open": '<path d="M6 14l1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"/>',
    "save": '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8"/><path d="M7 3v5h8"/>',
    "undo": '<path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/>',
    "redo": '<path d="M21 7v6h-6"/><path d="M3 17a9 9 0 0 1 9-9 9 9 0 0 1 6 2.3l3 2.7"/>',
    "zoom-in": '<circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/><path d="M11 8v6"/><path d="M8 11h6"/>',
    "zoom-out": '<circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/><path d="M8 11h6"/>',
    "fit": '<path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/>',
    "settings": '<path d="M21 4h-7"/><path d="M10 4H3"/><path d="M21 12h-9"/><path d="M8 12H3"/><path d="M21 20h-5"/><path d="M12 20H3"/><path d="M14 2v4"/><path d="M8 10v4"/><path d="M16 18v4"/>',
    "prev": '<path d="M15 18l-6-6 6-6"/>',
    "next": '<path d="M9 18l6-6-6-6"/>',
    "down": '<path d="M6 9l6 6 6-6"/>',
    "check": '<path d="M20 6L9 17l-5-5"/>',
    "pen": '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    "folder": '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2z"/>',
    "file": '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><path d="M14 2v6h6"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "layers": '<path d="M12 2l10 5-10 5L2 7z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>',
    "files": '<rect x="8" y="8" width="14" height="14" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    "panel": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M17 8l-5-5-5 5"/><path d="M12 3v12"/>',
    "wand": '<path d="M15 4V2"/><path d="M15 16v-2"/><path d="M8 9h2"/><path d="M20 9h2"/><path d="M17.8 11.8L19 13"/><path d="M17.8 6.2L19 5"/><path d="M3 21l9-9"/><path d="M12.2 6.2L11 5"/>',
    "signature": '<path d="M3 17c3-1 4-9 6-9s-1 9 1 9 3-5 5-5-1 4 1 4 2-2 4-2"/><path d="M3 21h18"/>',
    "list": '<path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M3 6h.01"/><path d="M3 12h.01"/><path d="M3 18h.01"/>',
    "more": '<circle cx="12" cy="12" r="1.2"/><circle cx="19" cy="12" r="1.2"/><circle cx="5" cy="12" r="1.2"/>',
    "star": '<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z"/>',
}


def icon_pixmap(name, color="#1f2a44", px=20, width=2.0):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" '
           f'stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round">'
           f'{ICONS[name]}</svg>')
    with pymupdf.open(stream=svg.encode(), filetype="svg") as d:
        z = px * 2 / 24
        pm = QPixmap.fromImage(to_qimage(d[0].get_pixmap(matrix=pymupdf.Matrix(z, z), alpha=True)))
    pm.setDevicePixelRatio(2)
    return pm


def icon(name, color="#1f2a44"):
    ic = QIcon(icon_pixmap(name, color))
    ic.addPixmap(icon_pixmap(name, "#b4bccd"), QIcon.Mode.Disabled)
    return ic


def style_assets():
    """PNG per spunta e frecce dello stylesheet (Qt qui non legge SVG)."""
    d = os.path.expanduser("~/.cache/sigla")
    os.makedirs(d, exist_ok=True)
    out = {}
    for name, color, px, w in (("check", "#ffffff", 14, 3.2), ("down", "#5b6680", 14, 2.2)):
        p = os.path.join(d, f"{name}.png")
        icon_pixmap(name, color, px, w).toImage().save(p)
        out[name] = p
    return out


def app_icon_pixmap(px):
    pm = QPixmap(os.path.join(APP_DIR, "icona.png")).scaled(
        px * 2, px * 2, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    pm.setDevicePixelRatio(2)
    return pm


_stamp_cursor = None


def stamp_cursor():
    global _stamp_cursor
    if _stamp_cursor is None:
        with pymupdf.open(os.path.join(APP_DIR, "timbro.svg")) as d:
            pix = QPixmap.fromImage(to_qimage(d[0].get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=True)))
        pix.setDevicePixelRatio(2)  # nitido anche su schermi HiDPI
        _stamp_cursor = QCursor(pix, 16, 30)  # punto attivo: l'impronta del timbro
    return _stamp_cursor


STYLE = f"""
QMainWindow, QDialog {{ background: #f6f7fb; }}
QToolBar {{ background: white; border: none; border-bottom: 1px solid #e1e5ee; padding: 6px 10px; spacing: 6px; }}
QToolButton {{ padding: 6px 10px; border-radius: 8px; color: #1f2a44; font-weight: 500; }}
QToolButton:hover {{ background: #eef2ff; }}
QToolButton:pressed {{ background: #dfe6ff; }}
QToolButton:disabled {{ color: #a0a8bb; }}
QToolButton::menu-button {{ border: none; width: 16px; }}
QToolButton#primary {{ background: {ACCENT}; color: white; padding: 6px 14px; }}
QToolButton#info {{ padding: 2px; margin: 0 4px; border-radius: 10px; }}
QToolButton#info:hover {{ background: #eef2ff; }}
QToolButton#primary:hover {{ background: #2a52d6; }}
QToolButton#primary:disabled {{ background: #c9d3f5; color: white; }}
QToolBar QSpinBox {{ background: white; border: 1px solid #d5dbe8; border-radius: 6px; padding: 3px; }}
QToolBar::separator {{ background: #e1e5ee; width: 1px; margin: 6px 6px; }}
QPushButton#primary {{ background: {ACCENT}; color: white; border-color: {ACCENT}; font-weight: 600; }}
QPushButton#primary:hover {{ background: #2a52d6; color: white; }}
QPushButton#soft {{ background: #eef2ff; border: 1px solid #c9d6ff; color: {ACCENT}; font-weight: 600; }}
QPushButton#soft:hover {{ background: #e2e9ff; border-color: {ACCENT}; }}
QPushButton#cta {{ border: 2px dashed #b9c6f5; background: #f5f7ff; color: {ACCENT}; padding: 18px; font-weight: 600; border-radius: 12px; }}
QPushButton#recent {{ border: none; background: transparent; text-align: left; padding: 7px 8px; color: #1f2a44; }}
QPushButton#recent:hover {{ background: #eef2ff; color: {ACCENT}; }}
QFrame#card {{ background: white; border: 1px solid #e1e5ee; border-radius: 16px; }}
QLabel#hero {{ font-size: 22px; font-weight: 700; color: #1f2a44; }}
QFrame#toast {{ background: #1f2a44; border-radius: 12px; }}
QPushButton#tile {{ background: white; border: 1px solid #e1e5ee; border-radius: 14px; }}
QPushButton#tile:hover {{ border: 2px solid {ACCENT}; background: #f5f7ff; }}
QPushButton#tile QLabel {{ background: transparent; }}
QLabel#tiletitle {{ font-weight: 700; color: #1f2a44; }}
QFrame#coach {{ background: white; border: 1px solid #d5dcf5; border-radius: 12px; }}
QFrame#coach QLabel {{ color: #1f2a44; }}
QPushButton#coachbtn {{ background: {ACCENT}; color: white; border: none; padding: 6px 12px; font-weight: 600; }}
QPushButton#coachbtn:hover {{ background: #2a52d6; color: white; }}
QFrame#toast QLabel {{ color: white; }}
QPushButton#toastbtn {{ background: transparent; border: 1px solid #5b6a92; color: #c9d6ff; padding: 5px 12px; }}
QPushButton#toastbtn:hover {{ background: #2c3a5e; color: white; }}
QMenu {{ background: white; border: 1px solid #e1e5ee; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 6px 18px 6px 10px; border-radius: 6px; color: #1f2a44; }}
QMenu::item:selected {{ background: #eef2ff; }}
QToolTip {{ background: #1f2a44; color: white; border: none; padding: 5px 8px; border-radius: 6px; }}
QLabel#zoom {{ min-width: 52px; color: #5b6680; }}
QWidget#side {{ background: white; border-left: 1px solid #e1e5ee; }}
QLabel#section {{ font-size: 15px; font-weight: 600; color: #1f2a44; }}
QLabel#hint {{ color: #6b7590; }}
QToolButton#variant {{ background: white; border: 1px solid #e1e5ee; border-radius: 12px; padding: 8px; color: #8a93a8; }}
QToolButton#variant:hover {{ border-color: {ACCENT}; }}
QToolButton#variant:checked {{ border: 2px solid {ACCENT}; background: #f5f7ff; }}
QSlider::groove:horizontal {{ height: 4px; background: #d5dbe8; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: white; border: 2px solid {ACCENT}; width: 14px; margin: -7px 0; border-radius: 9px; }}
QComboBox {{ background: white; border: 1px solid #d5dbe8; border-radius: 8px; padding: 5px 8px; color: #1f2a44;
             min-height: 22px; }}
QComboBox:hover, QDateEdit:hover {{ border-color: #aab6e8; }}
QComboBox:focus, QDateEdit:focus {{ border-color: {ACCENT}; }}
QComboBox:disabled {{ color: #a0a8bb; background: #eef0f5; }}
QComboBox QAbstractItemView {{ background: white; border: 1px solid #e1e5ee; border-radius: 8px; padding: 4px;
                               outline: none; color: #1f2a44; selection-background-color: #eef2ff;
                               selection-color: {ACCENT}; }}
QComboBox QAbstractItemView::item {{ min-height: 30px; padding: 0 10px; border-radius: 6px; color: #1f2a44; }}
QComboBox QAbstractItemView::item:hover {{ background: #eef2ff; color: {ACCENT}; }}
QComboBox QAbstractItemView::item:selected {{ background: #e4eaff; color: {ACCENT}; }}
QCalendarWidget QWidget {{ alternate-background-color: #f6f7fb; }}
QCalendarWidget QAbstractItemView {{ background: white; color: #1f2a44; selection-background-color: {ACCENT};
                                     selection-color: white; outline: none; }}
QCalendarWidget QAbstractItemView:disabled {{ color: #c3cad9; }}
QCalendarWidget QWidget#qt_calendar_navigationbar {{ background: white; border-bottom: 1px solid #e1e5ee; }}
QCalendarWidget QToolButton {{ color: #1f2a44; font-weight: 600; padding: 4px 8px; }}
QCalendarWidget QToolButton:hover {{ background: #eef2ff; }}
QCalendarWidget QSpinBox {{ background: white; color: #1f2a44; }}
QLabel#subsection {{ font-weight: 600; color: #1f2a44; }}
QFrame#opts {{ background: #f6f7fb; border: 1px solid #e1e5ee; border-radius: 10px; }}
QCheckBox {{ color: #1f2a44; spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid #b8c0d4; background: white; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QDateEdit {{ background: white; border: 1px solid #d5dbe8; border-radius: 8px; padding: 5px 8px; }}
QDateEdit:disabled, QLineEdit:disabled {{ color: #a0a8bb; background: #eef0f5; }}
QListWidget {{ border: none; background: transparent; outline: none; }}
QListWidget#firme::item {{ border: 1px solid #e1e5ee; border-radius: 10px; padding: 8px 4px; width: 210px;
                     background: white; color: #1f2a44; }}
QListWidget#firme::item:hover {{ border-color: {ACCENT}; background: #f5f7ff; }}
QListWidget#firme::item:selected {{ border: 2px solid {ACCENT}; background: #eef2ff; color: #1f2a44; }}
QWidget#thumbs_panel {{ background: #f0f2f7; border-right: 1px solid #e1e5ee; }}
QListWidget#thumbs::item {{ border: 2px solid transparent; border-radius: 6px; padding: 4px; width: 112px; color: #5b6680; }}
QListWidget#thumbs::item:hover {{ background: #e4e8f1; }}
QListWidget#thumbs::item:selected {{ border-color: {ACCENT}; background: #e4eaff; color: {ACCENT}; }}
QListWidget#files {{ background: white; border: 1px solid #e1e5ee; border-radius: 10px; padding: 4px; }}
QListWidget#files::item {{ padding: 6px; border-radius: 6px; color: #1f2a44; }}
QListWidget#files::item:selected {{ background: #eef2ff; }}
QRadioButton {{ color: #1f2a44; spacing: 8px; }}
QProgressBar {{ border: none; background: #e1e5ee; border-radius: 4px; height: 8px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}
QDialog QSpinBox {{ background: white; border: 1px solid #d5dbe8; border-radius: 8px; padding: 5px 8px; }}
QPushButton {{ background: white; border: 1px solid #d5dbe8; border-radius: 8px; padding: 7px 14px; color: #1f2a44; }}
QPushButton:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}
QPushButton:default {{ background: {ACCENT}; color: white; border-color: {ACCENT}; }}
QLineEdit {{ background: white; border: 1px solid #d5dbe8; border-radius: 8px; padding: 4px 8px; min-height: 22px; }}
QLineEdit:focus {{ border-color: {ACCENT}; }}
QStatusBar {{ background: white; border-top: 1px solid #e1e5ee; color: #5b6680; }}
QStatusBar QLabel {{ color: #5b6680; padding: 2px 6px; }}
QScrollBar:vertical {{ background: transparent; width: 12px; }}
QScrollBar::handle:vertical {{ background: #c3cad9; border-radius: 5px; min-height: 40px; margin: 2px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; }}
QScrollBar::handle:horizontal {{ background: #c3cad9; border-radius: 5px; min-width: 40px; margin: 2px; }}
"""


def light_palette():
    """Tavolozza chiara completa: lo stile è chiaro, i colori del tema di sistema (es. GNOME scuro) non devono
    filtrare nei widget non coperti dal QSS (menu a tendina, calendario, finestre di sistema)."""
    p = QPalette()
    for role, c in (("Window", "#f6f7fb"), ("WindowText", "#1f2a44"), ("Base", "#ffffff"), ("AlternateBase", "#f6f7fb"),
                    ("Text", "#1f2a44"), ("Button", "#ffffff"), ("ButtonText", "#1f2a44"), ("BrightText", "#ffffff"),
                    ("Highlight", "#e4eaff"), ("HighlightedText", "#1f2a44"), ("ToolTipBase", "#1f2a44"),
                    ("ToolTipText", "#ffffff"), ("PlaceholderText", "#a0a8bb"), ("Link", ACCENT), ("Mid", "#d5dbe8"),
                    ("Light", "#ffffff"), ("Midlight", "#eef0f5"), ("Dark", "#b8c0d4"), ("Shadow", "#8a93a8")):
        p.setColor(getattr(QPalette.ColorRole, role), QColor(c))
    for role in ("WindowText", "Text", "ButtonText"):
        p.setColor(QPalette.ColorGroup.Disabled, getattr(QPalette.ColorRole, role), QColor("#a0a8bb"))
    return p


def style_extra(a, base_pt=None):
    """Parte dello stile che usa le immagini generate da style_assets() e il carattere di sistema."""
    base = base_pt or QApplication.font().pointSizeF() or 10
    # titoli in proporzione al carattere di sistema: in px risultavano più piccoli del testo con caratteri grandi
    return f"""
QLabel#section {{ font-size: {base * 1.3:.1f}pt; }}
QLabel#hero {{ font-size: {base * 1.9:.1f}pt; }}
QLabel#tiletitle {{ font-size: {base * 1.15:.1f}pt; }}
QCheckBox::indicator:checked {{ image: url({a["check"]}); }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 26px; }}
QComboBox::down-arrow, QDateEdit::down-arrow {{ image: url({a["down"]}); width: 12px; height: 12px; }}
"""
