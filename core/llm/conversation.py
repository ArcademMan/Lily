"""Memoria di conversazione a breve termine per la modalità chat."""

import threading


class ConversationMemory:
    def __init__(self, max_exchanges: int = 5):
        self._history: list[dict] = []
        self._max_exchanges = max_exchanges
        self._lock = threading.Lock()

    @property
    def max_exchanges(self) -> int:
        return self._max_exchanges

    @max_exchanges.setter
    def max_exchanges(self, value: int):
        with self._lock:
            self._max_exchanges = value
            self._trim()

    def add_user(self, text: str):
        with self._lock:
            self._history.append({"role": "user", "content": text})
            self._trim()

    def add_assistant(self, text: str):
        with self._lock:
            self._history.append({"role": "assistant", "content": text})
            self._trim()

    def get_messages(self) -> list[dict]:
        with self._lock:
            return list(self._history)

    def clear(self):
        with self._lock:
            self._history.clear()

    def _trim(self):
        max_msgs = self._max_exchanges * 2
        if len(self._history) > max_msgs:
            self._history = self._history[-max_msgs:]
