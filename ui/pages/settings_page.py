"""Settings page: general preferences (hotkey, audio, TTS, paths, dictation)."""

import sys
import os

from PySide6.QtCore import Qt, Signal as QtSignal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QCheckBox, QSlider,
    QPushButton, QScrollArea, QFileDialog, QMessageBox,
)

import qtawesome as qta

from core.i18n import t
from ui.widgets.ai_hint import AiHint
from ui.widgets.glass_card import GlassCard


def _row(label_text: str, widget: QWidget, hint: str = "") -> QHBoxLayout:
    row = QHBoxLayout()
    lbl = QLabel(label_text)
    lbl.setFixedWidth(160)
    row.addWidget(lbl)
    row.addWidget(widget)
    if hint:
        row.addWidget(AiHint(hint))
    return row


def _check_row(checkbox: QCheckBox, hint: str = "") -> QHBoxLayout:
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(checkbox)
    if hint:
        row.addWidget(AiHint(hint))
    row.addStretch()
    return row


def _slider_row(label_text: str, min_val: int, max_val: int, value: int,
                fmt=str, hint: str = "") -> tuple[QHBoxLayout, QSlider, QLabel]:
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
    if hint:
        row.addWidget(AiHint(hint))
    return row, slider, val_label


def _section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("color: #aaa; font-size: 12px; font-weight: 600;")
    return lbl


class SettingsPage(QWidget):
    dirty_changed = QtSignal(bool)
    terminal_toggled = QtSignal(bool)
    log_toggled = QtSignal(bool)
    memory_toggled = QtSignal(bool)
    navigate_to = QtSignal(int)  # stack index to navigate to

    def __init__(self, config, assistant, parent=None):
        super().__init__(parent)
        self._config = config
        self._assistant = assistant

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)

        title = QLabel(t("settings_title"))
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
        form.addWidget(_section_title(t("settings_general")))
        form.addSpacing(4)

        general_card = GlassCard()
        gc = general_card.body()
        gc.setSpacing(10)

        self._language = QComboBox()
        self._language.addItem(t("lang_it"), "it")
        self._language.addItem(t("lang_en"), "en")
        current_lang = getattr(config, "language", "it")
        idx = self._language.findData(current_lang)
        if idx >= 0:
            self._language.setCurrentIndex(idx)
        gc.addLayout(_row(t("settings_language"), self._language))

        self._hotkey = QLineEdit(config.hotkey)
        gc.addLayout(_row("Hotkey", self._hotkey, t("ai_hint_hotkey")))

        self._hotkey_suppress = QCheckBox(t("settings_hotkey_suppress"))
        self._hotkey_suppress.setChecked(getattr(config, "hotkey_suppress", False))
        gc.addLayout(_check_row(self._hotkey_suppress, t("ai_hint_hotkey_suppress")))

        self._overlay_enabled = QCheckBox(t("settings_overlay"))
        self._overlay_enabled.setChecked(config.overlay_enabled)
        gc.addLayout(_check_row(self._overlay_enabled, t("ai_hint_overlay")))

        form.addWidget(general_card)
        form.addSpacing(8)

        # ── Card: Wake Word ──────────────────────────────────────
        form.addWidget(_section_title("Wake Word"))
        form.addSpacing(4)

        wake_card = GlassCard()
        wc = wake_card.body()
        wc.setSpacing(10)

        self._wake_word_enabled = QCheckBox(t("settings_wake_word_enabled"))
        self._wake_word_enabled.setChecked(getattr(config, "wake_word_enabled", False))
        wc.addLayout(_check_row(self._wake_word_enabled, t("ai_hint_wake_word")))

        self._wake_keyword = QLineEdit(getattr(config, "wake_word_keyword", "lily"))
        self._wake_keyword.setPlaceholderText("lily")
        wc.addLayout(_row(t("settings_wake_keyword"), self._wake_keyword, t("ai_hint_wake_keyword")))

        sens = int(getattr(config, "wake_word_sensitivity", 0.5) * 100)
        sens_row, self._wake_sensitivity, _ = _slider_row(
            t("settings_wake_sensitivity"), 10, 100, sens,
            fmt=lambda v: f"{v}%",
        )
        wc.addLayout(sens_row)

        form.addWidget(wake_card)
        form.addSpacing(8)

        # ── Card: Audio ───────────────────────────────────────────
        form.addWidget(_section_title(t("settings_audio")))
        form.addSpacing(4)

        audio_card = GlassCard()
        ac = audio_card.body()
        ac.setSpacing(10)

        self._whisper = QComboBox()
        self._whisper.addItems(["tiny", "base", "small", "medium", "large-v3"])
        self._whisper.setCurrentText(config.whisper_model)
        ac.addLayout(_row(t("settings_whisper_model"), self._whisper, t("ai_hint_whisper_model")))

        self._whisper_device = QComboBox()
        self._whisper_device.addItems(["cuda", "cpu"])
        self._whisper_device.setCurrentText(getattr(config, "whisper_device", "cuda"))
        ac.addLayout(_row(t("settings_whisper_device"), self._whisper_device, t("ai_hint_whisper_device")))

        self._mic = QComboBox()
        self._mic.addItem("Default", None)
        self._populate_mics()
        ac.addLayout(_row(t("settings_microphone"), self._mic))

        form.addWidget(audio_card)
        form.addSpacing(8)

        # ── Card: Percorsi ────────────────────────────────────────
        form.addWidget(_section_title(t("settings_paths")))
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
        browse.setFixedSize(36, 36)
        browse.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,10); border: 1px solid rgba(255,255,255,20);"
            " border-radius: 8px; color: #EAEAEA; font-weight: 700; padding: 0px; }"
            " QPushButton:hover { background: rgba(124, 92, 252, 40); }"
        )
        browse.clicked.connect(self._browse_es)
        es_row.addWidget(browse)
        es_row.addWidget(AiHint(t("ai_hint_es_path")))
        ptc.addLayout(es_row)

        tess_row = QHBoxLayout()
        lbl = QLabel("Tesseract Path")
        lbl.setFixedWidth(160)
        tess_row.addWidget(lbl)
        self._tesseract_path = QLineEdit(getattr(config, "tesseract_path", "tesseract"))
        tess_row.addWidget(self._tesseract_path)
        tess_browse = QPushButton("...")
        tess_browse.setFixedSize(36, 36)
        tess_browse.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,10); border: 1px solid rgba(255,255,255,20);"
            " border-radius: 8px; color: #EAEAEA; font-weight: 700; padding: 0px; }"
            " QPushButton:hover { background: rgba(124, 92, 252, 40); }"
        )
        tess_browse.clicked.connect(self._browse_tesseract)
        tess_row.addWidget(tess_browse)
        tess_row.addWidget(AiHint(t("ai_hint_tesseract_path")))
        ptc.addLayout(tess_row)

        form.addWidget(paths_card)
        form.addSpacing(8)

        # ── Card: TTS ─────────────────────────────────────────────
        form.addWidget(_section_title("Text-to-Speech"))
        form.addSpacing(4)

        tts_card = GlassCard()
        tc = tts_card.body()
        tc.setSpacing(10)

        self._tts_enabled = QCheckBox(t("settings_tts_enable"))
        self._tts_enabled.setChecked(config.tts_enabled)
        tc.addLayout(_check_row(self._tts_enabled, t("ai_hint_tts")))

        self._tts_voice = QComboBox()
        from core.voice.tts import TTSEngine
        self._tts_voice.addItems(TTSEngine.available_voices())
        self._tts_voice.setCurrentText(config.tts_voice)
        tc.addLayout(_row(t("settings_tts_voice"), self._tts_voice))

        form.addWidget(tts_card)
        form.addSpacing(8)

        # ── Card: Dettatura ───────────────────────────────────────
        form.addWidget(_section_title(t("settings_dictation")))
        form.addSpacing(4)

        dict_card = GlassCard()
        dc = dict_card.body()
        dc.setSpacing(10)

        ds_row, self._dict_silence, self._ds_label = _slider_row(
            t("settings_dictation_silence"), 10, 100,
            int(getattr(config, "dictation_silence_duration", 3.5) * 10),
            fmt=lambda v: f"{v / 10:.1f}",
            hint=t("ai_hint_dict_silence"))
        dc.addLayout(ds_row)

        dm_row, self._dict_max, self._dm_label = _slider_row(
            t("settings_dictation_max"), 10, 300,
            int(getattr(config, "dictation_max_duration", 60)),
            hint=t("ai_hint_dict_max"))
        dc.addLayout(dm_row)

        dt_row, self._dict_timeout, self._dt_label = _slider_row(
            t("settings_dictation_timeout"), 2, 30,
            int(getattr(config, "dictation_silence_timeout", 4)),
            hint=t("ai_hint_dict_timeout"))
        dc.addLayout(dt_row)

        form.addWidget(dict_card)

        # ── Card: Avanzate ───────────────────────────────────────
        form.addWidget(_section_title(t("settings_advanced")))
        form.addSpacing(4)

        adv_card = GlassCard()
        ac = adv_card.body()

        self._log_enabled = QCheckBox(t("settings_log_enabled"))
        self._log_enabled.setChecked(getattr(config, "log_enabled", False))
        self._log_enabled.toggled.connect(self._check_dirty)

        log_row = QHBoxLayout()
        log_row.addWidget(self._log_enabled)
        log_row.addWidget(AiHint(t("ai_hint_log")))
        log_row.addStretch()
        log_go_btn = QPushButton()
        log_go_btn.setIcon(qta.icon("mdi6.text-box-outline", color="#EAEAEA"))
        log_go_btn.setToolTip(t("sidebar_log"))
        log_go_btn.setFixedSize(28, 28)
        log_go_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        log_go_btn.setStyleSheet("QPushButton { background: rgba(255,255,255,8); border: none; border-radius: 6px; } QPushButton:hover { background: rgba(124, 92, 252, 40); }")
        log_go_btn.clicked.connect(lambda: self.navigate_to.emit(5))
        log_row.addWidget(log_go_btn)
        ac.addLayout(log_row)

        self._terminal_enabled = QCheckBox(t("settings_terminal_enabled"))
        self._terminal_enabled.setChecked(getattr(config, "terminal_enabled", False))
        self._terminal_enabled.toggled.connect(self._check_dirty)

        term_row = QHBoxLayout()
        term_row.addWidget(self._terminal_enabled)
        term_row.addWidget(AiHint(t("ai_hint_terminal")))
        term_row.addStretch()
        term_go_btn = QPushButton()
        term_go_btn.setIcon(qta.icon("mdi6.console", color="#EAEAEA"))
        term_go_btn.setToolTip(t("sidebar_terminal"))
        term_go_btn.setFixedSize(28, 28)
        term_go_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        term_go_btn.setStyleSheet("QPushButton { background: rgba(255,255,255,8); border: none; border-radius: 6px; } QPushButton:hover { background: rgba(124, 92, 252, 40); }")
        term_go_btn.clicked.connect(lambda: self.navigate_to.emit(6))
        term_row.addWidget(term_go_btn)
        ac.addLayout(term_row)

        self._memory_enabled = QCheckBox(t("settings_memory_enabled"))
        self._memory_enabled.setChecked(getattr(config, "memory_enabled", False))
        self._memory_enabled.toggled.connect(self._check_dirty)

        mem_row = QHBoxLayout()
        mem_row.addWidget(self._memory_enabled)
        mem_row.addWidget(AiHint(t("ai_hint_memory")))
        mem_row.addStretch()
        mem_go_btn = QPushButton()
        mem_go_btn.setIcon(qta.icon("mdi6.head-lightbulb-outline", color="#EAEAEA"))
        mem_go_btn.setToolTip(t("sidebar_memory"))
        mem_go_btn.setFixedSize(28, 28)
        mem_go_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        mem_go_btn.setStyleSheet("QPushButton { background: rgba(255,255,255,8); border: none; border-radius: 6px; } QPushButton:hover { background: rgba(124, 92, 252, 40); }")
        mem_go_btn.clicked.connect(lambda: self.navigate_to.emit(4))
        mem_row.addWidget(mem_go_btn)
        ac.addLayout(mem_row)

        form.addWidget(adv_card)

        form.addStretch()

        # ── save / status ─────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._status = QLabel("")
        self._status.setStyleSheet("color: #4CAF50; font-size: 12px;")
        btn_row.addWidget(self._status)
        save_btn = QPushButton(t("settings_save"))
        save_btn.setFixedWidth(120)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        outer.addSpacing(8)
        outer.addLayout(btn_row)

        # ── dirty tracking ─────────────────────────────────────────
        self._snapshot = self._take_snapshot()
        self._language.currentIndexChanged.connect(self._check_dirty)
        self._hotkey.textChanged.connect(self._check_dirty)
        self._hotkey_suppress.toggled.connect(self._check_dirty)
        self._wake_word_enabled.toggled.connect(self._check_dirty)
        self._wake_keyword.textChanged.connect(self._check_dirty)
        self._wake_sensitivity.valueChanged.connect(self._check_dirty)
        self._overlay_enabled.toggled.connect(self._check_dirty)
        self._whisper.currentTextChanged.connect(self._check_dirty)
        self._whisper_device.currentTextChanged.connect(self._check_dirty)
        self._mic.currentIndexChanged.connect(self._check_dirty)
        self._es_path.textChanged.connect(self._check_dirty)
        self._tesseract_path.textChanged.connect(self._check_dirty)
        self._tts_enabled.toggled.connect(self._check_dirty)
        self._tts_voice.currentTextChanged.connect(self._check_dirty)
        self._dict_silence.valueChanged.connect(self._check_dirty)
        self._dict_max.valueChanged.connect(self._check_dirty)
        self._dict_timeout.valueChanged.connect(self._check_dirty)

    # ── dirty tracking ─────────────────────────────────────────────
    def _take_snapshot(self):
        return (
            self._language.currentData(),
            self._hotkey.text().strip(),
            self._hotkey_suppress.isChecked(),
            self._overlay_enabled.isChecked(),
            self._whisper.currentText(),
            self._whisper_device.currentText(),
            self._mic.currentData(),
            self._es_path.text().strip(),
            self._tesseract_path.text().strip(),
            self._tts_enabled.isChecked(),
            self._tts_voice.currentText(),
            self._dict_silence.value(),
            self._dict_max.value(),
            self._dict_timeout.value(),
            self._log_enabled.isChecked(),
            self._terminal_enabled.isChecked(),
            self._memory_enabled.isChecked(),
            self._wake_word_enabled.isChecked(),
            self._wake_keyword.text().strip(),
            self._wake_sensitivity.value(),
        )

    def _check_dirty(self):
        dirty = self._take_snapshot() != self._snapshot
        self.dirty_changed.emit(dirty)

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
        path, _ = QFileDialog.getOpenFileName(self, t("settings_browse_es"), "", t("settings_exe_filter"))
        if path:
            self._es_path.setText(path)

    def _browse_tesseract(self):
        path, _ = QFileDialog.getOpenFileName(self, t("settings_browse_tesseract"), "", t("settings_exe_filter"))
        if path:
            self._tesseract_path.setText(path)

    def _save(self):
        old_hotkey = self._config.hotkey
        old_language = getattr(self._config, "language", "it")
        new_language = self._language.currentData()

        self._config.language = new_language
        self._config.hotkey = self._hotkey.text().strip()
        self._config.hotkey_suppress = self._hotkey_suppress.isChecked()
        self._config.whisper_model = self._whisper.currentText()
        self._config.whisper_device = self._whisper_device.currentText()
        self._config.mic_device = self._mic.currentData()
        self._config.es_path = self._es_path.text().strip()
        self._config.tesseract_path = self._tesseract_path.text().strip()
        self._config.tts_enabled = self._tts_enabled.isChecked()
        self._config.tts_voice = self._tts_voice.currentText()
        self._config.overlay_enabled = self._overlay_enabled.isChecked()
        self._config.dictation_silence_duration = self._dict_silence.value() / 10.0
        self._config.dictation_max_duration = self._dict_max.value()
        self._config.dictation_silence_timeout = self._dict_timeout.value()
        self._config.log_enabled = self._log_enabled.isChecked()
        self._config.terminal_enabled = self._terminal_enabled.isChecked()
        self._config.memory_enabled = self._memory_enabled.isChecked()
        self._config.wake_word_enabled = self._wake_word_enabled.isChecked()
        self._config.wake_word_keyword = self._wake_keyword.text().strip() or "lily"
        self._config.wake_word_sensitivity = self._wake_sensitivity.value() / 100.0
        self._config.save()

        self.log_toggled.emit(self._log_enabled.isChecked())
        self.terminal_toggled.emit(self._terminal_enabled.isChecked())
        self.memory_toggled.emit(self._memory_enabled.isChecked())

        self._assistant.apply_config()
        # Ri-registra hotkey se cambiato tasto o suppress
        self._assistant.update_hotkey()
        self._assistant.update_wake_word()

        self._snapshot = self._take_snapshot()
        self.dirty_changed.emit(False)
        self._status.setText(t("settings_saved"))
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self._status.setText(""))

        if new_language != old_language:
            self._ask_restart()

    def _ask_restart(self):
        dlg = QMessageBox(self)
        dlg.setWindowTitle(t("restart_required_title"))
        dlg.setText(t("restart_required_msg"))
        dlg.setIcon(QMessageBox.Icon.Information)
        btn_now = dlg.addButton(t("restart_now"), QMessageBox.ButtonRole.AcceptRole)
        dlg.addButton(t("restart_later"), QMessageBox.ButtonRole.RejectRole)
        dlg.exec()

        if dlg.clickedButton() == btn_now:
            # Restart the application
            os.execv(sys.executable, [sys.executable] + sys.argv)
