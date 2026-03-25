"""Small 'i' circle badge that shows an explanatory tooltip on hover or click."""

from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QLabel, QToolTip

from ui.style import ACCENT


class AiHint(QLabel):
    """Cerchietto 'i' con tooltip informativo (hover + click)."""

    def __init__(self, tooltip: str, parent=None):
        super().__init__("i", parent)
        self._tooltip = tooltip
        self.setToolTip(tooltip)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(18, 18)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"QLabel {{"
            f"  background: transparent;"
            f"  color: {ACCENT};"
            f"  font-size: 10px;"
            f"  font-weight: 700;"
            f"  font-style: italic;"
            f"  border-radius: 9px;"
            f"  border: 1.5px solid {ACCENT};"
            f"}}"
        )

    def mouseReleaseEvent(self, event):
        QToolTip.showText(self.mapToGlobal(QPoint(0, -10)), self._tooltip, self)
