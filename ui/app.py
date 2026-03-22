"""Lily – PySide6 UI entry point."""

import sys
import os

from PySide6.QtWidgets import QApplication

from config import Config
from core.assistant import Assistant
from ui.bridge import SignalBridge
from ui.log_capture import LogCapture
from ui.style import STYLESHEET
from ui.main_window import MainWindow
from ui.tray import TrayManager

_ICON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "lily.png")


def run_app():
    config = Config()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(STYLESHEET)

    assistant = Assistant(config)
    bridge = SignalBridge(assistant)

    # redirect stdout/stderr to log page (before anything else prints)
    sys.stdout = LogCapture(bridge, sys.stdout)
    sys.stderr = LogCapture(bridge, sys.stderr)

    window = MainWindow(config, assistant, bridge)
    tray = TrayManager(app, window, _ICON)

    window.show()
    sys.exit(app.exec())
