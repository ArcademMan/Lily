"""LLM configuration page: provider, models, and generation parameters."""

import threading

from PySide6.QtCore import Qt, Signal as QtSignal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QCheckBox, QSlider,
    QPushButton, QScrollArea,
)

from core.i18n import t
from ui.widgets.ai_hint import AiHint
from ui.widgets.glass_card import GlassCard


def _row(label_text: str, widget: QWidget, hint: str = "") -> QHBoxLayout:
    row = QHBoxLayout()
    lbl = QLabel(label_text)
    lbl.setFixedWidth(180)
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
    lbl.setFixedWidth(180)
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


class LLMPage(QWidget):
    dirty_changed = QtSignal(bool)
    _ollama_models_ready = QtSignal(list)
    _ollama_status_ready = QtSignal(bool)

    def __init__(self, config, assistant, parent=None):
        super().__init__(parent)
        self._config = config
        self._assistant = assistant

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)

        title = QLabel("Configurazione LLM")
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

        # ── Card: Provider ────────────────────────────────────────
        form.addWidget(_section_title("Provider"))
        form.addSpacing(4)

        provider_card = GlassCard()
        pc = provider_card.body()
        pc.setSpacing(10)

        self._provider = QComboBox()
        self._provider.addItems(["ollama", "anthropic", "openai", "gemini"])
        self._provider.setCurrentText(config.provider)
        self._provider.currentTextChanged.connect(self._on_provider_changed)
        pc.addLayout(_row("Provider", self._provider, t("ai_hint_llm_provider")))

        # ollama fields
        self._ollama_model = QComboBox()
        self._ollama_model.setEditable(True)
        self._ollama_model.setCurrentText(config.ollama_model)
        self._ollama_row = _row("Modello Ollama", self._ollama_model, t("ai_hint_llm_ollama_model"))
        pc.addLayout(self._ollama_row)
        self._ollama_models_ready.connect(self._populate_ollama_models)
        self._fetch_ollama_models()

        self._ollama_status = QLabel("")
        self._ollama_status.setFixedHeight(20)
        self._ollama_status_row = _row("Stato Ollama", self._ollama_status)
        pc.addLayout(self._ollama_status_row)
        self._ollama_status_ready.connect(self._update_ollama_status)
        self._check_ollama_status()

        # anthropic fields
        self._api_key = QLineEdit(config.anthropic_api_key)
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_row = _row("API Key Anthropic", self._api_key)
        pc.addLayout(self._api_key_row)

        self._anthropic_model = QComboBox()
        self._anthropic_model.addItems([
            "claude-haiku-4-5-20251001",
            "claude-sonnet-4-6-20250514",
        ])
        self._anthropic_model.setCurrentText(config.anthropic_model)
        self._anthropic_model_row = _row("Modello Anthropic", self._anthropic_model)
        pc.addLayout(self._anthropic_model_row)

        # openai fields
        self._openai_api_key = QLineEdit(config.openai_api_key)
        self._openai_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._openai_api_key_row = _row("API Key OpenAI", self._openai_api_key)
        pc.addLayout(self._openai_api_key_row)

        self._openai_model = QComboBox()
        self._openai_model.addItems([
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-5.4-nano",
            "gpt-5.4-mini",
        ])
        self._openai_model.setCurrentText(config.openai_model)
        self._openai_model_row = _row("Modello OpenAI", self._openai_model)
        pc.addLayout(self._openai_model_row)

        # gemini fields
        self._gemini_api_key = QLineEdit(config.gemini_api_key)
        self._gemini_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._gemini_api_key_row = _row("API Key Gemini", self._gemini_api_key)
        pc.addLayout(self._gemini_api_key_row)

        self._gemini_model = QComboBox()
        self._gemini_model.addItems([
            "gemini-2.5-flash",
            "gemini-2.5-pro",
        ])
        self._gemini_model.setCurrentText(config.gemini_model)
        self._gemini_model_row = _row("Modello Gemini", self._gemini_model)
        pc.addLayout(self._gemini_model_row)

        # max results slider (cloud only, always last)
        max_res_row, self._max_results, self._mr_label = _slider_row(
            "Max risultati", 1, 30, config.anthropic_max_results,
            hint=t("ai_hint_llm_max_results"))
        self._max_results_row = max_res_row
        pc.addLayout(max_res_row)

        form.addWidget(provider_card)
        form.addSpacing(8)

        # ── Card: Parametri generazione ───────────────────────────
        form.addWidget(_section_title("Parametri generazione"))
        form.addSpacing(4)

        gen_card = GlassCard()
        gc = gen_card.body()
        gc.setSpacing(10)

        self._thinking = QCheckBox("Ragionamento esteso")
        self._thinking.setChecked(config.thinking_enabled)
        gc.addLayout(_check_row(self._thinking, t("ai_hint_llm_thinking")))

        self._classify_agent = QCheckBox("Classify & Agent")
        self._classify_agent.setChecked(config.classify_agent_enabled)
        gc.addLayout(_check_row(self._classify_agent, t("ai_hint_llm_classify_agent")))

        self._agent = QCheckBox("Agent mode")
        self._agent.setChecked(config.agent_enabled)
        gc.addLayout(_check_row(self._agent, t("ai_hint_llm_agent")))

        # Mutually exclusive: classify_agent <-> agent
        self._classify_agent.toggled.connect(self._on_classify_agent_toggled)
        self._agent.toggled.connect(self._on_agent_toggled)

        np_row, self._num_predict, self._np_label = _slider_row(
            "Token risposta (comandi)", 32, 512, config.num_predict,
            hint=t("ai_hint_llm_num_predict"))
        gc.addLayout(np_row)

        cnp_row, self._chat_num_predict, self._cnp_label = _slider_row(
            "Token risposta (chat)", 64, 1024, config.chat_num_predict,
            hint=t("ai_hint_llm_chat_predict"))
        gc.addLayout(cnp_row)

        hist_row, self._chat_max_history, self._hist_label = _slider_row(
            "Storico chat", 1, 20, config.chat_max_history,
            hint=t("ai_hint_llm_history"))
        gc.addLayout(hist_row)

        form.addWidget(gen_card)

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

        # ── dirty tracking ─────────────────────────────────────────
        self._snapshot = self._take_snapshot()
        self._provider.currentTextChanged.connect(self._check_dirty)
        self._ollama_model.currentTextChanged.connect(self._check_dirty)
        self._ollama_model.editTextChanged.connect(self._check_dirty)
        self._api_key.textChanged.connect(self._check_dirty)
        self._anthropic_model.currentTextChanged.connect(self._check_dirty)
        self._openai_api_key.textChanged.connect(self._check_dirty)
        self._openai_model.currentTextChanged.connect(self._check_dirty)
        self._gemini_api_key.textChanged.connect(self._check_dirty)
        self._gemini_model.currentTextChanged.connect(self._check_dirty)
        self._max_results.valueChanged.connect(self._check_dirty)
        self._thinking.toggled.connect(self._check_dirty)
        self._classify_agent.toggled.connect(self._check_dirty)
        self._agent.toggled.connect(self._check_dirty)
        self._num_predict.valueChanged.connect(self._check_dirty)
        self._chat_num_predict.valueChanged.connect(self._check_dirty)
        self._chat_max_history.valueChanged.connect(self._check_dirty)

    # ── dirty tracking ─────────────────────────────────────────────
    def _take_snapshot(self):
        return (
            self._provider.currentText(),
            self._ollama_model.currentText().strip(),
            self._api_key.text().strip(),
            self._anthropic_model.currentText(),
            self._openai_api_key.text().strip(),
            self._openai_model.currentText(),
            self._gemini_api_key.text().strip(),
            self._gemini_model.currentText(),
            self._max_results.value(),
            self._thinking.isChecked(),
            self._classify_agent.isChecked(),
            self._agent.isChecked(),
            self._num_predict.value(),
            self._chat_num_predict.value(),
            self._chat_max_history.value(),
        )

    def _check_dirty(self):
        dirty = self._take_snapshot() != self._snapshot
        self.dirty_changed.emit(dirty)

    # ── helpers ───────────────────────────────────────────────────
    def _check_ollama_status(self):
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

    def _on_classify_agent_toggled(self, checked: bool):
        if checked:
            self._agent.blockSignals(True)
            self._agent.setChecked(False)
            self._agent.blockSignals(False)

    def _on_agent_toggled(self, checked: bool):
        if checked:
            self._classify_agent.blockSignals(True)
            self._classify_agent.setChecked(False)
            self._classify_agent.blockSignals(False)

    def _on_provider_changed(self, provider: str):
        is_ollama = provider == "ollama"
        is_anthropic = provider == "anthropic"
        is_openai = provider == "openai"
        is_gemini = provider == "gemini"
        is_cloud = not is_ollama
        self._set_row_visible(self._ollama_row, is_ollama)
        self._set_row_visible(self._ollama_status_row, is_ollama)
        self._set_row_visible(self._api_key_row, is_anthropic)
        self._set_row_visible(self._anthropic_model_row, is_anthropic)
        self._set_row_visible(self._openai_api_key_row, is_openai)
        self._set_row_visible(self._openai_model_row, is_openai)
        self._set_row_visible(self._gemini_api_key_row, is_gemini)
        self._set_row_visible(self._gemini_model_row, is_gemini)
        self._set_row_visible(self._max_results_row, is_cloud)

    @staticmethod
    def _set_row_visible(layout: QHBoxLayout, visible: bool):
        for i in range(layout.count()):
            w = layout.itemAt(i).widget()
            if w:
                w.setVisible(visible)

    def _save(self):
        self._config.provider = self._provider.currentText()
        self._config.ollama_model = self._ollama_model.currentText().strip()
        self._config.anthropic_api_key = self._api_key.text().strip()
        self._config.anthropic_model = self._anthropic_model.currentText()
        self._config.anthropic_max_results = self._max_results.value()
        self._config.openai_api_key = self._openai_api_key.text().strip()
        self._config.openai_model = self._openai_model.currentText()
        self._config.gemini_api_key = self._gemini_api_key.text().strip()
        self._config.gemini_model = self._gemini_model.currentText()
        self._config.thinking_enabled = self._thinking.isChecked()
        self._config.classify_agent_enabled = self._classify_agent.isChecked()
        self._config.agent_enabled = self._agent.isChecked()
        self._config.num_predict = self._num_predict.value()
        self._config.chat_num_predict = self._chat_num_predict.value()
        self._config.chat_max_history = self._chat_max_history.value()
        self._config.save()

        self._assistant.apply_config()

        self._snapshot = self._take_snapshot()
        self.dirty_changed.emit(False)
        self._status.setText("Salvato!")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self._status.setText(""))
