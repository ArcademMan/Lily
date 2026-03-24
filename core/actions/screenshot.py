import os
from datetime import datetime

from config import LILY_DIR
from core.actions.base import Action
from core.i18n import t


class ScreenshotAction(Action):
    TOOL_SCHEMA = {
        "name": "screenshot",
        "description": "Cattura uno screenshot dello schermo",
        "parameters": {"type": "object", "properties": {}}
    }

    def execute(self, intent: dict, config, **kwargs) -> str:
        try:
            from PySide6.QtWidgets import QApplication

            screenshot_dir = os.path.join(LILY_DIR, "Screenshots")
            os.makedirs(screenshot_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filepath = os.path.join(screenshot_dir, f"screenshot_{timestamp}.png")

            screen = QApplication.primaryScreen()
            if screen is None:
                return t("screenshot_no_screen")

            pixmap = screen.grabWindow(0)
            pixmap.save(filepath, "PNG")

            print(f"[Screenshot] Salvato: {filepath}")
            return t("screenshot_saved", path=filepath)
        except Exception as e:
            return t("screenshot_error", e=e)
