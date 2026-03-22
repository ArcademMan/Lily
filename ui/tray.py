"""Native PySide6 system-tray icon (replaces core/tray.py pystray)."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPainterPath
from PySide6.QtWidgets import QSystemTrayIcon, QMenu


def _make_circle_icon(icon_path: str, size: int = 64) -> QIcon:
    """Crea un'icona circolare per il tray."""
    src = QPixmap(icon_path).scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    if src.width() != size or src.height() != size:
        x = (src.width() - size) // 2
        y = (src.height() - size) // 2
        src = src.copy(x, y, size, size)

    result = QPixmap(size, size)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addEllipse(0, 0, size, size)
    painter.setClipPath(clip)
    painter.drawPixmap(0, 0, src)
    painter.end()
    return QIcon(result)


_MENU_STYLE = """
QMenu {
    background-color: #1E1E2D;
    border: 1px solid #333355;
    border-radius: 6px;
    padding: 4px 0;
}
QMenu::item {
    color: #CCCCCC;
    padding: 6px 24px;
}
QMenu::item:selected {
    background-color: #7C5CFC;
    color: #FFFFFF;
}
QMenu::separator {
    height: 1px;
    background: #333355;
    margin: 4px 8px;
}
"""


class TrayManager:
    def __init__(self, app, main_window, icon_path: str):
        self._app = app
        self._window = main_window

        self._tray = QSystemTrayIcon(_make_circle_icon(icon_path), app)
        menu = QMenu()
        menu.setStyleSheet(_MENU_STYLE)
        menu.addAction("Apri", self._show)
        menu.addSeparator()
        menu.addAction("Esci", self._quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)
        self._tray.setToolTip("Lily")
        self._tray.show()

    def _show(self):
        self._window.show_and_raise()

    def _quit(self):
        self._window.allow_close()
        self._app.quit()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show()
