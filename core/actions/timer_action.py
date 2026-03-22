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
    _active_timers: dict[str, threading.Timer] = {}
    _lock = threading.Lock()

    def execute(self, intent: dict, config) -> str:
        parameter = intent.get("parameter", "").strip().lower()

        # Cancellazione timer
        if parameter in ("cancel", "cancella", "togli", "rimuovi", "stop"):
            return self._cancel_all()

        seconds = self._parse_duration(parameter)
        if seconds <= 0:
            return f"Durata timer non valida: '{parameter}'"

        label = intent.get("query", "").strip() or "Timer"
        human_duration = self._format_duration(seconds)

        def on_timer():
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            notifier = _TimerNotifier.instance()
            notifier.notify.emit(f"Timer scaduto: {human_duration} - {label}")
            with self._lock:
                self._active_timers.pop(timer_id, None)

        timer_id = f"{label}_{seconds}"
        timer = threading.Timer(seconds, on_timer)
        timer.daemon = True
        timer.start()

        with self._lock:
            # Cancella timer precedente con stesso id
            old = self._active_timers.pop(timer_id, None)
            if old:
                old.cancel()
            self._active_timers[timer_id] = timer

        print(f"[Timer] Impostato: {human_duration} - '{label}'")
        return f"Timer impostato: {human_duration}."

    def _cancel_all(self) -> str:
        with self._lock:
            count = len(self._active_timers)
            for t in self._active_timers.values():
                t.cancel()
            self._active_timers.clear()
        if count == 0:
            return "Nessun timer attivo."
        return f"Rimossi {count} timer." if count > 1 else "Timer rimosso."

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
