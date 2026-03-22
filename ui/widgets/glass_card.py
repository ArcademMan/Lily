"""Reusable semi-transparent card with glass effect."""

from PySide6.QtWidgets import QFrame, QVBoxLayout


class GlassCard(QFrame):
    """A rounded, semi-transparent container."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "GlassCard {"
            "  background: rgba(255, 255, 255, 8);"
            "  border: 1px solid rgba(255, 255, 255, 12);"
            "  border-radius: 12px;"
            "}"
        )
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)

    def body(self) -> QVBoxLayout:
        return self._layout
