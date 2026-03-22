import os
from datetime import datetime

from core.actions.base import Action


class ScreenshotAction(Action):
    def execute(self, intent: dict, config) -> str:
        try:
            from PySide6.QtWidgets import QApplication
            from PySide6.QtCore import QTimer

            # Screenshot directory — next to the executable / main.py
            import sys
            if getattr(sys, 'frozen', False):
                base = os.path.dirname(sys.executable)
            else:
                base = os.path.dirname(os.path.abspath(sys.modules['__main__'].__file__))
            screenshot_dir = os.path.join(base, "Screenshots")
            os.makedirs(screenshot_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filepath = os.path.join(screenshot_dir, f"screenshot_{timestamp}.png")

            screen = QApplication.primaryScreen()
            if screen is None:
                return "Nessuno schermo trovato."

            pixmap = screen.grabWindow(0)
            pixmap.save(filepath, "PNG")

            print(f"[Screenshot] Salvato: {filepath}")
            return "Screenshot salvato."
        except Exception as e:
            return f"Errore screenshot: {e}"
