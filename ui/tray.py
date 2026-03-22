"""Native PySide6 system-tray icon (replaces core/tray.py pystray)."""

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QSystemTrayIcon, QMenu


class TrayManager:
    def __init__(self, app, main_window, icon_path: str):
        self._app = app
        self._window = main_window

        self._tray = QSystemTrayIcon(QIcon(icon_path), app)
        menu = QMenu()
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
