"""Voice interaction page: state indicator + transcription + result."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from ui.widgets.state_indicator import StateIndicator

_STATE_LABELS = {
    "loading": "Caricamento modello...",
    "idle": "Pronto",
    "listening": "Ascolto...",
    "processing": "Elaborazione...",
}


class VoicePage(QWidget):
    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self._bridge = bridge

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        layout.addStretch(2)

        # state indicator
        self._indicator = StateIndicator()
        layout.addWidget(self._indicator, alignment=Qt.AlignmentFlag.AlignCenter)

        # state label
        self._state_label = QLabel("Caricamento modello...")
        self._state_label.setObjectName("sectionTitle")
        self._state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._state_label)

        layout.addSpacing(20)

        # transcription
        self._transcription = QLabel("")
        self._transcription.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._transcription.setWordWrap(True)
        self._transcription.setStyleSheet("font-size: 15px; color: #EAEAEA;")
        layout.addWidget(self._transcription)

        # result
        self._result = QLabel("")
        self._result.setObjectName("secondary")
        self._result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result.setWordWrap(True)
        self._result.setStyleSheet("font-size: 13px; color: #888888;")
        layout.addWidget(self._result)

        layout.addStretch(1)

        # hotkey hint
        self._hint = QLabel("Tieni premuto il tasto hotkey per parlare")
        self._hint.setObjectName("secondary")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._hint)

        layout.addStretch(1)

        # clear timer
        self._clear_timer = QTimer(self)
        self._clear_timer.setSingleShot(True)
        self._clear_timer.timeout.connect(self._clear_result)

        # signals
        bridge.state_changed.connect(self._on_state)
        bridge.result_ready.connect(self._on_result)
        bridge.notify.connect(self._on_notify)

    def _on_state(self, state: str):
        self._indicator.set_state(state)
        self._state_label.setText(_STATE_LABELS.get(state, state))
        if state == "listening":
            self._transcription.setText("")
            self._result.setText("")
            self._clear_timer.stop()

    def _on_result(self, text: str, result: str):
        self._indicator.set_state("idle")
        self._state_label.setText("Pronto")
        self._transcription.setText(f'"{text}"')
        self._result.setText(result)
        self._clear_timer.start(8000)

    def _on_notify(self, msg: str):
        self._result.setText(msg)
        self._clear_timer.start(5000)

    def _clear_result(self):
        self._transcription.setText("")
        self._result.setText("")
