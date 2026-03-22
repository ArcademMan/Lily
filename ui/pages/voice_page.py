"""Voice interaction page: state indicator + transcription + result."""

import subprocess
import threading

from PySide6.QtCore import Qt, QTimer, Signal as QtSignal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel

from ui.widgets.state_indicator import StateIndicator

_STATE_LABELS = {
    "loading": "Caricamento modello...",
    "idle": "Pronto",
    "listening": "Ascolto...",
    "processing": "Elaborazione...",
}


class VoicePage(QWidget):
    _gpu_info_ready = QtSignal(str)

    def __init__(self, bridge, config=None, parent=None):
        super().__init__(parent)
        self._bridge = bridge
        self._config = config

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

        # detail label (cosa sta facendo)
        self._detail_label = QLabel("")
        self._detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._detail_label.setStyleSheet("font-size: 11px; color: #7C5CFC;")
        layout.addWidget(self._detail_label)

        layout.addSpacing(16)

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

        # provider warning
        self._provider_warn = QLabel("")
        self._provider_warn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._provider_warn)
        self._update_provider_warning()

        # blink timer per il warning Anthropic
        self._blink_on = True
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink_warning)
        self._blink_timer.start(800)

        layout.addStretch(1)

        # GPU info bar
        gpu_bar = QHBoxLayout()
        gpu_bar.setContentsMargins(0, 0, 0, 0)
        self._gpu_label = QLabel("")
        self._gpu_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._gpu_label.setStyleSheet("font-size: 10px; color: #555555;")
        gpu_bar.addWidget(self._gpu_label)
        layout.addLayout(gpu_bar)

        # clear timer
        self._clear_timer = QTimer(self)
        self._clear_timer.setSingleShot(True)
        self._clear_timer.timeout.connect(self._clear_result)

        # GPU update timer
        self._gpu_timer = QTimer(self)
        self._gpu_timer.timeout.connect(self._fetch_gpu_info)
        self._gpu_timer.start(5000)
        self._gpu_info_ready.connect(self._gpu_label.setText)
        self._fetch_gpu_info()

        # signals
        bridge.state_changed.connect(self._on_state)
        bridge.result_ready.connect(self._on_result)
        bridge.notify.connect(self._on_notify)
        bridge.detail.connect(self._on_detail)

    def _on_state(self, state: str):
        self._indicator.set_state(state)
        self._state_label.setText(_STATE_LABELS.get(state, state))
        if state == "listening":
            self._transcription.setText("")
            self._result.setText("")
            self._detail_label.setText("")
            self._clear_timer.stop()

    def _on_detail(self, detail: str):
        self._detail_label.setText(detail)

    def _on_result(self, text: str, result: str):
        self._indicator.set_state("idle")
        self._state_label.setText("Pronto")
        self._detail_label.setText("")
        self._transcription.setText(f'"{text}"')
        self._result.setText(result)
        self._clear_timer.start(8000)

    def _on_notify(self, msg: str):
        self._result.setText(msg)
        self._clear_timer.start(5000)

    def _clear_result(self):
        self._transcription.setText("")
        self._result.setText("")

    def _update_provider_warning(self):
        if self._config and getattr(self._config, "provider", "ollama") == "anthropic":
            self._provider_warn.setText("Anthropic")
            self._provider_warn.setStyleSheet("font-size: 12px; font-weight: bold; color: #F44336;")
            self._blink_on = True
        else:
            self._provider_warn.setText("Tieni premuto il tasto hotkey per parlare")
            self._provider_warn.setStyleSheet("font-size: 12px; color: #555555;")

    def _blink_warning(self):
        if not self._config or getattr(self._config, "provider", "ollama") != "anthropic":
            self._update_provider_warning()
            return
        self._blink_on = not self._blink_on
        if self._blink_on:
            self._provider_warn.setStyleSheet("font-size: 12px; font-weight: bold; color: #F44336;")
        else:
            self._provider_warn.setStyleSheet("font-size: 12px; font-weight: bold; color: #661111;")

    def _fetch_gpu_info(self):
        """Aggiorna info GPU in background."""
        def _query():
            try:
                r = subprocess.run(
                    ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu,name",
                     "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=3,
                )
                parts = [p.strip() for p in r.stdout.strip().split(",")]
                if len(parts) >= 4:
                    used = int(parts[0])
                    total = int(parts[1])
                    util = int(parts[2])
                    name = parts[3]
                    free = total - used
                    self._gpu_info_ready.emit(
                        f"{name}  |  VRAM: {used}/{total} MB ({free} MB liberi)  |  GPU: {util}%"
                    )
                else:
                    self._gpu_info_ready.emit("")
            except Exception:
                self._gpu_info_ready.emit("")

        threading.Thread(target=_query, daemon=True).start()

    def showEvent(self, event):
        super().showEvent(event)
        self._gpu_timer.start(5000)

    def hideEvent(self, event):
        super().hideEvent(event)
        self._gpu_timer.stop()
