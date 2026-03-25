"""Memory page: view and manage Lily's persistent user memories + token cost."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QMessageBox,
)

from core.memory import load_memory, save_memory, MEMORY_FILE
from ui.widgets.glass_card import GlassCard

_tokenizer = None


def _count_tokens(text: str) -> int:
    """Conta token con tiktoken (cl100k_base), fallback a stima."""
    global _tokenizer
    if not text:
        return 0
    if _tokenizer is None:
        try:
            import tiktoken
            _tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _tokenizer = False
    if _tokenizer:
        return len(_tokenizer.encode(text))
    return max(1, len(text) // 3)


class MemoryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)

        title = QLabel("Memoria permanente")
        title.setObjectName("sectionTitle")
        outer.addWidget(title)
        outer.addSpacing(4)

        # Info card
        info_card = GlassCard()
        info_layout = info_card.body()

        desc = QLabel(
            "Queste sono le preferenze e informazioni che Lily ricorda tra le sessioni.\n"
            "Vengono iniettate nel prompt di ogni richiesta LLM."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #aaa; font-size: 12px;")
        info_layout.addWidget(desc)

        # Token count
        self._token_label = QLabel()
        self._token_label.setStyleSheet("color: #7C5CFC; font-size: 12px; font-weight: 600;")
        info_layout.addWidget(self._token_label)

        outer.addWidget(info_card)
        outer.addSpacing(8)

        # Editor
        self._editor = QPlainTextEdit()
        self._editor.setPlaceholderText("Nessuna memoria salvata...")
        self._editor.textChanged.connect(self._on_text_changed)
        outer.addWidget(self._editor)

        # Toolbar
        toolbar = QHBoxLayout()

        self._status = QLabel()
        self._status.setStyleSheet("color: #888; font-size: 11px;")
        toolbar.addWidget(self._status)
        toolbar.addStretch()

        reload_btn = QPushButton("Ricarica")
        reload_btn.setFixedWidth(90)
        reload_btn.clicked.connect(self._reload)
        toolbar.addWidget(reload_btn)

        self._save_btn = QPushButton("Salva")
        self._save_btn.setFixedWidth(90)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save)
        toolbar.addWidget(self._save_btn)

        clear_btn = QPushButton("Svuota")
        clear_btn.setFixedWidth(90)
        clear_btn.clicked.connect(self._clear)
        toolbar.addWidget(clear_btn)

        outer.addLayout(toolbar)

        # Path info
        path_label = QLabel(MEMORY_FILE)
        path_label.setStyleSheet("color: #555; font-size: 10px;")
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        outer.addWidget(path_label)

        self._dirty = False
        self._reload()

    def _reload(self):
        content = load_memory()
        self._editor.blockSignals(True)
        self._editor.setPlainText(content)
        self._editor.blockSignals(False)
        self._dirty = False
        self._save_btn.setEnabled(False)
        self._update_token_count(content)
        self._status.setText("")

    def _on_text_changed(self):
        self._dirty = True
        self._save_btn.setEnabled(True)
        self._update_token_count(self._editor.toPlainText())

    def _update_token_count(self, text: str):
        tokens = _count_tokens(text)
        lines = len(text.splitlines()) if text.strip() else 0
        self._token_label.setText(
            f"{lines} righe  |  ~{tokens} token per richiesta LLM"
        )

    def _save(self):
        content = self._editor.toPlainText().strip()
        save_memory(content)
        self._dirty = False
        self._save_btn.setEnabled(False)
        self._status.setText("Salvato")

    def _clear(self):
        if not self._editor.toPlainText().strip():
            return
        reply = QMessageBox.question(
            self, "Svuota memoria",
            "Cancellare tutta la memoria permanente?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._editor.clear()
            save_memory("")
            self._dirty = False
            self._save_btn.setEnabled(False)
            self._status.setText("Memoria svuotata")
            self._update_token_count("")
