"""Dialog that downloads the Whisper model from HuggingFace with progress."""

import os
import threading

import requests
from PySide6.QtCore import Qt, Signal as QtSignal
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar

from config import MODELS_DIR

_ACCENT = "#7C5CFC"

_REPO_MAP = {
    "tiny": "Systran/faster-whisper-tiny",
    "base": "Systran/faster-whisper-base",
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
    "large-v3": "Systran/faster-whisper-large-v3",
}

# Files needed by faster-whisper (in download order: small first, big last)
_MODEL_FILES = [
    "config.json",
    "preprocessor_config.json",
    "vocabulary.json",
    "tokenizer.json",
    "model.bin",
]


def _model_dir(model_size: str) -> str:
    return os.path.join(MODELS_DIR, f"faster-whisper-{model_size}")


def is_model_cached(model_size: str) -> bool:
    path = _model_dir(model_size)
    return os.path.isfile(os.path.join(path, "model.bin"))


class ModelDownloadDialog(QDialog):
    """Modal dialog showing Whisper model download progress."""

    _progress_signal = QtSignal(int, str, str)  # percent, size_text, pct_text
    _done_signal = QtSignal(bool, str)

    def __init__(self, model_size: str, parent=None):
        super().__init__(parent)
        self.model_size = model_size
        self.success = False
        self.error_msg = ""
        self._drag_pos = None

        self.setWindowTitle("Download modello")
        self.setFixedSize(500, 200)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setStyleSheet("""
            QDialog {
                background: #16161e;
                border: 1px solid #2a2a3a;
                border-radius: 16px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        title = QLabel("Preparazione di Lily")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {_ACCENT};")
        layout.addWidget(title)

        self._status = QLabel(f"Scaricamento modello vocale ({model_size})...")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setWordWrap(True)
        self._status.setStyleSheet("font-size: 12px; color: #ccc;")
        layout.addWidget(self._status)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(20)
        self._bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid #333;
                border-radius: 6px;
                background: #1e1e2e;
            }}
            QProgressBar::chunk {{
                border-radius: 5px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {_ACCENT}, stop:1 #9B7DFC);
            }}
        """)
        layout.addWidget(self._bar)

        detail_row = QHBoxLayout()
        self._size_label = QLabel("")
        self._size_label.setStyleSheet("font-size: 11px; color: #888;")
        detail_row.addWidget(self._size_label)
        detail_row.addStretch()
        self._pct_label = QLabel("")
        self._pct_label.setStyleSheet("font-size: 11px; color: #888;")
        detail_row.addWidget(self._pct_label)
        layout.addLayout(detail_row)

        layout.addStretch()

        self._progress_signal.connect(self._on_progress)
        self._done_signal.connect(self._on_done)

    # ── Drag ──────────────────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ── Events ────────────────────────────────────────────────────────────────
    def showEvent(self, event):
        super().showEvent(event)
        threading.Thread(target=self._download, daemon=True).start()

    def _on_progress(self, percent: int, size_text: str, pct_text: str):
        self._bar.setValue(percent)
        self._size_label.setText(size_text)
        self._pct_label.setText(pct_text)

    def _on_done(self, ok: bool, msg: str):
        self.success = ok
        self.error_msg = msg
        self.accept()

    # ── Download ──────────────────────────────────────────────────────────────
    def _download(self):
        try:
            repo = _REPO_MAP.get(self.model_size,
                                 f"Systran/faster-whisper-{self.model_size}")
            local_dir = _model_dir(self.model_size)
            os.makedirs(local_dir, exist_ok=True)

            # First pass: get total size via HEAD requests
            base_url = f"https://huggingface.co/{repo}/resolve/main"
            file_sizes = {}
            total_bytes = 0
            for fname in _MODEL_FILES:
                try:
                    r = requests.head(f"{base_url}/{fname}", allow_redirects=True, timeout=10)
                    size = int(r.headers.get("content-length", 0))
                    file_sizes[fname] = size
                    total_bytes += size
                except Exception:
                    file_sizes[fname] = 0

            # Second pass: download each file with real byte-level progress
            import time
            downloaded = 0
            _speed_prev_bytes = 0
            _speed_prev_time = time.monotonic()
            _instant_speed = 0.0

            for fname in _MODEL_FILES:
                dest = os.path.join(local_dir, fname)

                # Skip if already exists with correct size
                if os.path.isfile(dest):
                    existing = os.path.getsize(dest)
                    if file_sizes[fname] and existing == file_sizes[fname]:
                        downloaded += existing
                        continue

                url = f"{base_url}/{fname}"
                r = requests.get(url, stream=True, timeout=30)
                r.raise_for_status()

                file_total = int(r.headers.get("content-length", 0)) or file_sizes[fname]
                tmp = dest + ".tmp"

                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):  # 1 MB chunks
                        f.write(chunk)
                        downloaded += len(chunk)

                        if total_bytes > 0:
                            pct = min(int(downloaded / total_bytes * 100), 99)
                            dl_mb = downloaded / (1024 ** 2)
                            tot_mb = total_bytes / (1024 ** 2)

                            # Instant speed (every 1s window)
                            now = time.monotonic()
                            dt = now - _speed_prev_time
                            if dt >= 1.0:
                                _instant_speed = (downloaded - _speed_prev_bytes) / dt
                                _speed_prev_bytes = downloaded
                                _speed_prev_time = now
                            if _instant_speed >= 1024 * 1024:
                                speed_text = f"{_instant_speed / (1024**2):.1f} MB/s"
                            elif _instant_speed > 0:
                                speed_text = f"{_instant_speed / 1024:.0f} KB/s"
                            else:
                                speed_text = "..."

                            if tot_mb >= 1024:
                                size_text = f"{dl_mb / 1024:.2f} / {tot_mb / 1024:.2f} GB  —  {speed_text}"
                            else:
                                size_text = f"{dl_mb:.1f} / {tot_mb:.1f} MB  —  {speed_text}"
                            self._progress_signal.emit(pct, size_text, f"{pct}%")

                # Atomic rename
                os.replace(tmp, dest)

            self._progress_signal.emit(100, "Download completato!", "100%")
            self._done_signal.emit(True, "")

        except Exception as e:
            self._done_signal.emit(False, str(e))
