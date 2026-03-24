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

    # Initialize locale from config before any UI/string imports
    from core.i18n import set_locale
    set_locale(getattr(config, "language", "it"))

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(STYLESHEET)

    # Show welcome wizard on first run
    if not config.setup_done:
        from ui.welcome import WelcomeWizard
        wizard = WelcomeWizard()
        wizard.exec()
        config.setup_done = True
        config.save()

    # Download Whisper model if not cached
    from ui.model_download import is_model_cached, ModelDownloadDialog
    whisper_model = config.whisper_model
    if not is_model_cached(whisper_model):
        dlg = ModelDownloadDialog(whisper_model)
        dlg.exec()
        if not dlg.success:
            print(f"[Whisper] Download fallito: {dlg.error_msg}")

    assistant = Assistant(config)
    bridge = SignalBridge(assistant)

    # redirect stdout/stderr to log page (before anything else prints)
    sys.stdout = LogCapture(bridge, sys.stdout)
    sys.stderr = LogCapture(bridge, sys.stderr)

    window = MainWindow(config, assistant, bridge)
    tray = TrayManager(app, window, _ICON)

    window.show()
    sys.exit(app.exec())
