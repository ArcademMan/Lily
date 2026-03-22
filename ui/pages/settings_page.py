"""Settings page: general preferences (hotkey, audio, TTS, paths, dictation)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QCheckBox, QSlider,
    QPushButton, QScrollArea, QFileDialog,
)

from ui.widgets.glass_card import GlassCard


def _row(label_text: str, widget: QWidget) -> QHBoxLayout:
    row = QHBoxLayout()
    lbl = QLabel(label_text)
    lbl.setFixedWidth(160)
    row.addWidget(lbl)
    row.addWidget(widget)
    return row


def _slider_row(label_text: str, min_val: int, max_val: int, value: int,
                fmt=str) -> tuple[QHBoxLayout, QSlider, QLabel]:
    row = QHBoxLayout()
    lbl = QLabel(label_text)
    lbl.setFixedWidth(160)
    row.addWidget(lbl)
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(min_val, max_val)
    slider.setValue(value)
    row.addWidget(slider)
    val_label = QLabel(fmt(value))
    val_label.setFixedWidth(40)
    slider.valueChanged.connect(lambda v: val_label.setText(fmt(v)))
    row.addWidget(val_label)
    return row, slider, val_label


def _section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("color: #aaa; font-size: 12px; font-weight: 600;")
    return lbl


class SettingsPage(QWidget):
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

        # ── Card: Generale ────────────────────────────────────────
        form.addWidget(_section_title("Generale"))
        form.addSpacing(4)

        general_card = GlassCard()
        gc = general_card.body()
        gc.setSpacing(10)

        self._hotkey = QLineEdit(config.hotkey)
        gc.addLayout(_row("Hotkey", self._hotkey))

        self._overlay_enabled = QCheckBox("Lily Overlay (mostra icona quando minimizzata)")
        self._overlay_enabled.setChecked(config.overlay_enabled)
        gc.addWidget(self._overlay_enabled)

        form.addWidget(general_card)
        form.addSpacing(8)

        # ── Card: Audio ───────────────────────────────────────────
        form.addWidget(_section_title("Audio"))
        form.addSpacing(4)

        audio_card = GlassCard()
        ac = audio_card.body()
        ac.setSpacing(10)

        self._whisper = QComboBox()
        self._whisper.addItems(["tiny", "base", "small", "medium", "large-v3"])
        self._whisper.setCurrentText(config.whisper_model)
        ac.addLayout(_row("Modello Whisper", self._whisper))

        self._mic = QComboBox()
        self._mic.addItem("Default", None)
        self._populate_mics()
        ac.addLayout(_row("Microfono", self._mic))

        form.addWidget(audio_card)
        form.addSpacing(8)

        # ── Card: Percorsi ────────────────────────────────────────
        form.addWidget(_section_title("Percorsi"))
        form.addSpacing(4)

        paths_card = GlassCard()
        ptc = paths_card.body()
        ptc.setSpacing(10)

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
        ptc.addLayout(es_row)

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
        ptc.addLayout(tess_row)

        form.addWidget(paths_card)
        form.addSpacing(8)

        # ── Card: TTS ─────────────────────────────────────────────
        form.addWidget(_section_title("Text-to-Speech"))
        form.addSpacing(4)

        tts_card = GlassCard()
        tc = tts_card.body()
        tc.setSpacing(10)

        self._tts_enabled = QCheckBox("Abilita Text-to-Speech")
        self._tts_enabled.setChecked(config.tts_enabled)
        tc.addWidget(self._tts_enabled)

        self._tts_voice = QComboBox()
        from core.voice.tts import TTSEngine
        self._tts_voice.addItems(TTSEngine.available_voices())
        self._tts_voice.setCurrentText(config.tts_voice)
        tc.addLayout(_row("Voce TTS", self._tts_voice))

        form.addWidget(tts_card)
        form.addSpacing(8)

        # ── Card: Dettatura ───────────────────────────────────────
        form.addWidget(_section_title("Dettatura"))
        form.addSpacing(4)

        dict_card = GlassCard()
        dc = dict_card.body()
        dc.setSpacing(10)

        ds_row, self._dict_silence, self._ds_label = _slider_row(
            "Silenzio dettatura (s)", 10, 100,
            int(getattr(config, "dictation_silence_duration", 3.5) * 10),
            fmt=lambda v: f"{v / 10:.1f}")
        dc.addLayout(ds_row)

        dm_row, self._dict_max, self._dm_label = _slider_row(
            "Durata max dettatura (s)", 10, 120,
            int(getattr(config, "dictation_max_duration", 60)))
        dc.addLayout(dm_row)

        dt_row, self._dict_timeout, self._dt_label = _slider_row(
            "Timeout inattività (s)", 2, 30,
            int(getattr(config, "dictation_silence_timeout", 4)))
        dc.addLayout(dt_row)

        form.addWidget(dict_card)

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

    # ── helpers ───────────────────────────────────────────────────
    def _populate_mics(self):
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            for i, d in enumerate(devices):
                if d["max_input_channels"] > 0:
                    self._mic.addItem(d["name"], i)
            current = self._config.mic_device
            if current is not None:
                idx = self._mic.findData(current)
                if idx >= 0:
                    self._mic.setCurrentIndex(idx)
        except Exception:
            pass

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
        self._config.whisper_model = self._whisper.currentText()
        self._config.mic_device = self._mic.currentData()
        self._config.es_path = self._es_path.text().strip()
        self._config.tesseract_path = self._tesseract_path.text().strip()
        self._config.tts_enabled = self._tts_enabled.isChecked()
        self._config.tts_voice = self._tts_voice.currentText()
        self._config.overlay_enabled = self._overlay_enabled.isChecked()
        self._config.dictation_silence_duration = self._dict_silence.value() / 10.0
        self._config.dictation_max_duration = self._dict_max.value()
        self._config.dictation_silence_timeout = self._dict_timeout.value()
        self._config.save()

        self._assistant.apply_config()
        if self._config.hotkey != old_hotkey:
            self._assistant.update_hotkey()

        self._status.setText("Salvato!")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self._status.setText(""))
