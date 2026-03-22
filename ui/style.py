"""Glassmorphism theme: QSS stylesheet + Windows 10 DWM blur."""

import ctypes
import ctypes.wintypes

# ── Colour palette ────────────────────────────────────────────────
BG = "rgba(25, 25, 35, 200)"
CARD_BG = "rgba(255, 255, 255, 8)"
CARD_BORDER = "rgba(255, 255, 255, 15)"
ACCENT = "#7C5CFC"
ACCENT_HOVER = "#9B82FD"
TEXT = "#EAEAEA"
TEXT_SEC = "#888888"
SIDEBAR_BG = "rgba(15, 15, 25, 220)"
INPUT_BG = "rgba(255, 255, 255, 6)"
INPUT_BORDER = "rgba(255, 255, 255, 20)"
INPUT_FOCUS = ACCENT

# ── Global QSS ───────────────────────────────────────────────────
STYLESHEET = f"""
/* ── base ─────────────────────────────── */
QWidget {{
    color: {TEXT};
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}}
QMainWindow, #CentralWidget {{
    background: transparent;
}}

/* ── scroll area ──────────────────────── */
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(255,255,255,30);
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
    height: 0;
}}

/* ── inputs ───────────────────────────── */
QLineEdit, QComboBox, QSpinBox {{
    background: {INPUT_BG};
    border: 1px solid {INPUT_BORDER};
    border-radius: 8px;
    padding: 8px 12px;
    color: {TEXT};
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 1px solid {INPUT_FOCUS};
}}
QComboBox::drop-down {{
    border: none;
    width: 30px;
}}
QComboBox::down-arrow {{
    image: url(assets/arrow_down.svg);
    width: 12px;
    height: 12px;
}}
QComboBox QAbstractItemView {{
    background: rgb(30, 30, 45);
    border: 1px solid {CARD_BORDER};
    border-radius: 6px;
    selection-background-color: {ACCENT};
    padding: 4px;
    outline: none;
}}

/* ── buttons ──────────────────────────── */
QPushButton {{
    background: {ACCENT};
    border: none;
    border-radius: 8px;
    padding: 9px 24px;
    color: white;
    font-weight: 600;
}}
QPushButton:hover {{
    background: {ACCENT_HOVER};
}}
QPushButton:pressed {{
    background: {ACCENT};
}}
QPushButton#flatBtn {{
    background: transparent;
    padding: 6px;
}}
QPushButton#flatBtn:hover {{
    background: rgba(255,255,255,10);
}}

/* ── checkbox / toggle ────────────────── */
QCheckBox {{
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 18px; height: 18px;
    border: 2px solid {INPUT_BORDER};
    border-radius: 4px;
    background: {INPUT_BG};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

/* ── slider ───────────────────────────── */
QSlider::groove:horizontal {{
    background: rgba(255,255,255,15);
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    width: 16px; height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 2px;
}}

/* ── plain text (log) ─────────────────── */
QPlainTextEdit {{
    background: rgba(0, 0, 0, 60);
    border: 1px solid {CARD_BORDER};
    border-radius: 10px;
    padding: 10px;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
    color: {TEXT};
    selection-background-color: {ACCENT};
}}

/* ── labels ───────────────────────────── */
QLabel#sectionTitle {{
    font-size: 20px;
    font-weight: 700;
}}
QLabel#secondary {{
    color: {TEXT_SEC};
    font-size: 12px;
}}

/* ── tooltip ──────────────────────────── */
QToolTip {{
    background: rgb(35, 35, 50);
    border: 1px solid {CARD_BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {TEXT};
}}
"""


# ── Windows 10 acrylic blur ──────────────────────────────────────
class _ACCENT_POLICY(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_int),
    ]


class _WINCOMPATTRDATA(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.POINTER(_ACCENT_POLICY)),
        ("SizeOfData", ctypes.c_size_t),
    ]


def enable_blur(hwnd: int):
    """Enable acrylic-like blur behind the window (Windows 10+)."""
    try:
        accent = _ACCENT_POLICY()
        accent.AccentState = 3  # ACCENT_ENABLE_BLURBEHIND
        accent.GradientColor = 0xCC191923  # AABBGGRR – semi-transparent dark
        data = _WINCOMPATTRDATA()
        data.Attribute = 19  # WCA_ACCENT_POLICY
        data.Data = ctypes.pointer(accent)
        data.SizeOfData = ctypes.sizeof(accent)
        ctypes.windll.user32.SetWindowCompositionAttribute(
            hwnd, ctypes.byref(data)
        )
    except Exception:
        pass  # fallback: solid dark bg still looks fine
