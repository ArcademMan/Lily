"""Settings page: form for all Config fields."""

import threading

from PySide6.QtCore import Qt, Signal as QtSignal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QCheckBox, QSlider,
    QPushButton, QScrollArea, QFileDialog, QSizePolicy,
)

from ui.widgets.glass_card import GlassCard


def _row(label_text: str, widget: QWidget) -> QHBoxLayout:
    row = QHBoxLayout()
    lbl = QLabel(label_text)
    lbl.setFixedWidth(160)
    row.addWidget(lbl)
    row.addWidget(widget)
    return row


class SettingsPage(QWidget):
    _ollama_models_ready = QtSignal(list)
    _ollama_status_ready = QtSignal(bool)

    def __init__(self, config, assistant, parent=None):
        super().__init__(parent)
        self._config = config
        self._assistant = assistant

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)

        title = QLabel("Impostazioni")
        title.setObjectName("sectionTitle")
        outer.addWidget(title)
        outer.addSpacing(12)

        # scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        form = QVBoxLayout(container)
        form.setSpacing(14)
        scroll.setWidget(container)
        outer.addWidget(scroll)

        # ── fields ────────────────────────────────────────────────
        self._hotkey = QLineEdit(config.hotkey)
        form.addLayout(_row("Hotkey", self._hotkey))

        self._provider = QComboBox()
        self._provider.addItems(["ollama", "anthropic"])
        self._provider.setCurrentText(config.provider)
        self._provider.currentTextChanged.connect(self._on_provider_changed)
        form.addLayout(_row("Provider LLM", self._provider))

        # ollama fields
        self._ollama_model = QComboBox()
        self._ollama_model.setEditable(True)
        self._ollama_model.setCurrentText(config.ollama_model)
        self._ollama_row = _row("Modello Ollama", self._ollama_model)
        form.addLayout(self._ollama_row)
        self._fetch_ollama_models()

        # ollama status
        self._ollama_status = QLabel("")
        self._ollama_status.setFixedHeight(20)
        self._ollama_status_row = _row("Stato Ollama", self._ollama_status)
        form.addLayout(self._ollama_status_row)
        self._check_ollama_status()

        # anthropic fields
        self._api_key = QLineEdit(config.anthropic_api_key)
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_row = _row("API Key Anthropic", self._api_key)
        form.addLayout(self._api_key_row)

        self._anthropic_model = QComboBox()
        self._anthropic_model.addItems([
            "claude-haiku-4-5-20251001",
            "claude-sonnet-4-6-20250514",
        ])
        self._anthropic_model.setCurrentText(config.anthropic_model)
        self._anthropic_model_row = _row("Modello Anthropic", self._anthropic_model)
        form.addLayout(self._anthropic_model_row)

        # whisper
        self._whisper = QComboBox()
        self._whisper.addItems(["tiny", "base", "small", "medium", "large-v3"])
        self._whisper.setCurrentText(config.whisper_model)
        form.addLayout(_row("Modello Whisper", self._whisper))

        # mic
        self._mic = QComboBox()
        self._mic.addItem("Default", None)
        self._populate_mics()
        form.addLayout(_row("Microfono", self._mic))

        # es path
        es_row = QHBoxLayout()
        lbl = QLabel("ES Path")
        lbl.setFixedWidth(160)
        es_row.addWidget(lbl)
        self._es_path = QLineEdit(config.es_path)
        es_row.addWidget(self._es_path)
        browse = QPushButton("...")
        browse.setFixedWidth(36)
        browse.clicked.connect(self._browse_es)
        es_row.addWidget(browse)
        form.addLayout(es_row)

        # ── TTS ──────────────────────────────────────────────────
        self._tts_enabled = QCheckBox("Abilita Text-to-Speech")
        self._tts_enabled.setChecked(config.tts_enabled)
        form.addWidget(self._tts_enabled)

        self._tts_voice = QComboBox()
        from core.voice.tts import TTSEngine
        self._tts_voice.addItems(TTSEngine.available_voices())
        self._tts_voice.setCurrentText(config.tts_voice)
        form.addLayout(_row("Voce TTS", self._tts_voice))

        # ── Tesseract ───────────────────────────────────────────
        tess_row = QHBoxLayout()
        lbl = QLabel("Tesseract Path")
        lbl.setFixedWidth(160)
        tess_row.addWidget(lbl)
        self._tesseract_path = QLineEdit(getattr(config, "tesseract_path", "tesseract"))
        tess_row.addWidget(self._tesseract_path)
        tess_browse = QPushButton("...")
        tess_browse.setFixedWidth(36)
        tess_browse.clicked.connect(self._browse_tesseract)
        tess_row.addWidget(tess_browse)
        form.addLayout(tess_row)

        # ── LLM ────────────────────────────────────────────────
        # thinking
        self._thinking = QCheckBox("Abilita ragionamento esteso")
        self._thinking.setChecked(config.thinking_enabled)
        form.addWidget(self._thinking)

        # num_predict
        slider_row = QHBoxLayout()
        lbl = QLabel("Num Predict")
        lbl.setFixedWidth(160)
        slider_row.addWidget(lbl)
        self._num_predict = QSlider(Qt.Orientation.Horizontal)
        self._num_predict.setRange(32, 512)
        self._num_predict.setValue(config.num_predict)
        slider_row.addWidget(self._num_predict)
        self._np_label = QLabel(str(config.num_predict))
        self._np_label.setFixedWidth(40)
        self._num_predict.valueChanged.connect(lambda v: self._np_label.setText(str(v)))
        slider_row.addWidget(self._np_label)
        form.addLayout(slider_row)

        # chat num_predict
        chat_slider_row = QHBoxLayout()
        lbl = QLabel("Chat Num Predict")
        lbl.setFixedWidth(160)
        chat_slider_row.addWidget(lbl)
        self._chat_num_predict = QSlider(Qt.Orientation.Horizontal)
        self._chat_num_predict.setRange(64, 1024)
        self._chat_num_predict.setValue(getattr(config, "chat_num_predict", 384))
        chat_slider_row.addWidget(self._chat_num_predict)
        self._cnp_label = QLabel(str(getattr(config, "chat_num_predict", 384)))
        self._cnp_label.setFixedWidth(40)
        self._chat_num_predict.valueChanged.connect(lambda v: self._cnp_label.setText(str(v)))
        chat_slider_row.addWidget(self._cnp_label)
        form.addLayout(chat_slider_row)

        # chat max history
        hist_row = QHBoxLayout()
        lbl = QLabel("Storico chat")
        lbl.setFixedWidth(160)
        hist_row.addWidget(lbl)
        self._chat_max_history = QSlider(Qt.Orientation.Horizontal)
        self._chat_max_history.setRange(1, 20)
        self._chat_max_history.setValue(getattr(config, "chat_max_history", 5))
        hist_row.addWidget(self._chat_max_history)
        self._hist_label = QLabel(str(getattr(config, "chat_max_history", 5)))
        self._hist_label.setFixedWidth(40)
        self._chat_max_history.valueChanged.connect(lambda v: self._hist_label.setText(str(v)))
        hist_row.addWidget(self._hist_label)
        form.addLayout(hist_row)

        # ── Dettatura ──────────────────────────────────────────
        dict_silence_row = QHBoxLayout()
        lbl = QLabel("Silenzio dettatura (s)")
        lbl.setFixedWidth(160)
        dict_silence_row.addWidget(lbl)
        self._dict_silence = QSlider(Qt.Orientation.Horizontal)
        self._dict_silence.setRange(10, 100)  # 1.0 - 10.0 (x10)
        self._dict_silence.setValue(int(getattr(config, "dictation_silence_duration", 3.5) * 10))
        dict_silence_row.addWidget(self._dict_silence)
        self._ds_label = QLabel(f"{getattr(config, 'dictation_silence_duration', 3.5):.1f}")
        self._ds_label.setFixedWidth(40)
        self._dict_silence.valueChanged.connect(lambda v: self._ds_label.setText(f"{v / 10:.1f}"))
        dict_silence_row.addWidget(self._ds_label)
        form.addLayout(dict_silence_row)

        dict_max_row = QHBoxLayout()
        lbl = QLabel("Durata max dettatura (s)")
        lbl.setFixedWidth(160)
        dict_max_row.addWidget(lbl)
        self._dict_max = QSlider(Qt.Orientation.Horizontal)
        self._dict_max.setRange(10, 120)
        self._dict_max.setValue(int(getattr(config, "dictation_max_duration", 60)))
        dict_max_row.addWidget(self._dict_max)
        self._dm_label = QLabel(str(int(getattr(config, "dictation_max_duration", 60))))
        self._dm_label.setFixedWidth(40)
        self._dict_max.valueChanged.connect(lambda v: self._dm_label.setText(str(v)))
        dict_max_row.addWidget(self._dm_label)
        form.addLayout(dict_max_row)

        dict_timeout_row = QHBoxLayout()
        lbl = QLabel("Timeout inattività (s)")
        lbl.setFixedWidth(160)
        dict_timeout_row.addWidget(lbl)
        self._dict_timeout = QSlider(Qt.Orientation.Horizontal)
        self._dict_timeout.setRange(2, 30)
        self._dict_timeout.setValue(int(getattr(config, "dictation_silence_timeout", 4)))
        dict_timeout_row.addWidget(self._dict_timeout)
        self._dt_label = QLabel(str(int(getattr(config, "dictation_silence_timeout", 4))))
        self._dt_label.setFixedWidth(40)
        self._dict_timeout.valueChanged.connect(lambda v: self._dt_label.setText(str(v)))
        dict_timeout_row.addWidget(self._dt_label)
        form.addLayout(dict_timeout_row)

        form.addStretch()

        # ── save / status ─────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._status = QLabel("")
        self._status.setStyleSheet("color: #4CAF50; font-size: 12px;")
        btn_row.addWidget(self._status)
        save_btn = QPushButton("Salva")
        save_btn.setFixedWidth(120)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        outer.addSpacing(8)
        outer.addLayout(btn_row)

        self._on_provider_changed(config.provider)

    # ── helpers ───────────────────────────────────────────────────
    def _populate_mics(self):
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            for i, d in enumerate(devices):
                if d["max_input_channels"] > 0:
                    self._mic.addItem(d["name"], i)
            # select current
            current = self._config.mic_device
            if current is not None:
                idx = self._mic.findData(current)
                if idx >= 0:
                    self._mic.setCurrentIndex(idx)
        except Exception:
            pass

    def _check_ollama_status(self):
        """Verifica se Ollama è raggiungibile in background."""
        self._ollama_status_ready.connect(self._update_ollama_status)

        def _check():
            try:
                from core.llm.ollama_provider import OllamaProvider
                ok = OllamaProvider().check()
            except Exception:
                ok = False
            self._ollama_status_ready.emit(ok)

        threading.Thread(target=_check, daemon=True).start()

    def _update_ollama_status(self, connected: bool):
        if connected:
            self._ollama_status.setText("Connesso")
            self._ollama_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self._ollama_status.setText("Non connesso")
            self._ollama_status.setStyleSheet("color: #F44336; font-weight: bold;")

    def _fetch_ollama_models(self):
        """Fetch available Ollama models in a background thread."""
        self._ollama_models_ready.connect(self._populate_ollama_models)

        def _fetch():
            try:
                from core.llm.ollama_provider import OllamaProvider
                models = OllamaProvider().get_models()
            except Exception:
                models = []
            self._ollama_models_ready.emit(models)

        threading.Thread(target=_fetch, daemon=True).start()

    def _populate_ollama_models(self, models: list):
        current = self._ollama_model.currentText()
        self._ollama_model.blockSignals(True)
        self._ollama_model.clear()
        for m in models:
            self._ollama_model.addItem(m)
        self._ollama_model.setCurrentText(current)
        self._ollama_model.blockSignals(False)

    def _on_provider_changed(self, provider: str):
        is_ollama = provider == "ollama"
        self._set_row_visible(self._ollama_row, is_ollama)
        self._set_row_visible(self._ollama_status_row, is_ollama)
        self._set_row_visible(self._api_key_row, not is_ollama)
        self._set_row_visible(self._anthropic_model_row, not is_ollama)

    @staticmethod
    def _set_row_visible(layout: QHBoxLayout, visible: bool):
        for i in range(layout.count()):
            w = layout.itemAt(i).widget()
            if w:
                w.setVisible(visible)

    def _browse_es(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleziona es.exe", "", "Eseguibili (*.exe)")
        if path:
            self._es_path.setText(path)

    def _browse_tesseract(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleziona tesseract.exe", "", "Eseguibili (*.exe)")
        if path:
            self._tesseract_path.setText(path)

    def _save(self):
        old_hotkey = self._config.hotkey

        self._config.hotkey = self._hotkey.text().strip()
        self._config.provider = self._provider.currentText()
        self._config.ollama_model = self._ollama_model.currentText().strip()
        self._config.anthropic_api_key = self._api_key.text().strip()
        self._config.anthropic_model = self._anthropic_model.currentText()
        self._config.whisper_model = self._whisper.currentText()
        self._config.mic_device = self._mic.currentData()
        self._config.es_path = self._es_path.text().strip()
        self._config.tesseract_path = self._tesseract_path.text().strip()
        self._config.thinking_enabled = self._thinking.isChecked()
        self._config.num_predict = self._num_predict.value()
        self._config.chat_num_predict = self._chat_num_predict.value()
        self._config.chat_max_history = self._chat_max_history.value()
        self._config.tts_enabled = self._tts_enabled.isChecked()
        self._config.tts_voice = self._tts_voice.currentText()
        self._config.dictation_silence_duration = self._dict_silence.value() / 10.0
        self._config.dictation_max_duration = self._dict_max.value()
        self._config.dictation_silence_timeout = self._dict_timeout.value()
        self._config.save()

        # Aggiorna TTS engine live
        self._assistant.tts.enabled = self._config.tts_enabled
        self._assistant.tts.voice = self._config.tts_voice

        # Aggiorna memoria conversazionale
        self._assistant._memory.max_exchanges = self._config.chat_max_history

        if self._config.hotkey != old_hotkey:
            self._assistant.update_hotkey()

        self._status.setText("Salvato!")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self._status.setText(""))
