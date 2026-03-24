import re
import threading
import winsound

from core.signal import Signal
from core.actions.base import Action
from core.i18n import t


class _TimerNotifier:
    """Emits signal when timer fires. Connected to TTS by Assistant."""
    notify = Signal()      # (message: str)
    speak = Signal()       # (message: str) — triggers TTS

    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


class TimerAction(Action):
    TOOL_SCHEMA = {
        "name": "timer",
        "description": "Imposta un timer, promemoria o timer ricorrente. Cancella o elenca timer attivi",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Messaggio del promemoria (opzionale)"},
                "parameter": {"type": "string", "description": "Durata (5m, 1h, 30s), 'cancel', 'lista', o 'recurring DURATA'"}
            },
            "required": ["parameter"]
        }
    }

    _active_timers: dict[str, threading.Timer] = {}
    _recurring_timers: dict[str, dict] = {}  # id -> {seconds, label, timer}
    _lock = threading.Lock()

    def execute(self, intent: dict, config, **kwargs) -> str:
        parameter = intent.get("parameter", "").strip().lower()

        # Cancellazione timer
        if parameter in ("cancel", "cancella", "togli", "rimuovi", "stop"):
            return self._cancel_all()

        # Lista timer attivi
        if parameter in ("lista", "list", "attivi", "quanti"):
            return self._list_timers()

        # Controlla se è ricorrente ("ogni X")
        recurring = "recurring" in parameter
        clean_param = parameter.replace("recurring", "").strip()

        seconds = self._parse_duration(clean_param)
        if seconds <= 0:
            return t("timer_invalid_duration", parameter=parameter)

        label = intent.get("query", "").strip() or "Timer"
        human_duration = self._format_duration(seconds)
        is_reminder = label != "Timer"

        if recurring:
            return self._start_recurring(seconds, label, human_duration, is_reminder)
        else:
            return self._start_single(seconds, label, human_duration, is_reminder)

    def _start_single(self, seconds: int, label: str, human_duration: str,
                      is_reminder: bool) -> str:
        timer_id = f"{label}_{seconds}"

        def on_timer():
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            notifier = _TimerNotifier.instance()
            if is_reminder:
                msg = t("timer_reminder_fire", label=label)
                notifier.speak.emit(msg)
            else:
                msg = t("timer_fire", duration=human_duration)
                notifier.speak.emit(msg)
            notifier.notify.emit(msg)
            with self._lock:
                self._active_timers.pop(timer_id, None)

        timer = threading.Timer(seconds, on_timer)
        timer.daemon = True
        timer.start()

        with self._lock:
            old = self._active_timers.pop(timer_id, None)
            if old:
                old.cancel()
            self._active_timers[timer_id] = timer

        if is_reminder:
            print(f"[Timer] Promemoria impostato: {human_duration} - '{label}'")
            return t("timer_reminder_set", duration=human_duration, label=label)
        else:
            print(f"[Timer] Impostato: {human_duration}")
            return t("timer_set", duration=human_duration)

    def _start_recurring(self, seconds: int, label: str, human_duration: str,
                         is_reminder: bool) -> str:
        timer_id = f"rec_{label}_{seconds}"

        cancel_event = threading.Event()

        def on_tick():
            if cancel_event.is_set():
                return
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            notifier = _TimerNotifier.instance()
            msg = t("timer_recurring_reminder_fire", label=label) if is_reminder else t("timer_recurring_fire", duration=human_duration)
            notifier.speak.emit(msg)
            notifier.notify.emit(msg)
            # Rilancia il prossimo tick solo se non cancellato
            if not cancel_event.is_set():
                next_timer = threading.Timer(seconds, on_tick)
                next_timer.daemon = True
                next_timer.start()
                with self._lock:
                    if timer_id in self._recurring_timers:
                        self._recurring_timers[timer_id]["timer"] = next_timer

        timer = threading.Timer(seconds, on_tick)
        timer.daemon = True
        timer.start()

        with self._lock:
            # Cancella eventuale ricorrente precedente
            old = self._recurring_timers.pop(timer_id, None)
            if old:
                if old.get("cancel"):
                    old["cancel"].set()
                if old.get("timer"):
                    old["timer"].cancel()
            self._recurring_timers[timer_id] = {
                "seconds": seconds, "label": label, "timer": timer,
                "cancel": cancel_event,
            }

        print(f"[Timer] Ricorrente: ogni {human_duration} - '{label}'")
        return t("timer_recurring_set", duration=human_duration, label=label)

    def _cancel_all(self) -> str:
        with self._lock:
            count = len(self._active_timers) + len(self._recurring_timers)
            for t in self._active_timers.values():
                t.cancel()
            self._active_timers.clear()
            for info in self._recurring_timers.values():
                if info.get("cancel"):
                    info["cancel"].set()
                if info.get("timer"):
                    info["timer"].cancel()
            self._recurring_timers.clear()
        if count == 0:
            return t("timer_none_active")
        return t("timer_removed_many", count=count) if count > 1 else t("timer_removed_one")

    def _list_timers(self) -> str:
        with self._lock:
            single = len(self._active_timers)
            recurring = len(self._recurring_timers)
        total = single + recurring
        if total == 0:
            return t("timer_none_active")
        parts = []
        if single:
            parts.append(t("timer_count_single", count=single))
        if recurring:
            parts.append(t("timer_count_recurring", count=recurring))
        return t("timer_active_list", parts=" e ".join(parts))

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
