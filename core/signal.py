"""Lightweight thread-safe signal system to replace PySide6 Signal/QObject."""

import threading


class Signal:
    """Simple callback-based signal, thread-safe."""

    def __init__(self):
        self._callbacks: list = []
        self._lock = threading.Lock()

    def connect(self, callback):
        with self._lock:
            self._callbacks.append(callback)

    def disconnect(self, callback=None):
        with self._lock:
            if callback:
                self._callbacks.remove(callback)
            else:
                self._callbacks.clear()

    def emit(self, *args):
        with self._lock:
            callbacks = list(self._callbacks)
        for cb in callbacks:
            cb(*args)
