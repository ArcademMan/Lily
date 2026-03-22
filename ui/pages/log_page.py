"""Live log page: captures all print() output in real time."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPlainTextEdit, QLineEdit, QPushButton,
)


class LogPage(QWidget):
    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self._bridge = bridge
        self._lines: list[str] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)

        title = QLabel("Log")
        title.setObjectName("sectionTitle")
        outer.addWidget(title)
        outer.addSpacing(8)

        # toolbar
        toolbar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Cerca nei log...")
        self._search.textChanged.connect(self._filter)
        toolbar.addWidget(self._search)

        clear_btn = QPushButton("Cancella")
        clear_btn.setFixedWidth(90)
        clear_btn.clicked.connect(self._clear)
        toolbar.addWidget(clear_btn)
        outer.addLayout(toolbar)
        outer.addSpacing(6)

        # log output
        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setMaximumBlockCount(5000)
        outer.addWidget(self._text)

        bridge.log_line.connect(self._append)

    def _append(self, line: str):
        self._lines.append(line)
        query = self._search.text().lower()
        if not query or query in line.lower():
            self._text.appendPlainText(line)
            sb = self._text.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _filter(self, query: str):
        self._text.clear()
        q = query.lower()
        for line in self._lines:
            if not q or q in line.lower():
                self._text.appendPlainText(line)

    def _clear(self):
        self._lines.clear()
        self._text.clear()
