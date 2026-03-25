import os
import shutil
from datetime import datetime

from config import LILY_DIR
from core.actions.base import Action
from core.i18n import t


class ScreenshotAction(Action):
    TOOL_SCHEMA = {
        "name": "screenshot",
        "description": "Cattura uno screenshot dello schermo intero o di una finestra specifica",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Nome della finestra da catturare (opzionale, se omesso cattura lo schermo intero)"}
            }
        }
    }

    def execute(self, intent: dict, config, **kwargs) -> str:
        try:
            screenshot_dir = os.path.join(LILY_DIR, "Screenshots")
            os.makedirs(screenshot_dir, exist_ok=True)

            query = intent.get("query", "").strip()
            search_terms = intent.get("search_terms", [])
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

            if query:
                return self._capture_window(query, search_terms, screenshot_dir, timestamp)
            return self._capture_fullscreen(screenshot_dir, timestamp)

        except Exception as e:
            return t("screenshot_error", e=e)

    def _capture_fullscreen(self, screenshot_dir: str, timestamp: str) -> str:
        from PySide6.QtWidgets import QApplication

        screen = QApplication.primaryScreen()
        if screen is None:
            return t("screenshot_no_screen")

        filepath = os.path.join(screenshot_dir, f"screenshot_{timestamp}.png")
        pixmap = screen.grabWindow(0)
        pixmap.save(filepath, "PNG")

        print(f"[Screenshot] Salvato: {filepath}")
        return t("screenshot_saved", path=filepath)

    def _capture_window(self, query: str, search_terms: list[str],
                        screenshot_dir: str, timestamp: str) -> str:
        from core.utils.win32 import find_window_hwnd
        from core.utils.screenshot import capture_window

        hwnd = find_window_hwnd(query, search_terms=search_terms)
        if hwnd is None:
            return t("screenshot_window_not_found", query=query)

        tmp_path = capture_window(hwnd)
        if tmp_path is None:
            return t("screenshot_capture_error", query=query)

        try:
            filepath = os.path.join(screenshot_dir, f"screenshot_{query}_{timestamp}.png")
            shutil.move(tmp_path, filepath)
        except Exception:
            filepath = tmp_path

        print(f"[Screenshot] Salvato: {filepath}")
        return t("screenshot_saved", path=filepath)
