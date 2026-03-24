"""Overlay per selezione risultati: appare quando l'LLM non è sicuro della scelta."""

import os

from PySide6.QtCore import Qt, Signal as QtSignal, QTimer, QSize
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QApplication, QScrollArea,
)

from ui.style import ACCENT, TEXT, TEXT_SEC

_MAX_VISIBLE_HEIGHT = 260  # altezza max area risultati (scrollabile)


class _ResultRow(QPushButton):
    """Singola riga cliccabile per un risultato."""

    def __init__(self, index: int, path: str, metadata: str, parent=None):
        super().__init__(parent)
        self.index = index
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)

        # Numero
        num = QLabel(f"{index + 1}")
        num.setFixedWidth(20)
        num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num.setStyleSheet(
            f"QLabel {{ color: {ACCENT}; font-size: 12px; font-weight: 700;"
            f" background: transparent; border: none; }}"
        )
        layout.addWidget(num)

        # Path short
        parts = path.replace("\\", "/").split("/")
        short = "/".join(parts[-3:]) if len(parts) > 3 else path
        path_label = QLabel(short)
        path_label.setStyleSheet(
            f"QLabel {{ color: {TEXT}; font-size: 11px; background: transparent; border: none; }}"
        )
        layout.addWidget(path_label, 1)

        # Metadata inline
        if metadata:
            meta_label = QLabel(metadata)
            meta_label.setStyleSheet(
                f"QLabel {{ color: {TEXT_SEC}; font-size: 9px; background: transparent; border: none; }}"
            )
            layout.addWidget(meta_label)

        self.setStyleSheet(
            "_ResultRow {"
            "  background: rgba(255, 255, 255, 5);"
            "  border: 1px solid rgba(255, 255, 255, 10);"
            "  border-radius: 6px;"
            "}"
            "_ResultRow:hover {"
            "  background: rgba(124, 92, 252, 30);"
            "  border: 1px solid rgba(124, 92, 252, 60);"
            "}"
        )


class PickOverlay(QWidget):
    """Overlay always-on-top che mostra risultati di ricerca ambigui."""

    choice_made = QtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedWidth(460)

        self._results = []
        self._build_ui()

        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.timeout.connect(self._on_timeout)

    def _build_ui(self):
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(0)

        # Container
        self._container = QWidget()
        self._container.setStyleSheet(
            "QWidget#pickContainer {"
            "  background: rgba(20, 20, 32, 240);"
            "  border: 1px solid rgba(124, 92, 252, 40);"
            "  border-radius: 10px;"
            "}"
        )
        self._container.setObjectName("pickContainer")
        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(12, 10, 12, 10)
        container_layout.setSpacing(6)

        # Header
        header = QHBoxLayout()
        header.setSpacing(6)

        title = QLabel("Quale intendevi?")
        title.setStyleSheet(
            f"QLabel {{ color: {TEXT}; font-size: 13px; font-weight: 600;"
            f" background: transparent; border: none; }}"
        )
        header.addWidget(title)

        hint = QLabel('di\' "il primo", "il secondo"... o clicca')
        hint.setStyleSheet(
            f"QLabel {{ color: {TEXT_SEC}; font-size: 9px; font-style: italic;"
            f" background: transparent; border: none; }}"
        )
        header.addWidget(hint)
        header.addStretch()

        cancel_btn = QPushButton("\u2715")
        cancel_btn.setFixedSize(24, 24)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #888;"
            " font-size: 13px; border-radius: 12px; padding: 0; }"
            "QPushButton:hover { background: rgba(255,255,255,10); color: #eee; }"
        )
        cancel_btn.clicked.connect(lambda: self._choose(-1))
        header.addWidget(cancel_btn)

        container_layout.addLayout(header)

        # Scroll area per risultati
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setMaximumHeight(_MAX_VISIBLE_HEIGHT)
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: transparent; width: 4px; }"
            "QScrollBar::handle:vertical { background: rgba(255,255,255,30); border-radius: 2px; min-height: 20px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; height: 0; }"
        )

        self._results_widget = QWidget()
        self._results_widget.setStyleSheet("background: transparent;")
        self._results_layout = QVBoxLayout(self._results_widget)
        self._results_layout.setSpacing(3)
        self._results_layout.setContentsMargins(0, 0, 0, 0)

        self._scroll.setWidget(self._results_widget)
        container_layout.addWidget(self._scroll)

        self._root.addWidget(self._container)

    def show_results(self, results: list[tuple[str, str]], suggested_index: int = -1):
        """Mostra i risultati. results = [(path, metadata), ...]."""
        # Pulisci
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._results = results

        for i, (path, meta) in enumerate(results):
            row = _ResultRow(i, path, meta)
            row.clicked.connect(lambda checked, idx=i: self._choose(idx))
            self._results_layout.addWidget(row)

        self._position()
        self.adjustSize()
        self.show()
        self._timeout.start(30000)

    def _choose(self, index: int):
        self._timeout.stop()
        self.hide()
        self.choice_made.emit(index)

    def _on_timeout(self):
        self.hide()
        self.choice_made.emit(-1)

    def _position(self):
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.left() + 20, geo.top() + 20)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(0, 0, 0, 40))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(self.rect().adjusted(2, 2, 0, 0), 10, 10)
        p.end()
        super().paintEvent(event)
