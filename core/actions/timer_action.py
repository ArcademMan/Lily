import re
import threading
import winsound

from core.signal import Signal
from core.actions.base import Action


class _TimerNotifier:
    """Emits signal when timer fires."""
    notify = Signal()

    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


class TimerAction(Action):
    def execute(self, intent: dict, config) -> str:
        parameter = intent.get("parameter", "").strip()

        seconds = self._parse_duration(parameter)
        if seconds <= 0:
            return f"Invalid timer duration: '{parameter}'"

        label = intent.get("query", "").strip() or "Timer"
        human_duration = self._format_duration(seconds)

        def on_timer():
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            notifier = _TimerNotifier.instance()
            notifier.notify.emit(f"Timer finished: {human_duration} - {label}")

        timer = threading.Timer(seconds, on_timer)
        timer.daemon = True
        timer.start()

        print(f"[Timer] Set: {human_duration} - '{label}'")
        return f"Timer set: {human_duration}"

    @staticmethod
    def _parse_duration(text: str) -> int:
        if not text:
            return 0
        text = text.strip().lower()
        total = 0

        hours = re.findall(r"(\d+)\s*(?:h|or[ae]|hour)", text)
        minutes = re.findall(r"(\d+)\s*(?:m|min|minut[oi])", text)
        seconds = re.findall(r"(\d+)\s*(?:s|sec|second[oi])", text)

        for h in hours:
            total += int(h) * 3600
        for m in minutes:
            total += int(m) * 60
        for s in seconds:
            total += int(s)

        # Plain number = assume minutes
        if total == 0:
            try:
                total = int(text) * 60
            except ValueError:
                pass

        return total

    @staticmethod
    def _format_duration(seconds: int) -> str:
        if seconds >= 3600:
            h = seconds // 3600
            m = (seconds % 3600) // 60
            return f"{h}h {m}m" if m else f"{h}h"
        elif seconds >= 60:
            m = seconds // 60
            s = seconds % 60
            return f"{m}m {s}s" if s else f"{m}m"
        return f"{seconds}s"
