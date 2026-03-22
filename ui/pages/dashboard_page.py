"""Dashboard page: token usage statistics and daily chart."""

import threading

from PySide6.QtCore import Qt, QTimer, QRectF, Signal as QtSignal
from PySide6.QtGui import QPainter, QColor, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QSizePolicy, QComboBox,
)

from ui.widgets.glass_card import GlassCard
from core.llm.token_tracker import TokenTracker

_ACCENT = QColor("#7C5CFC")


class StatCard(GlassCard):
    """Small card showing a single metric."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.body().setSpacing(4)
        self._title = QLabel(title)
        self._title.setObjectName("secondary")
        self._title.setStyleSheet("color: #888; font-size: 11px;")
        self.body().addWidget(self._title)

        self._value = QLabel("0")
        self._value.setStyleSheet("font-size: 22px; font-weight: 700; color: #EAEAEA;")
        self.body().addWidget(self._value)

    def set_value(self, text: str):
        self._value.setText(text)


class MiniBarChart(QWidget):
    """Simple bar chart drawn with QPainter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(140)
        self._data: list[tuple[str, float]] = []  # (label, value)

    def set_data(self, data: list[tuple[str, float]]):
        self._data = data[-14:]  # last 14 days
        self.update()

    def paintEvent(self, _event):
        if not self._data:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        margin_bottom = 28
        margin_top = 8
        chart_h = h - margin_bottom - margin_top
        max_val = max((v for _, v in self._data), default=1) or 1

        n = len(self._data)
        bar_w = max(8, min(28, (w - 20) // max(n, 1) - 4))
        gap = 4
        total_w = n * (bar_w + gap) - gap
        x0 = (w - total_w) / 2

        for i, (label, val) in enumerate(self._data):
            bar_h = (val / max_val) * chart_h if max_val else 0
            x = x0 + i * (bar_w + gap)
            y = margin_top + chart_h - bar_h

            p.setBrush(_ACCENT)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(x, y, bar_w, bar_h), 3, 3)

            # date label
            p.setPen(QColor("#666666"))
            p.setFont(QFont("Segoe UI", 7))
            short = label[-5:]  # MM-DD
            p.drawText(QRectF(x - 4, h - margin_bottom + 4, bar_w + 8, 20),
                        Qt.AlignmentFlag.AlignCenter, short)

        p.end()


class DashboardPage(QWidget):
    _services_ready = QtSignal(dict)

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self._tracker = TokenTracker()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)

        title_row = QHBoxLayout()
        title = QLabel("Usage")
        title.setObjectName("sectionTitle")
        title_row.addWidget(title)
        title_row.addStretch()

        self._provider_combo = QComboBox()
        self._provider_combo.addItems(["Ollama", "Anthropic"])
        # Default al provider attualmente in uso
        current = config.provider if config else "ollama"
        self._provider_combo.setCurrentText("Anthropic" if current == "anthropic" else "Ollama")
        self._provider_combo.currentTextChanged.connect(lambda _: self.refresh())
        self._provider_combo.setFixedWidth(140)
        title_row.addWidget(self._provider_combo)

        outer.addLayout(title_row)
        outer.addSpacing(12)

        # ── session stats ─────────────────────────────────────────
        session_label = QLabel("Sessione corrente")
        session_label.setStyleSheet("color: #aaa; font-size: 12px; font-weight: 600;")
        outer.addWidget(session_label)
        outer.addSpacing(4)

        row1 = QHBoxLayout()
        row1.setSpacing(12)
        self._s_input = StatCard("Token Input")
        self._s_output = StatCard("Token Output")
        self._s_cost = StatCard("Costo")
        self._s_reqs = StatCard("Richieste Oggi")
        for card in (self._s_input, self._s_output, self._s_cost, self._s_reqs):
            row1.addWidget(card)
        outer.addLayout(row1)
        outer.addSpacing(16)

        # ── total stats ───────────────────────────────────────────
        total_label = QLabel("Totali")
        total_label.setStyleSheet("color: #aaa; font-size: 12px; font-weight: 600;")
        outer.addWidget(total_label)
        outer.addSpacing(4)

        row2 = QHBoxLayout()
        row2.setSpacing(12)
        self._t_tokens = StatCard("Token Totali")
        self._t_cost = StatCard("Costo Totale")
        row2.addWidget(self._t_tokens)
        row2.addWidget(self._t_cost)
        row2.addStretch()
        outer.addLayout(row2)
        outer.addSpacing(16)

        # ── chart ─────────────────────────────────────────────────
        chart_label = QLabel("Uso giornaliero (richieste)")
        chart_label.setStyleSheet("color: #aaa; font-size: 12px; font-weight: 600;")
        outer.addWidget(chart_label)

        chart_card = GlassCard()
        self._chart = MiniBarChart()
        chart_card.body().addWidget(self._chart)
        outer.addWidget(chart_card)

        outer.addStretch()

        # ── status bar ──────────────────────────────────────────
        self._config = config
        status_card = GlassCard()
        status_layout = QHBoxLayout()
        status_layout.setSpacing(20)

        self._status_ollama = QLabel("Ollama: ...")
        self._status_ollama.setStyleSheet("font-size: 11px; color: #888;")
        status_layout.addWidget(self._status_ollama)

        self._status_everything = QLabel("Everything: ...")
        self._status_everything.setStyleSheet("font-size: 11px; color: #888;")
        status_layout.addWidget(self._status_everything)

        status_layout.addStretch()
        status_card.body().addLayout(status_layout)
        outer.addWidget(status_card)

        # auto refresh
        self._services_ready.connect(self._update_services)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(3000)
        self.refresh()
        self._check_services()

    def showEvent(self, event):
        super().showEvent(event)
        self._timer.start(5000)
        self.refresh()
        self._check_services()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()

    def _selected_provider(self) -> str:
        return "anthropic" if self._provider_combo.currentText() == "Anthropic" else "ollama"

    def refresh(self):
        t = self._tracker
        provider = self._selected_provider()

        session = t.get_session(provider)
        self._s_input.set_value(f"{session['input']:,}")
        self._s_output.set_value(f"{session['output']:,}")
        self._s_cost.set_value(f"${session['cost']:.4f}")

        # today's requests
        sessions = t.get_sessions(provider)
        from datetime import date
        today = date.today().isoformat()
        today_reqs = 0
        if sessions and sessions[-1].get("date") == today:
            today_reqs = sessions[-1].get("requests", 0)
        self._s_reqs.set_value(str(today_reqs))

        totals = t.get_totals(provider)
        self._t_tokens.set_value(f"{totals['total_input'] + totals['total_output']:,}")
        self._t_cost.set_value(f"${totals['total_cost']:.4f}")

        # chart data
        chart_data = [(s["date"], s.get("requests", 0)) for s in sessions]
        self._chart.set_data(chart_data)

    def _check_services(self):
        """Controlla lo stato dei servizi in background."""
        def _check():
            status = {}
            # Ollama
            try:
                from core.llm.ollama_provider import OllamaProvider
                status["ollama"] = OllamaProvider().check()
            except Exception:
                status["ollama"] = False
            # Everything
            try:
                from core.search import check_everything
                es_path = self._config.es_path if self._config else "es.exe"
                status["everything"] = check_everything(es_path)
            except Exception:
                status["everything"] = False
            self._services_ready.emit(status)

        threading.Thread(target=_check, daemon=True).start()

    def _update_services(self, status: dict):
        def _fmt(name, ok):
            color = "#4CAF50" if ok else "#F44336"
            text = "OK" if ok else "Off"
            return f'<span style="color:{color}; font-weight:bold;">{name}: {text}</span>'

        self._status_ollama.setText(_fmt("Ollama", status.get("ollama", False)))
        self._status_everything.setText(_fmt("Everything", status.get("everything", False)))
