"""First-run welcome wizard – explains Lily and optional dependencies."""

import subprocess
import threading

from PySide6.QtCore import Qt, Signal as QtSignal, QPoint
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QWidget,
)

from ui.widgets.glass_card import GlassCard


_ACCENT = "#7C5CFC"


def _status_dot(ok: bool) -> str:
    color = "#4CAF50" if ok else "#F44336"
    label = "Rilevato" if ok else "Non trovato"
    return f'<span style="color:{color}; font-weight:600;">● {label}</span>'


class _DepCard(GlassCard):
    """Card for a single dependency."""

    def __init__(self, name: str, description: str, why: str, url: str, parent=None):
        super().__init__(parent)
        b = self.body()
        b.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel(name)
        title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {_ACCENT};")
        header.addWidget(title)
        header.addStretch()

        self._status = QLabel("")
        self._status.setStyleSheet("font-size: 11px;")
        header.addWidget(self._status)
        b.addLayout(header)

        desc = QLabel(description)
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 12px; color: #ccc;")
        b.addWidget(desc)

        why_label = QLabel(why)
        why_label.setWordWrap(True)
        why_label.setStyleSheet("font-size: 11px; color: #888;")
        b.addWidget(why_label)

        link = QLabel(f'<a style="color:{_ACCENT};" href="{url}">{url}</a>')
        link.setOpenExternalLinks(True)
        link.setStyleSheet("font-size: 11px;")
        b.addWidget(link)

    def set_status(self, ok: bool):
        self._status.setText(_status_dot(ok))


class WelcomeWizard(QDialog):
    """Modal dialog shown on first run."""

    _checks_ready = QtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Benvenuto in Lily")
        self.setFixedSize(560, 620)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._drag_pos = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(12)

        # ── Header ──
        title = QLabel("Benvenuto in Lily")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {_ACCENT};")
        layout.addWidget(title)

        subtitle = QLabel(
            "Assistente vocale per Windows. Controlla il tuo PC con la voce: "
            "apri programmi, cerca file, gestisci finestre, detta testo e molto altro."
        )
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 12px; color: #aaa;")
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        deps_title = QLabel("Dipendenze opzionali")
        deps_title.setStyleSheet("font-size: 13px; font-weight: 600; color: #ccc;")
        layout.addWidget(deps_title)

        # ── Scrollable deps ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        deps_layout = QVBoxLayout(container)
        deps_layout.setContentsMargins(0, 0, 0, 0)
        deps_layout.setSpacing(10)

        self._card_everything = _DepCard(
            "Everything",
            "Motore di ricerca file istantaneo per Windows. Indicizza l'intero disco in pochi secondi.",
            "Lily lo usa per trovare qualsiasi programma, cartella o file sul tuo PC in millisecondi. "
            "Senza Everything la ricerca è limitata a Start Menu, Desktop e Registry.",
            "https://www.voidtools.com/downloads/",
        )
        deps_layout.addWidget(self._card_everything)

        self._card_ollama = _DepCard(
            "Ollama",
            "Server per modelli LLM locali. Esegue modelli AI direttamente sul tuo PC senza costi.",
            "Permette a Lily di ragionare e capire i tuoi comandi usando un LLM locale (es. Qwen, Llama). "
            "Non necessario se preferisci usare API cloud (Anthropic, OpenAI, Gemini).",
            "https://ollama.com/download",
        )
        deps_layout.addWidget(self._card_ollama)

        self._card_cuda = _DepCard(
            "CUDA (NVIDIA)",
            "Librerie GPU NVIDIA per accelerare la trascrizione vocale con Whisper.",
            "Con CUDA la trascrizione è molto più veloce (5-10x). "
            "Se non hai una GPU NVIDIA, puoi usare Whisper su CPU dalle impostazioni (più lento ma funziona).",
            "https://developer.nvidia.com/cuda-downloads",
        )
        deps_layout.addWidget(self._card_cuda)

        self._card_tesseract = _DepCard(
            "Tesseract OCR",
            "Motore OCR open-source per leggere testo dallo schermo.",
            "Usato dalla funzione 'leggi schermo': Lily fa uno screenshot e Tesseract ne estrae il testo. "
            "Necessario solo se vuoi usare questa funzionalità.",
            "https://github.com/tesseract-ocr/tesseract",
        )
        deps_layout.addWidget(self._card_tesseract)

        deps_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        # ── Footer ──
        footer = QHBoxLayout()
        footer.addStretch()

        self._btn = QPushButton("Inizia")
        self._btn.setFixedWidth(140)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(self.accept)
        footer.addWidget(self._btn)
        footer.addStretch()
        layout.addLayout(footer)

        # ── Background checks ──
        self._checks_ready.connect(self._on_checks)
        threading.Thread(target=self._run_checks, daemon=True).start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(22, 22, 32))
        p.setPen(QPen(QColor(255, 255, 255, 20), 1))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 16, 16)
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def _run_checks(self):
        results = {}

        # Everything
        try:
            r = subprocess.run(["es.exe", "-get-everything-version"],
                               capture_output=True, text=True, timeout=3)
            results["everything"] = r.returncode == 0 and bool(r.stdout.strip())
        except Exception:
            results["everything"] = False

        # Ollama
        try:
            r = subprocess.run(["ollama", "list"],
                               capture_output=True, text=True, timeout=5)
            results["ollama"] = r.returncode == 0
        except Exception:
            results["ollama"] = False

        # CUDA (nvidia-smi)
        try:
            r = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=3)
            results["cuda"] = r.returncode == 0
        except Exception:
            results["cuda"] = False

        # Tesseract
        try:
            r = subprocess.run(["tesseract", "--version"],
                               capture_output=True, text=True, timeout=3)
            results["tesseract"] = r.returncode == 0
        except Exception:
            results["tesseract"] = False

        self._checks_ready.emit(results)

    def _on_checks(self, results: dict):
        self._card_everything.set_status(results.get("everything", False))
        self._card_ollama.set_status(results.get("ollama", False))
        self._card_cuda.set_status(results.get("cuda", False))
        self._card_tesseract.set_status(results.get("tesseract", False))
