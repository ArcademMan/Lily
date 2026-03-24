"""Embedded real terminal: ConPTY (pywinpty) + xterm.js in QWebEngineView.

Supports multiple tabs, each with its own PTY session.
"""

import json
import os
import threading

from PySide6.QtCore import Qt, QObject, Signal, Slot, QUrl, QTimer
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QStackedWidget, QSizePolicy,
)

from winpty import PtyProcess

from core import terminal_buffer


# ── xterm.js HTML ────────────────────────────────────────────────
_XTERM_HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/css/xterm.min.css">
<script src="https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/lib/xterm.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@xterm/addon-fit@0.10.0/lib/addon-fit.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@xterm/addon-web-links@0.11.0/lib/addon-web-links.min.js"></script>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { width: 100%; height: 100%; overflow: hidden; background: transparent; }
  #terminal { width: 100%; height: 100%; }
  .xterm { height: 100%; }
  .xterm-viewport::-webkit-scrollbar { width: 6px; }
  .xterm-viewport::-webkit-scrollbar-track { background: transparent; }
  .xterm-viewport::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.2); border-radius: 3px; }
</style>
</head>
<body>
<div id="terminal"></div>
<script>
let bridge = null;
let term = null;
let fitAddon = null;

function initTerminal() {
    term = new Terminal({
        theme: {
            background: 'rgba(0, 0, 0, 0)',
            foreground: '#EAEAEA',
            cursor: '#7C5CFC',
            cursorAccent: '#191923',
            selectionBackground: 'rgba(124, 92, 252, 0.4)',
            selectionForeground: '#FFFFFF',
            black: '#1e1e1e',
            red: '#F44747',
            green: '#6A9955',
            yellow: '#DCDCAA',
            blue: '#569CD6',
            magenta: '#C586C0',
            cyan: '#4EC9B0',
            white: '#D4D4D4',
            brightBlack: '#808080',
            brightRed: '#F44747',
            brightGreen: '#6A9955',
            brightYellow: '#DCDCAA',
            brightBlue: '#569CD6',
            brightMagenta: '#C586C0',
            brightCyan: '#4EC9B0',
            brightWhite: '#FFFFFF'
        },
        fontFamily: '"Cascadia Code", "Consolas", monospace',
        fontSize: 13,
        lineHeight: 1.2,
        cursorBlink: true,
        cursorStyle: 'bar',
        scrollback: 10000,
        allowTransparency: true,
        convertEol: false
    });

    fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);

    const webLinksAddon = new WebLinksAddon.WebLinksAddon();
    term.loadAddon(webLinksAddon);

    term.open(document.getElementById('terminal'));
    fitAddon.fit();

    term.onData(function(data) {
        if (bridge) bridge.on_input(data);
    });

    term.onResize(function(size) {
        if (bridge) bridge.on_resize(size.cols, size.rows);
    });

    new ResizeObserver(function() {
        if (fitAddon) fitAddon.fit();
    }).observe(document.getElementById('terminal'));
}

// Called from Python to scroll to bottom
function scrollToBottom() {
    if (term) term.scrollToBottom();
}

new QWebChannel(qt.webChannelTransport, function(channel) {
    bridge = channel.objects.bridge;

    bridge.output_ready.connect(function(data) {
        if (term) term.write(data);
    });

    // Python can ask us to clear
    bridge.clear_requested.connect(function() {
        if (term) { term.clear(); term.scrollToTop(); }
    });

    initTerminal();

    setTimeout(function() {
        if (fitAddon && bridge) {
            fitAddon.fit();
            bridge.on_ready(term.cols, term.rows);
        }
    }, 100);
});
</script>
</body>
</html>"""


# ── Bridge: Python ↔ xterm.js ───────────────────────────────────

class PtyBridge(QObject):
    """Bridges xterm.js (in QWebEngineView) with a ConPTY process."""

    output_ready = Signal(str)
    clear_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pty: PtyProcess | None = None
        self._reader_thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start_pty(self, shell: str, cwd: str, rows: int = 24, cols: int = 80):
        self.stop_pty()
        self._stop.clear()

        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"

        try:
            self._pty = PtyProcess.spawn(
                shell, cwd=cwd, env=env, dimensions=(rows, cols),
            )
        except Exception as e:
            self.output_ready.emit(f"\r\nErrore avvio shell: {e}\r\n")
            return

        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()

    def stop_pty(self):
        self._stop.set()
        if self._pty:
            try:
                if self._pty.isalive():
                    self._pty.close(force=True)
            except Exception:
                pass
            self._pty = None
        self._reader_thread = None

    def is_alive(self) -> bool:
        return self._pty is not None and self._pty.isalive()

    def _read_loop(self):
        while not self._stop.is_set():
            try:
                if not self._pty or not self._pty.isalive():
                    break
                data = self._pty.read(4096)
                if data:
                    terminal_buffer.append(data)
                    self.output_ready.emit(data)
            except EOFError:
                break
            except Exception:
                if self._stop.is_set():
                    break
                continue

        if not self._stop.is_set():
            self.output_ready.emit("\r\n[Processo terminato]\r\n")

    @Slot(str)
    def on_input(self, data: str):
        if self._pty and self._pty.isalive():
            try:
                self._pty.write(data)
            except Exception:
                pass

    @Slot(int, int)
    def on_resize(self, cols: int, rows: int):
        if self._pty and self._pty.isalive():
            try:
                self._pty.setwinsize(rows, cols)
            except Exception:
                pass

    @Slot(int, int)
    def on_ready(self, cols: int, rows: int):
        self.on_resize(cols, rows)


# ── Single terminal session (WebView + PTY) ─────────────────────

class TerminalSession(QWidget):
    """One terminal tab: a QWebEngineView wired to a PtyBridge."""

    closed = Signal(object)  # emits self

    def __init__(self, cwd: str, parent=None):
        super().__init__(parent)
        self._cwd = cwd
        self._bridge = PtyBridge(self)
        self._loaded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._web = QWebEngineView()
        self._web.setStyleSheet(
            "QWebEngineView {"
            "  background: rgba(0, 0, 0, 80);"
            "  border: 1px solid rgba(255, 255, 255, 15);"
            "  border-radius: 10px;"
            "}"
        )
        settings = self._web.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        self._channel = QWebChannel()
        self._channel.registerObject("bridge", self._bridge)
        self._web.page().setWebChannel(self._channel)
        self._web.page().setBackgroundColor(Qt.GlobalColor.transparent)

        layout.addWidget(self._web)

    def start(self):
        if self._loaded:
            return
        self._loaded = True
        self._web.setHtml(_XTERM_HTML, QUrl("https://cdn.jsdelivr.net"))
        QTimer.singleShot(800, self._start_shell)

    def _start_shell(self):
        self._bridge.start_pty("powershell.exe", cwd=self._cwd)

    def restart(self):
        self._bridge.stop_pty()
        self._bridge.clear_requested.emit()
        self._bridge.start_pty("powershell.exe", cwd=self._cwd)

    def scroll_to_bottom(self):
        self._web.page().runJavaScript("scrollToBottom();")

    def is_alive(self) -> bool:
        return self._bridge.is_alive()

    def cleanup(self):
        self._bridge.stop_pty()


# ── Tab button ───────────────────────────────────────────────────

import qtawesome as qta
from PySide6.QtGui import QIcon
from PySide6.QtCore import QSize


class TabButton(QWidget):
    """A single tab: icon + label + close, styled like modern terminal tabs."""

    clicked = Signal()
    close_clicked = Signal()

    _ACTIVE_SS = (
        "TabButton { background: rgba(255, 255, 255, 10);"
        "  border: 1px solid rgba(255, 255, 255, 18);"
        "  border-bottom: 2px solid #7C5CFC;"
        "  border-radius: 8px; border-bottom-left-radius: 0; border-bottom-right-radius: 0; }"
    )
    _INACTIVE_SS = (
        "TabButton { background: transparent;"
        "  border: 1px solid transparent;"
        "  border-bottom: 1px solid rgba(255, 255, 255, 8);"
        "  border-radius: 8px; border-bottom-left-radius: 0; border-bottom-right-radius: 0; }"
        "TabButton:hover { background: rgba(255, 255, 255, 6); }"
    )

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self._label_text = label
        self._active = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(34)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 6, 4)
        layout.setSpacing(6)

        # Terminal icon
        self._icon = QLabel()
        self._icon.setFixedSize(16, 16)
        self._icon.setPixmap(
            qta.icon("mdi6.console", color="#888").pixmap(QSize(16, 16))
        )
        layout.addWidget(self._icon)

        # Label
        self._label = QLabel(label)
        self._label.setStyleSheet("border: none; background: transparent; font-size: 12px;")
        layout.addWidget(self._label)

        # Close button
        self._close_btn = QPushButton()
        self._close_btn.setIcon(qta.icon("mdi6.close", color="#666"))
        self._close_btn.setIconSize(QSize(14, 14))
        self._close_btn.setFixedSize(20, 20)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setToolTip("Chiudi tab")
        self._close_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; border-radius: 4px; padding: 0; }"
            "QPushButton:hover { background: rgba(255, 80, 80, 0.4); }"
        )
        self._close_btn.clicked.connect(self.close_clicked.emit)
        layout.addWidget(self._close_btn)

        self.set_active(False)

    def set_active(self, active: bool):
        self._active = active
        self.setStyleSheet(self._ACTIVE_SS if active else self._INACTIVE_SS)
        color = "#EAEAEA" if active else "#888"
        self._label.setStyleSheet(
            f"border: none; background: transparent; font-size: 12px;"
            f" color: {color}; font-weight: {'600' if active else '400'};"
        )
        self._icon.setPixmap(
            qta.icon("mdi6.console", color="#7C5CFC" if active else "#666").pixmap(QSize(16, 16))
        )

    def set_label(self, label: str):
        self._label_text = label
        self._label.setText(label)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ── Terminal Page (main widget) ──────────────────────────────────

class TerminalPage(QWidget):
    """Terminal page with tabbed sessions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cwd = os.path.expanduser("~")
        self._sessions: list[TerminalSession] = []
        self._tab_buttons: list[TabButton] = []
        self._counter = 0
        self._first_show = True

        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(0)

        # ── Header row ───────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("Terminale")
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        header.addStretch()
        outer.addLayout(header)
        outer.addSpacing(8)

        # ── Tab bar ──────────────────────────────────────────────
        tab_bar_row = QHBoxLayout()
        tab_bar_row.setContentsMargins(0, 0, 0, 0)
        tab_bar_row.setSpacing(2)

        self._tab_bar = QHBoxLayout()
        self._tab_bar.setContentsMargins(0, 0, 0, 0)
        self._tab_bar.setSpacing(2)
        tab_bar_row.addLayout(self._tab_bar)

        # "+" button for new tab
        add_btn = QPushButton()
        add_btn.setIcon(qta.icon("mdi6.plus", color="#888"))
        add_btn.setIconSize(QSize(18, 18))
        add_btn.setFixedSize(34, 34)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setToolTip("Nuova sessione")
        add_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; border-radius: 8px; }"
            "QPushButton:hover { background: rgba(255, 255, 255, 10); }"
        )
        add_btn.clicked.connect(self._add_tab)
        tab_bar_row.addWidget(add_btn)

        tab_bar_row.addStretch()
        outer.addLayout(tab_bar_row)
        outer.addSpacing(4)

        # ── Stacked sessions (inside a container for the floating btn)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("QStackedWidget { background: transparent; }")
        container_layout.addWidget(self._stack)

        outer.addWidget(container)

        # ── Floating scroll-to-bottom button ─────────────────────
        self._bottom_btn = QPushButton(self)
        self._bottom_btn.setIcon(qta.icon("mdi6.chevron-double-down", color="#EAEAEA"))
        self._bottom_btn.setIconSize(QSize(20, 20))
        self._bottom_btn.setFixedSize(36, 36)
        self._bottom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bottom_btn.setToolTip("Vai in fondo")
        self._bottom_btn.setStyleSheet(
            "QPushButton { background: rgba(30, 30, 45, 200);"
            "  border: 1px solid rgba(255, 255, 255, 20);"
            "  border-radius: 18px; }"
            "QPushButton:hover { background: rgba(124, 92, 252, 0.6); }"
        )
        self._bottom_btn.clicked.connect(self._scroll_to_bottom)
        self._bottom_btn.raise_()

    # ── Tab management ────────────────────────────────────────────

    def _add_tab(self):
        self._counter += 1
        label = f"PS {self._counter}"

        session = TerminalSession(self._cwd, self)
        self._sessions.append(session)
        self._stack.addWidget(session)

        tab = TabButton(label, self)
        tab.clicked.connect(lambda s=session: self._switch_to(s))
        tab.close_clicked.connect(lambda s=session: self._close_tab(s))
        self._tab_buttons.append(tab)
        self._tab_bar.addWidget(tab)

        self._switch_to(session)
        session.start()

    def _switch_to(self, session: TerminalSession):
        self._stack.setCurrentWidget(session)
        for i, s in enumerate(self._sessions):
            self._tab_buttons[i].set_active(s is session)

    def _close_tab(self, session: TerminalSession):
        # Don't close last tab
        if len(self._sessions) <= 1:
            return

        idx = self._sessions.index(session)
        session.cleanup()

        # Remove tab button
        tab = self._tab_buttons.pop(idx)
        self._tab_bar.removeWidget(tab)
        tab.deleteLater()

        # Remove session
        self._stack.removeWidget(session)
        self._sessions.remove(session)
        session.deleteLater()

        # Switch to neighbor
        new_idx = min(idx, len(self._sessions) - 1)
        self._switch_to(self._sessions[new_idx])

    def _scroll_to_bottom(self):
        current = self._stack.currentWidget()
        if isinstance(current, TerminalSession):
            current.scroll_to_bottom()

    # ── lifecycle ──────────────────────────────────────────────────

    def _reposition_bottom_btn(self):
        margin = 20
        x = self.width() - self._bottom_btn.width() - margin - 24
        y = self.height() - self._bottom_btn.height() - margin - 20
        self._bottom_btn.move(x, y)
        self._bottom_btn.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_bottom_btn()

    def showEvent(self, event):
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            self._add_tab()
        QTimer.singleShot(0, self._reposition_bottom_btn)

    def cleanup(self):
        for session in self._sessions:
            session.cleanup()
