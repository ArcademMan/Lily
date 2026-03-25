"""Main application window: frameless, glassmorphism, sidebar navigation."""

import ctypes

from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtGui import QIcon, QPainter, QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QSizePolicy,
)

from ui.style import enable_blur, BG
from ui.widgets.animated_stack import AnimatedStack
from ui.widgets.overlay import LilyOverlay
from ui.widgets.sidebar import Sidebar
from ui.pages.voice_page import VoicePage
from ui.pages.llm_page import LLMPage
from ui.pages.settings_page import SettingsPage
from ui.pages.dashboard_page import DashboardPage
from ui.pages.log_page import LogPage
from ui.pages.chat_page import ChatPage
from ui.pages.terminal_page import TerminalPage
from ui.widgets.pick_overlay import PickOverlay


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

        # Overlay
        self._overlay = LilyOverlay(config)
        bridge.state_changed.connect(self._overlay.set_state)
        bridge.countdown.connect(self._overlay.set_countdown)

        # Foreground check timer (every 500ms)
        self._fg_timer = QTimer(self)
        self._fg_timer.timeout.connect(self._check_foreground)
        self._fg_timer.start(500)

        # Pick overlay
        self._pick_overlay = PickOverlay()
        bridge.pick_request.connect(self._on_pick_request)
        bridge.pick_done.connect(self._pick_overlay.hide)
        self._pick_overlay.choice_made.connect(self.assistant.on_pick_choice)

        # Listener per riavvio — intercetta il segnale "__RESTART__" nel main thread Qt
        bridge.notify.connect(self._on_notify_restart)

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

        self._stack = AnimatedStack()
        self._voice_page = VoicePage(self.bridge, config=self.config)
        self._chat_page = ChatPage(self.config, bridge=self.bridge, assistant=self.assistant)
        self._llm_page = LLMPage(self.config, self.assistant)
        self._settings_page = SettingsPage(self.config, self.assistant)
        self._dashboard_page = DashboardPage(config=self.config)
        self._log_page = LogPage(self.bridge)
        self._terminal_page = TerminalPage()

        self._stack.addWidget(self._voice_page)      # 0 — Home (logo)
        self._stack.addWidget(self._chat_page)        # 1 — Chat
        self._stack.addWidget(self._llm_page)         # 2 — LLM
        self._stack.addWidget(self._settings_page)    # 3 — Impostazioni
        self._stack.addWidget(self._dashboard_page)   # 4 — Usage
        self._stack.addWidget(self._log_page)         # 5 — Log
        self._stack.addWidget(self._terminal_page)    # 6 — Terminale

        body_layout.addWidget(self._stack)
        root.addWidget(body)

        # Dirty indicators: LLM page = sidebar index 2, Settings = index 3
        self._llm_page.dirty_changed.connect(lambda d: self._sidebar.set_page_dirty(2, d))
        self._settings_page.dirty_changed.connect(lambda d: self._sidebar.set_page_dirty(3, d))

        # Log visibility from settings
        self._settings_page.log_toggled.connect(self._sidebar.set_log_visible)
        self._sidebar.set_log_visible(getattr(self.config, "log_enabled", False))

        # Terminal visibility from settings
        self._settings_page.terminal_toggled.connect(self._sidebar.set_terminal_visible)
        self._sidebar.set_terminal_visible(getattr(self.config, "terminal_enabled", False))

    def _switch_page(self, index: int):
        self._stack.setCurrentIndex(index)
        # Overlay visible when not on Home (0) or Chat (1)
        self._overlay.set_on_relevant_page(index in (0, 1))
        if index == 0:
            self._voice_page._update_model_label()
        elif index == 4:
            self._dashboard_page.refresh()

    def _on_pick_request(self, results_with_meta, suggested_index):
        self._pick_overlay.show_results(results_with_meta, suggested_index)

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

    # ── foreground detection ──────────────────────────────────────
    def _check_foreground(self):
        if not self._window_is_visible():
            return
        try:
            fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
            my_hwnd = int(self.winId())
            self._overlay.set_window_foreground(fg_hwnd == my_hwnd)
        except Exception:
            pass

    def _window_is_visible(self):
        return self.isVisible() and not (self.windowState() & Qt.WindowState.WindowMinimized)

    # ── tray integration ──────────────────────────────────────────
    def show_and_raise(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _on_notify_restart(self, msg: str):
        if msg == "__RESTART__":
            print("[Restart] Chiusura pulita dal main thread Qt...")
            self._allow_close = True
            from PySide6.QtWidgets import QApplication
            QApplication.instance().quit()

    def allow_close(self):
        self._allow_close = True
        self.close()

    def closeEvent(self, event):
        if self._allow_close:
            self._fg_timer.stop()
            self._overlay.hide()
            self._terminal_page.cleanup()
            event.accept()
        else:
            event.ignore()
            self.hide()
            self._overlay.set_window_visible(False)

    def showEvent(self, event):
        super().showEvent(event)
        self._overlay.set_window_visible(True)
        self._overlay.set_window_foreground(True)
        try:
            enable_blur(int(self.winId()))
        except Exception:
            pass

    def hideEvent(self, event):
        super().hideEvent(event)
        self._overlay.set_window_visible(False)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange:
            minimized = bool(self.windowState() & Qt.WindowState.WindowMinimized)
            self._overlay.set_window_visible(not minimized)
