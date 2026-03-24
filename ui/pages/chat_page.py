"""Chat page: interfaccia conversazionale stile chatbot + log sessione vocale."""

import os

from PySide6.QtCore import Qt, Signal, QThread, QSize, QTimer
from PySide6.QtGui import QColor, QFont, QPixmap, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLabel, QPushButton, QLineEdit, QSizePolicy, QFrame,
)
import qtawesome as qta

from core.i18n import t
from ui.style import ACCENT, TEXT, TEXT_SEC, CARD_BG, CARD_BORDER

_AVATAR_SIZE = 28
_LILY_ICON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "assets", "lily.png",
)


def _make_circle_pixmap(path: str, size: int) -> QPixmap:
    src = QPixmap(path).scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    if src.width() != size or src.height() != size:
        x = (src.width() - size) // 2
        y = (src.height() - size) // 2
        src = src.copy(x, y, size, size)
    result = QPixmap(size, size)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addEllipse(0, 0, size, size)
    painter.setClipPath(clip)
    painter.drawPixmap(0, 0, src)
    painter.end()
    return result


# ── Worker thread per pipeline completa ────────────────────────────
class _ChatWorker(QThread):
    finished = Signal(str, int, int)  # response, input_tokens, output_tokens

    def __init__(self, text: str, assistant):
        super().__init__()
        self.text = text
        self.assistant = assistant

    def run(self):
        from core.llm.token_tracker import TokenTracker
        tracker = TokenTracker()
        before_in, before_out = tracker.session_totals()
        try:
            response = self.assistant.process_text_chat(self.text)
        except Exception as e:
            response = t("error_generic", e=e)
        after_in, after_out = tracker.session_totals()
        tok_in = after_in - before_in
        tok_out = after_out - before_out
        self.finished.emit(response, tok_in, tok_out)


# ── Bolla messaggio ────────────────────────────────────────────────
class ChatBubble(QFrame):
    def __init__(self, text: str, is_user: bool, is_voice: bool = False,
                 tok_in: int = 0, tok_out: int = 0, parent=None):
        super().__init__(parent)
        self.setObjectName("chatBubble")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)

        if is_user:
            bg = ACCENT
            border = ACCENT
            text_color = "#FFFFFF"
            radius = "14px 14px 4px 14px"
        else:
            bg = "rgba(255, 255, 255, 10)"
            border = "rgba(255, 255, 255, 15)"
            text_color = TEXT
            radius = "14px 14px 14px 4px"

        self.setStyleSheet(
            f"ChatBubble {{"
            f"  background: {bg};"
            f"  border: 1px solid {border};"
            f"  border-radius: {radius};"
            f"  padding: 0px;"
            f"}}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 8)
        layout.setSpacing(2)

        # Header: nome Lily (sinistra) + icona voce (destra)
        if not is_user or is_voice:
            top_row = QHBoxLayout()
            top_row.setContentsMargins(0, 0, 0, 0)
            top_row.setSpacing(0)

            if not is_user:
                name_label = QLabel("Lily")
                name_label.setStyleSheet(
                    f"QLabel {{ color: {text_color}; font-size: 11px; font-weight: 700;"
                    f" background: transparent; border: none; opacity: 0.8; }}"
                )
                top_row.addWidget(name_label)

            top_row.addStretch()

            if is_voice:
                voice_tag = QLabel()
                tag_color = "rgba(255,255,255,160)" if is_user else "rgba(255,255,255,80)"
                voice_tag.setText(
                    f'<span style="font-size: 10px; color: {tag_color};">\U0001F3A4 {t("chat_voice_tag")}</span>'
                )
                voice_tag.setStyleSheet("QLabel { background: transparent; border: none; }")
                top_row.addWidget(voice_tag)

            layout.addLayout(top_row)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setStyleSheet(
            f"QLabel {{ color: {text_color}; font-size: 13px; background: transparent; border: none; }}"
        )
        layout.addWidget(label)

        # Token info (solo per bolle di Lily, se presenti)
        if not is_user and (tok_in > 0 or tok_out > 0):
            tok_label = QLabel(f"\u25B8 {tok_in} in \u2022 {tok_out} out")
            tok_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            tok_label.setStyleSheet(
                "QLabel { color: rgba(255,255,255,40); font-size: 9px;"
                " background: transparent; border: none; }"
            )
            layout.addWidget(tok_label)

        self.setMaximumWidth(420)


# ── Chat Page ──────────────────────────────────────────────────────
class ChatPage(QWidget):
    def __init__(self, config, bridge=None, assistant=None, parent=None):
        super().__init__(parent)
        self.config = config
        self._bridge = bridge
        self._assistant = assistant
        self._memory = assistant._memory if assistant else None
        self._worker = None

        self._build_ui()

        # Snapshot token per calcolo delta voce
        self._voice_tok_snapshot = (0, 0)

        # Connetti segnali dal bridge (comandi vocali)
        if bridge:
            bridge.state_changed.connect(self._on_state_for_tokens)
            bridge.result_ready.connect(self._on_voice_result)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(0)

        # ── Header ─────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(10)

        title = QLabel("Chat")
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        header.addStretch()

        # Model label
        self._model_label = QLabel("")
        self._model_label.setStyleSheet(
            f"QLabel {{ color: {TEXT_SEC}; font-size: 13px; background: transparent; border: none; }}"
        )
        header.addWidget(self._model_label)

        header.addSpacing(12)

        # Token counter
        self._token_label = QLabel("")
        self._token_label.setStyleSheet(
            f"QLabel {{ color: {TEXT_SEC}; font-size: 13px; background: transparent; border: none; }}"
        )
        header.addWidget(self._token_label)
        self._update_model_label()
        self._update_tokens()

        # Refresh timer (token + contesto + modello)
        self._token_timer = QTimer(self)
        self._token_timer.timeout.connect(self._update_tokens)
        self._token_timer.timeout.connect(self._update_context)
        self._token_timer.timeout.connect(self._update_model_label)
        self._token_timer.start(5000)

        header.addSpacing(8)

        clear_btn = QPushButton()
        clear_btn.setToolTip(t("chat_clear"))
        clear_btn.setIcon(qta.icon("mdi6.delete-outline", color="#EAEAEA"))
        clear_btn.setIconSize(QSize(18, 18))
        clear_btn.setFixedSize(36, 36)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,8); border: 1px solid rgba(255,255,255,15); border-radius: 8px; padding: 0; }"
            "QPushButton:hover { background: rgba(255,255,255,15); }"
        )
        clear_btn.clicked.connect(self._clear_chat)
        header.addWidget(clear_btn)

        root.addLayout(header)
        root.addSpacing(12)

        # ── Scroll area per messaggi ───────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._messages_widget = QWidget()
        self._messages_layout = QVBoxLayout(self._messages_widget)
        self._messages_layout.setContentsMargins(140, 0, 140, 0)  # margini per centrare
        self._messages_layout.setSpacing(12)
        self._messages_layout.addStretch()

        self._scroll.setWidget(self._messages_widget)
        root.addWidget(self._scroll, 1)
        root.addSpacing(12)

        # ── Input bar ──────────────────────────────────────────
        input_bar = QHBoxLayout()
        input_bar.setContentsMargins(140, 0, 140, 0)
        input_bar.setSpacing(8)

        self._input = QLineEdit()
        self._input.setPlaceholderText(t("chat_placeholder"))
        self._input.setFixedHeight(42)
        self._input.setStyleSheet(
            "QLineEdit {"
            "  background: rgba(255, 255, 255, 6);"
            "  border: 1px solid rgba(255, 255, 255, 20);"
            "  border-radius: 12px;"
            "  padding: 8px 16px;"
            f" color: {TEXT};"
            "  font-size: 13px;"
            "}"
            "QLineEdit:focus {"
            f" border: 1px solid {ACCENT};"
            "}"
        )
        self._input.returnPressed.connect(self._send)
        input_bar.addWidget(self._input)

        send_btn = QPushButton()
        send_btn.setIcon(qta.icon("mdi6.send", color="white"))
        send_btn.setIconSize(QSize(20, 20))
        send_btn.setFixedSize(42, 42)
        send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_btn.setStyleSheet(
            f"QPushButton {{ background: {ACCENT}; border: none; border-radius: 12px; padding: 0; }}"
            f"QPushButton:hover {{ background: #9B82FD; }}"
        )
        send_btn.clicked.connect(self._send)
        input_bar.addWidget(send_btn)

        root.addLayout(input_bar)

        # ── Context bar (sotto input) ─────────────────────────
        self._context_label = QLabel("")
        self._context_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._context_label.setContentsMargins(140, 0, 140, 0)
        self._context_label.setStyleSheet(
            f"QLabel {{ color: {TEXT_SEC}; font-size: 12px; background: transparent;"
            f" border: none; padding: 4px 4px 0 4px; }}"
        )
        root.addWidget(self._context_label)
        self._update_context()

        # ── Welcome message ────────────────────────────────────
        self._show_welcome()

    def _update_tokens(self):
        """Aggiorna il contatore token nella header."""
        try:
            from core.llm.token_tracker import TokenTracker
            tracker = TokenTracker()
            provider = getattr(self.config, "provider", "ollama")
            session = tracker.get_session(provider)

            tok_in = session.get("input", 0)
            tok_out = session.get("output", 0)
            cost = session.get("cost", 0.0)
            reqs = session.get("requests", 0)

            parts = [f"\u26A1 {tok_in + tok_out:,} tok"]
            if cost > 0:
                parts.append(f"${cost:.4f}")
            parts.append(f"{reqs} req")

            self._token_label.setText("  \u2022  ".join(parts))
        except Exception:
            self._token_label.setText("")

    _tokenizer = None

    @classmethod
    def _get_tokenizer(cls):
        if cls._tokenizer is None:
            try:
                import tiktoken
                cls._tokenizer = tiktoken.get_encoding("cl100k_base")
            except Exception:
                cls._tokenizer = False  # fallback
        return cls._tokenizer

    def _count_tokens(self, text: str) -> int:
        """Conta token con tiktoken (cl100k_base), fallback a stima."""
        enc = self._get_tokenizer()
        if enc:
            return len(enc.encode(text))
        return max(1, len(text) // 3)

    def _update_model_label(self):
        """Mostra il modello attivo nella header."""
        try:
            provider = getattr(self.config, "provider", "ollama")
            model = getattr(self.config, f"{provider}_model", "") or getattr(self.config, "ollama_model", "")
            self._model_label.setText(f"{provider.capitalize()} — {model}" if model else provider.capitalize())
        except Exception:
            self._model_label.setText("")

    def _update_context(self):
        """Aggiorna l'indicatore del contesto che verrà inviato all'LLM."""
        try:
            from core.llm.prompts import (
                get_classify_prompt, get_chat_system_prompt,
            )

            provider = getattr(self.config, "provider", "ollama")

            # System prompt: sia quello di chat che quello di classificazione
            chat_system = get_chat_system_prompt()
            classify_system = get_classify_prompt(provider)

            # Il più grande dei due (classify è usato dalla voce, chat dalla chat testuale)
            system_text = max(chat_system, classify_system, key=len)
            system_tok = self._count_tokens(system_text)

            # History in memoria
            history_tok = 0
            msg_count = 0
            if self._memory:
                messages = self._memory.get_messages()
                msg_count = len(messages)
                for m in messages:
                    history_tok += self._count_tokens(m.get("content", ""))

            total_ctx = system_tok + history_tok

            # Context window del modello
            if provider == "ollama":
                max_ctx = getattr(self.config, "num_ctx", 8192) or 8192
            else:
                max_ctx = 128_000
            pct = min(100, (total_ctx / max_ctx) * 100)

            if pct < 50:
                color = "#4CAF50"
            elif pct < 80:
                color = "#FF9800"
            else:
                color = "#F44336"

            parts = [
                t("chat_context_info", total_ctx=total_ctx),
                t("chat_context_system", system_tok=system_tok),
                t("chat_context_history", msg_count=msg_count, history_tok=history_tok),
                f'<span style="color: {color};">{pct:.0f}% di {max_ctx:,}</span>',
            ]
            self._context_label.setText("  |  ".join(parts))
        except Exception:
            self._context_label.setText("")

    def _show_welcome(self):
        welcome = QLabel(t("chat_welcome"))
        welcome.setObjectName("chatWelcome")
        welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome.setStyleSheet(
            f"QLabel {{ color: {TEXT_SEC}; font-size: 14px; font-style: italic;"
            f" background: transparent; border: none; padding: 40px; }}"
        )
        self._welcome_label = welcome
        self._messages_layout.insertWidget(0, welcome)

    def _remove_welcome(self):
        if hasattr(self, '_welcome_label') and self._welcome_label:
            self._welcome_label.deleteLater()
            self._welcome_label = None

    def _add_bubble(self, text: str, is_user: bool, is_voice: bool = False,
                    tok_in: int = 0, tok_out: int = 0):
        self._remove_welcome()
        bubble = ChatBubble(text, is_user, is_voice=is_voice, tok_in=tok_in, tok_out=tok_out)

        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent; border: none;")
        row = QHBoxLayout(wrapper)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        if is_user:
            row.addStretch()
            row.addWidget(bubble)
        else:
            # Avatar affiancato alla bolla
            avatar = QLabel()
            avatar.setFixedSize(_AVATAR_SIZE, _AVATAR_SIZE)
            avatar.setPixmap(_make_circle_pixmap(_LILY_ICON, _AVATAR_SIZE))
            avatar.setStyleSheet("QLabel { background: transparent; border: none; }")
            avatar.setAlignment(Qt.AlignmentFlag.AlignTop)
            row.addWidget(avatar, alignment=Qt.AlignmentFlag.AlignTop)
            row.addWidget(bubble)
            row.addStretch()

        count = self._messages_layout.count()
        self._messages_layout.insertWidget(count - 1, wrapper)

        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        vbar = self._scroll.verticalScrollBar()
        vbar.setValue(vbar.maximum())

    # ── Messaggi vocali dal bridge ─────────────────────────────
    def _on_state_for_tokens(self, state: str):
        """Cattura snapshot token quando inizia il processing."""
        if state == "processing":
            try:
                from core.llm.token_tracker import TokenTracker
                self._voice_tok_snapshot = TokenTracker().session_totals()
            except Exception:
                self._voice_tok_snapshot = (0, 0)

    def _on_voice_result(self, text: str, result: str):
        """Riceve i risultati dei comandi vocali e li mostra come bolle."""
        # Calcola token usati da questa richiesta vocale
        tok_in = tok_out = 0
        try:
            from core.llm.token_tracker import TokenTracker
            after_in, after_out = TokenTracker().session_totals()
            tok_in = after_in - self._voice_tok_snapshot[0]
            tok_out = after_out - self._voice_tok_snapshot[1]
        except Exception:
            pass

        if text:
            self._add_bubble(text, is_user=True, is_voice=True)
        if result:
            self._add_bubble(result, is_user=False, is_voice=True, tok_in=tok_in, tok_out=tok_out)
        self._update_tokens()
        self._update_context()

    # ── Messaggi dalla chat testuale ───────────────────────────
    def _send(self):
        text = self._input.text().strip()
        if not text or self._worker is not None:
            return

        self._input.clear()
        self._add_bubble(text, is_user=True)

        # Indicatore "sta scrivendo..."
        self._typing_label = QLabel(t("chat_typing"))
        self._typing_label.setStyleSheet(
            f"QLabel {{ color: {TEXT_SEC}; font-size: 12px; font-style: italic;"
            f" background: transparent; border: none; padding-left: 8px; }}"
        )
        count = self._messages_layout.count()
        self._messages_layout.insertWidget(count - 1, self._typing_label)
        QTimer.singleShot(50, self._scroll_to_bottom)

        # Worker thread (pipeline completa: classify → execute)
        self._worker = _ChatWorker(text, self._assistant)
        self._worker.finished.connect(self._on_chat_response)
        self._worker.start()

    def _on_chat_response(self, response: str, tok_in: int, tok_out: int):
        if hasattr(self, '_typing_label') and self._typing_label:
            self._typing_label.deleteLater()
            self._typing_label = None

        self._add_bubble(response, is_user=False, tok_in=tok_in, tok_out=tok_out)
        self._update_tokens()
        self._update_context()
        self._worker = None

    def _clear_chat(self):
        while self._messages_layout.count() > 1:
            item = self._messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._memory:
            self._memory.clear()

        self._update_context()
        self._show_welcome()
