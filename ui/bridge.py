"""Bridge between core.signal.Signal (thread-unsafe for Qt) and PySide6 Signals."""

from PySide6.QtCore import QObject, Signal as QtSignal


class SignalBridge(QObject):
    """Receives emissions from core Signals on any thread and re-emits
    them as Qt Signals, which are safely delivered on the receiver's thread."""

    state_changed = QtSignal(str)
    result_ready = QtSignal(str, str)
    notify = QtSignal(str)
    detail = QtSignal(str)
    log_line = QtSignal(str)

    def __init__(self, assistant, parent=None):
        super().__init__(parent)
        assistant.state_changed.connect(lambda s: self.state_changed.emit(s))
        assistant.result_ready.connect(lambda t, r: self.result_ready.emit(t, r))
        assistant.notify.connect(lambda m: self.notify.emit(m))
        assistant.detail.connect(lambda d: self.detail.emit(d))
