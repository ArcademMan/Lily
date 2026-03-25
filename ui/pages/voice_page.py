"""Voice interaction page: state indicator + transcription + result."""

import subprocess
import threading

import qtawesome as qta
from PySide6.QtCore import Qt, QTimer, Signal as QtSignal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

from core.i18n import t
from ui.widgets.state_indicator import StateIndicator


def _state_label(state: str) -> str:
    return {
        "loading": t("state_loading"),
        "idle": t("state_idle"),
        "listening": t("state_listening"),
        "processing": t("state_processing"),
        "transcribing": t("state_transcribing"),
    }.get(state, state)


class VoicePage(QWidget):
    _gpu_info_ready = QtSignal(str)
    _services_ready = QtSignal(dict)

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
        self._state_label = QLabel(t("state_loading"))
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

        # model info label (provider — model)
        self._model_label = QLabel("")
        self._model_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._model_label)
        self._update_model_label()

        # soft blink timer
        self._blink_on = True
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink_model)
        self._blink_timer.start(1500)

        layout.addStretch(1)

        # ── Status footer (no card) ──
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 8, 0, 8)
        footer.setSpacing(12)
        footer.addStretch()

        self._status_ollama = QLabel("Ollama: ...")
        self._status_ollama.setStyleSheet("font-size: 11px; color: #888;")
        footer.addWidget(self._status_ollama)

        sep1 = QLabel("|")
        sep1.setStyleSheet("font-size: 11px; color: #333;")
        footer.addWidget(sep1)

        self._status_everything = QLabel("Everything: ...")
        self._status_everything.setStyleSheet("font-size: 11px; color: #888;")
        footer.addWidget(self._status_everything)

        sep2 = QLabel("|")
        sep2.setStyleSheet("font-size: 11px; color: #333;")
        footer.addWidget(sep2)

        self._status_tesseract = QLabel("Tesseract: ...")
        self._status_tesseract.setStyleSheet("font-size: 11px; color: #888;")
        footer.addWidget(self._status_tesseract)

        # info button — opens welcome wizard
        info_btn = QPushButton()
        info_btn.setIcon(qta.icon("mdi6.information-outline", color="#666"))
        info_btn.setFixedSize(24, 24)
        info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        info_btn.setToolTip("Dipendenze e download")
        info_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; border-radius: 12px; padding: 0; }"
            "QPushButton:hover { background: rgba(255,255,255,10); }"
        )
        info_btn.clicked.connect(self._show_deps_info)
        footer.addWidget(info_btn)

        footer.addStretch()
        layout.addLayout(footer)

        # GPU info
        self._gpu_label = QLabel("")
        self._gpu_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._gpu_label.setStyleSheet("font-size: 10px; color: #555555;")
        layout.addWidget(self._gpu_label)

        # clear timer
        self._clear_timer = QTimer(self)
        self._clear_timer.setSingleShot(True)
        self._clear_timer.timeout.connect(self._clear_result)

        # GPU update timer
        self._gpu_timer = QTimer(self)
        self._gpu_timer.timeout.connect(self._fetch_gpu_info)
        self._gpu_timer.start(30000)
        self._gpu_info_ready.connect(self._gpu_label.setText)
        self._fetch_gpu_info()

        # services check
        self._services_ready.connect(self._update_services)
        self._services_timer = QTimer(self)
        self._services_timer.timeout.connect(self._check_services)
        self._services_timer.start(10000)
        self._check_services()

        # signals
        bridge.state_changed.connect(self._on_state)
        bridge.result_ready.connect(self._on_result)
        bridge.notify.connect(self._on_notify)
        bridge.detail.connect(self._on_detail)

    def _on_state(self, state: str):
        self._indicator.set_state(state)
        self._state_label.setText(_state_label(state))
        if state == "listening":
            self._transcription.setText("")
            self._result.setText("")
            self._detail_label.setText("")
            self._clear_timer.stop()

    def _on_detail(self, detail: str):
        self._detail_label.setText(detail)

    def _on_result(self, text: str, result: str):
        self._indicator.set_state("idle")
        self._state_label.setText(t("state_idle"))
        self._detail_label.setText("")
        self._transcription.setText(f'"{text}"')
        self._result.setText(result)
        self._clear_timer.stop()

    def _on_notify(self, msg: str):
        self._result.setText(msg)
        self._clear_timer.start(5000)

    def _clear_result(self):
        self._transcription.setText("")
        self._result.setText("")

    def _get_model_text(self) -> str:
        if not self._config:
            return ""
        provider = getattr(self._config, "provider", "ollama")
        model = getattr(self._config, f"{provider}_model", "")
        return f"{provider.capitalize()} — {model}" if model else provider.capitalize()

    def _update_model_label(self):
        self._model_label.setText(self._get_model_text())
        self._model_label.setStyleSheet("font-size: 11px; color: #555;")

    def _blink_model(self):
        self._model_label.setText(self._get_model_text())
        self._blink_on = not self._blink_on
        color = "#666" if self._blink_on else "#3a3a3a"
        self._model_label.setStyleSheet(f"font-size: 11px; color: {color};")

    def _fetch_gpu_info(self):
        """Aggiorna info GPU in background."""
        def _query():
            try:
                r = subprocess.run(
                    ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu,name",
                     "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=3,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                parts = [p.strip() for p in r.stdout.strip().split(",")]
                if len(parts) >= 4:
                    used = int(parts[0])
                    total = int(parts[1])
                    util = int(parts[2])
                    name = parts[3]
                    free = total - used
                    self._gpu_info_ready.emit(
                        t("gpu_info", name=name, used=used, total=total, free=free, util=util)
                    )
                else:
                    self._gpu_info_ready.emit("")
            except Exception:
                self._gpu_info_ready.emit("")

        threading.Thread(target=_query, daemon=True).start()

    def _check_services(self):
        def _check():
            status = {}
            try:
                from core.llm.ollama_provider import OllamaProvider
                status["ollama"] = OllamaProvider().check()
            except Exception:
                status["ollama"] = False
            try:
                from core.search import check_everything
                es_path = self._config.es_path if self._config else "es.exe"
                status["everything"] = check_everything(es_path)
            except Exception:
                status["everything"] = False
            try:
                tess = self._config.tesseract_path if self._config else "tesseract"
                r = subprocess.run([tess, "--version"],
                                   capture_output=True, text=True, timeout=3,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                status["tesseract"] = r.returncode == 0
            except Exception:
                status["tesseract"] = False
            self._services_ready.emit(status)

        threading.Thread(target=_check, daemon=True).start()

    def _update_services(self, status: dict):
        def _fmt(name, ok):
            dot_color = "#4CAF50" if ok else "#F44336"
            return f'<span style="color:{dot_color};">●</span> <span style="color:#888;">{name}</span>'

        self._status_ollama.setText(_fmt("Ollama", status.get("ollama", False)))
        self._status_everything.setText(_fmt("Everything", status.get("everything", False)))
        self._status_tesseract.setText(_fmt("Tesseract", status.get("tesseract", False)))

    def _show_deps_info(self):
        from ui.welcome import WelcomeWizard
        dlg = WelcomeWizard(self.window())
        dlg.exec()

    def showEvent(self, event):
        super().showEvent(event)
        self._gpu_timer.start(30000)
        self._services_timer.start(10000)
        self._check_services()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._gpu_timer.stop()
        self._services_timer.stop()
