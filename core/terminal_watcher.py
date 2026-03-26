"""Monitoring passivo del terminale: rileva quando Claude Code (o altri processi)
chiedono conferma, finiscono un'operazione, o producono errori."""

import re
import threading
import time

from core.signal import Signal
from core import terminal_buffer

# ── Pattern di rilevamento ───────────────────────────────────────────────────

# Processo chiede conferma
_CONFIRM_PATTERNS = [
    r"(?i)\ballow\b",
    r"(?i)do\s*you\s*want\s*to",
    r"\(y/n\)",
    r"\(Y/n\)",
    r"\(yes/no\)",
    r"(?i)approve\s*this",
    r"(?i)permission\s*to",
    r"(?i)would\s*you\s*like\s*to",
    r"(?i)proceed.*\?",
    r"(?i)Doyouwant",  # Claude Code TUI (spazi strippati)
    r"(?i)Esctocancel",  # Claude Code TUI footer
]

# Processo ha finito (parola chiave concordata)
_DONE_PATTERNS = [
    r"(?i)LILY_DONE",
    r"(?i)lily_done",
    r"(?i)\bLILY.DONE\b",
]

# Errori
_ERROR_PATTERNS = [
    r"(?i)\berror\b.*\bfailed\b",
    r"(?i)\bfatal\b",
    r"(?i)\bpanic\b",
    r"(?i)traceback \(most recent",
    r"(?i)exception:",
]


class _TabState:
    """Stato di monitoring per un singolo tab."""
    __slots__ = ("last_seen",)

    def __init__(self, line_count: int):
        self.last_seen = line_count


class TerminalWatcher:
    """Monitora tab del terminale per conferme, errori e completamenti."""

    on_confirm = Signal()   # (tab_label: str, line: str)
    on_done = Signal()      # (tab_label: str)
    on_error = Signal()     # (tab_label: str, line: str)
    on_state_changed = Signal()  # (tab_id: str, watching: bool)

    _instance = None
    _cls_lock = threading.Lock()

    @classmethod
    def instance(cls):
        with cls._cls_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self._tabs: dict[str, _TabState] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._poll_interval = 2.0
        self._cooldown: dict[str, float] = {}
        self._cooldown_seconds = 15.0

    def watch(self, tab_id: str):
        """Inizia a monitorare un tab."""
        initial_total = terminal_buffer.get_total_lines(tab_id)
        self._tabs[tab_id] = _TabState(initial_total)
        if not self._thread or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._thread.start()
        self.on_state_changed.emit(tab_id, True)

    def unwatch(self, tab_id: str):
        """Smetti di monitorare un tab."""
        self._tabs.pop(tab_id, None)
        if not self._tabs:
            self._stop.set()
        self.on_state_changed.emit(tab_id, False)

    def unwatch_all(self):
        self._tabs.clear()
        self._stop.set()

    def is_watching(self, tab_id: str = None) -> bool:
        if tab_id:
            return tab_id in self._tabs
        return bool(self._tabs)

    def _poll_loop(self):
        while not self._stop.is_set():
            for tab_id in list(self._tabs.keys()):
                self._check_tab(tab_id)
            self._stop.wait(self._poll_interval)

    def _check_tab(self, tab_id: str):
        state = self._tabs.get(tab_id)
        if not state:
            return

        # Flusha chunk parziali rimasti (prompt senza newline)
        terminal_buffer.flush_pending(tab_id)

        total = terminal_buffer.get_total_lines(tab_id)
        if total <= state.last_seen:
            return

        new_count = total - state.last_seen

        text = terminal_buffer.get_text(tab_id=tab_id, max_lines=new_count)
        new_lines = text.splitlines()
        state.last_seen = total

        if not new_lines:
            return

        tab_label = terminal_buffer.get_label(tab_id)

        for line in new_lines:
            stripped = line.strip()
            if not stripped:
                continue

            if self._match_any(stripped, _CONFIRM_PATTERNS):
                if self._can_trigger("confirm", tab_id):
                    self.on_confirm.emit(tab_label, stripped)
                return

            if self._match_any(stripped, _DONE_PATTERNS):
                if self._can_trigger("done", tab_id):
                    self.on_done.emit(tab_label)
                return

            if self._match_any(stripped, _ERROR_PATTERNS):
                if self._can_trigger("error", tab_id):
                    self.on_error.emit(tab_label, stripped)
                return

    def _can_trigger(self, event_type: str, tab_id: str) -> bool:
        key = f"{event_type}:{tab_id}"
        now = time.time()
        last = self._cooldown.get(key, 0)
        if now - last < self._cooldown_seconds:
            return False
        self._cooldown[key] = now
        return True

    @staticmethod
    def _match_any(line: str, patterns: list[str]) -> bool:
        return any(re.search(p, line) for p in patterns)
