"""Vertical icon sidebar for page navigation."""

import qtawesome as qta
from PySide6.QtCore import Signal, Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton


_PAGES = [
    ("mdi6.microphone",       "Voce"),
    ("mdi6.cog-outline",      "Impostazioni"),
    ("mdi6.chart-bar",        "Dashboard"),
    ("mdi6.text-box-outline", "Log"),
]

_ICON_SIZE = QSize(22, 22)
_ICON_COLOR = "#EAEAEA"
_ICON_ACTIVE = "#7C5CFC"


class SidebarButton(QPushButton):
    def __init__(self, icon_name: str, tooltip: str, parent=None):
        super().__init__(parent)
        self._icon_name = icon_name
        self.setToolTip(tooltip)
        self.setFixedSize(48, 48)
        self.setIconSize(_ICON_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self.set_active(False)

    def set_active(self, active: bool):
        self.setChecked(active)
        color = _ICON_ACTIVE if active else _ICON_COLOR
        self.setIcon(qta.icon(self._icon_name, color=color))
        if active:
            self.setStyleSheet(
                "QPushButton { background: rgba(124, 92, 252, 40); "
                "border: none; border-left: 3px solid #7C5CFC; border-radius: 8px; }"
            )
        else:
            self.setStyleSheet(
                "QPushButton { background: transparent; border: none; border-radius: 8px; }"
                "QPushButton:hover { background: rgba(255,255,255,8); }"
            )


class Sidebar(QWidget):
    page_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(62)
        self.setStyleSheet("background: rgba(15, 15, 25, 220); border-radius: 0;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 16, 7, 16)
        layout.setSpacing(6)

        self._buttons: list[SidebarButton] = []
        for idx, (icon, tip) in enumerate(_PAGES):
            btn = SidebarButton(icon, tip, self)
            btn.clicked.connect(lambda checked, i=idx: self._on_click(i))
            layout.addWidget(btn)
            self._buttons.append(btn)

        layout.addStretch()
        self.set_active(0)

    def _on_click(self, index: int):
        self.set_active(index)
        self.page_selected.emit(index)

    def set_active(self, index: int):
        for i, btn in enumerate(self._buttons):
            btn.set_active(i == index)
