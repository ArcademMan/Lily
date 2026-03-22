"""Main application window: frameless, glassmorphism, sidebar navigation."""

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QIcon, QPainter, QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QLabel, QPushButton, QSizePolicy,
)

from ui.style import enable_blur, BG
from ui.widgets.sidebar import Sidebar
from ui.pages.voice_page import VoicePage
from ui.pages.settings_page import SettingsPage
from ui.pages.dashboard_page import DashboardPage
from ui.pages.log_page import LogPage


class MainWindow(QMainWindow):
    def __init__(self, config, assistant, bridge, parent=None):
        super().__init__(parent)
        self.config = config
        self.assistant = assistant
        self.bridge = bridge
        self._allow_close = False
        self._drag_pos: QPoint | None = None

        self.setWindowTitle("Lily")
        self.setWindowIcon(QIcon("assets/lily.png"))
        self.setMinimumSize(880, 560)
        self.resize(900, 600)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._build_ui()
        self._center()

    def _build_ui(self):
        central = QWidget(self)
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── title bar ────────────────────────────────────────────
        title_bar = QWidget()
        title_bar.setFixedHeight(38)
        title_bar.setStyleSheet("background: rgba(15, 15, 25, 240); border-top-left-radius: 12px; border-top-right-radius: 12px;")
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(14, 0, 8, 0)
        tb_layout.setSpacing(0)

        title_label = QLabel("Lily")
        title_label.setStyleSheet("color: #EAEAEA; font-size: 13px; font-weight: 600;")
        tb_layout.addWidget(title_label)
        tb_layout.addStretch()

        for text, slot in [("\u2013", self.showMinimized), ("\u2715", self.close)]:
            btn = QPushButton(text)
            btn.setObjectName("flatBtn")
            btn.setFixedSize(36, 28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(slot)
            tb_layout.addWidget(btn)

        root.addWidget(title_bar)

        # ── body: sidebar + pages ────────────────────────────────
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self._sidebar = Sidebar()
        self._sidebar.page_selected.connect(self._switch_page)
        body_layout.addWidget(self._sidebar)

        self._stack = QStackedWidget()
        self._voice_page = VoicePage(self.bridge)
        self._settings_page = SettingsPage(self.config, self.assistant)
        self._dashboard_page = DashboardPage(config=self.config)
        self._log_page = LogPage(self.bridge)

        self._stack.addWidget(self._voice_page)
        self._stack.addWidget(self._settings_page)
        self._stack.addWidget(self._dashboard_page)
        self._stack.addWidget(self._log_page)

        body_layout.addWidget(self._stack)
        root.addWidget(body)

    def _switch_page(self, index: int):
        self._stack.setCurrentIndex(index)
        if index == 2:
            self._dashboard_page.refresh()

    def _center(self):
        screen = self.screen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    # ── frameless drag ────────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 38:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ── background paint ──────────────────────────────────────────
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(25, 25, 35, 200))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(self.rect(), 12, 12)
        p.end()

    # ── tray integration ──────────────────────────────────────────
    def show_and_raise(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def allow_close(self):
        self._allow_close = True
        self.close()

    def closeEvent(self, event):
        if self._allow_close:
            event.accept()
        else:
            event.ignore()
            self.hide()

    def showEvent(self, event):
        super().showEvent(event)
        try:
            enable_blur(int(self.winId()))
        except Exception:
            pass
