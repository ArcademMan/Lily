"""Dashboard page: token usage statistics, per-model breakdown, and daily chart."""

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QColor, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QScrollArea, QFrame,
)

from ui.widgets.glass_card import GlassCard
from core.llm.token_tracker import TokenTracker, _cost_from_models

_ACCENT = QColor("#7C5CFC")
_GREEN = QColor("#4CAF50")
_ORANGE = QColor("#FF9800")
_RED = QColor("#F44336")
_BLUE = QColor("#2196F3")

# Colori per modelli (ciclici)
_MODEL_COLORS = [
    "#7C5CFC", "#4CAF50", "#FF9800", "#2196F3", "#E91E63", "#00BCD4", "#FF5722",
]


class StatCard(GlassCard):
    """Small card showing a single metric."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.body().setSpacing(4)
        self._title = QLabel(title)
        self._title.setStyleSheet("color: #888; font-size: 11px;")
        self.body().addWidget(self._title)

        self._value = QLabel("0")
        self._value.setStyleSheet("font-size: 22px; font-weight: 700; color: #EAEAEA;")
        self.body().addWidget(self._value)

        self._sub = QLabel("")
        self._sub.setStyleSheet("color: #666; font-size: 10px;")
        self._sub.setVisible(False)
        self.body().addWidget(self._sub)

    def set_value(self, text: str):
        self._value.setText(text)

    def set_sub(self, text: str):
        self._sub.setText(text)
        self._sub.setVisible(bool(text))


class ModelRow(QFrame):
    """A single row showing model stats."""

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "ModelRow { background: rgba(255,255,255,4); border-radius: 8px; }"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color: {color}; font-size: 10px;")
        self._dot.setFixedWidth(14)
        layout.addWidget(self._dot)

        self._name = QLabel("")
        self._name.setStyleSheet("font-size: 12px; font-weight: 600; color: #ddd;")
        self._name.setMinimumWidth(180)
        layout.addWidget(self._name)

        self._tokens = QLabel("")
        self._tokens.setStyleSheet("font-size: 11px; color: #aaa;")
        self._tokens.setMinimumWidth(160)
        layout.addWidget(self._tokens)

        self._reqs = QLabel("")
        self._reqs.setStyleSheet("font-size: 11px; color: #aaa;")
        self._reqs.setMinimumWidth(80)
        layout.addWidget(self._reqs)

        self._cost = QLabel("")
        self._cost.setStyleSheet("font-size: 12px; font-weight: 600; color: #EAEAEA;")
        layout.addWidget(self._cost)

        layout.addStretch()

    def update_data(self, name: str, input_t: int, output_t: int, requests: int, cost: float):
        # Abbrevia il nome del modello
        short = name
        for prefix in ("claude-", "gpt-"):
            if short.startswith(prefix):
                short = short[len(prefix):]
                break
        self._name.setText(short)
        self._tokens.setText(f"↑ {input_t:,}  ↓ {output_t:,}")
        self._reqs.setText(f"{requests:,} req")
        self._cost.setText(f"${cost:.4f}")


class MiniBarChart(QWidget):
    """Bar chart with dual mode: requests or cost."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(140)
        self._data: list[tuple[str, float]] = []

    def set_data(self, data: list[tuple[str, float]]):
        self._data = data[-14:]
        self.update()

    def paintEvent(self, _event):
        if not self._data:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        margin_bottom = 28
        margin_top = 18
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

            # Valore sopra la barra
            if val > 0:
                p.setPen(QColor("#aaa"))
                p.setFont(QFont("Segoe UI", 7))
                val_text = f"{val:,.0f}" if val >= 1 else f"{val:.3f}"
                p.drawText(QRectF(x - 10, y - 16, bar_w + 20, 14),
                           Qt.AlignmentFlag.AlignCenter, val_text)

            # Data
            p.setPen(QColor("#666"))
            p.setFont(QFont("Segoe UI", 7))
            short = label[-5:]  # MM-DD
            p.drawText(QRectF(x - 4, h - margin_bottom + 4, bar_w + 8, 20),
                       Qt.AlignmentFlag.AlignCenter, short)

        p.end()


class DashboardPage(QWidget):

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self._tracker = TokenTracker()

        # Scroll area per contenuto lungo
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(24, 20, 24, 20)

        # ── Header ──────────────────────────────────────────────
        title_row = QHBoxLayout()
        title = QLabel("Usage")
        title.setObjectName("sectionTitle")
        title_row.addWidget(title)
        title_row.addStretch()

        self._provider_combo = QComboBox()
        self._provider_combo.addItems(["Ollama", "Anthropic", "OpenAI", "Gemini"])
        current = config.provider if config else "ollama"
        _provider_labels = {"anthropic": "Anthropic", "openai": "OpenAI", "gemini": "Gemini", "ollama": "Ollama"}
        self._provider_combo.setCurrentText(_provider_labels.get(current, "Ollama"))
        self._provider_combo.currentTextChanged.connect(lambda _: self.refresh())
        self._provider_combo.setFixedWidth(140)
        title_row.addWidget(self._provider_combo)

        self._chart_mode = QComboBox()
        self._chart_mode.addItems(["Richieste", "Costo", "Token"])
        self._chart_mode.setFixedWidth(110)
        self._chart_mode.currentTextChanged.connect(lambda _: self.refresh())
        title_row.addWidget(self._chart_mode)

        outer.addLayout(title_row)
        outer.addSpacing(12)

        # ── Sessione corrente ───────────────────────────────────
        session_label = QLabel("Sessione corrente")
        session_label.setStyleSheet("color: #aaa; font-size: 12px; font-weight: 600;")
        outer.addWidget(session_label)
        outer.addSpacing(4)

        row1 = QHBoxLayout()
        row1.setSpacing(12)
        self._s_input = StatCard("Token Input")
        self._s_output = StatCard("Token Output")
        self._s_reqs = StatCard("Richieste")
        self._s_cost = StatCard("Costo Sessione")
        for card in (self._s_input, self._s_output, self._s_reqs, self._s_cost):
            row1.addWidget(card)
        outer.addLayout(row1)
        outer.addSpacing(4)

        # Model breakdown sessione
        self._session_models_container = QVBoxLayout()
        self._session_models_container.setSpacing(4)
        self._session_model_rows: list[ModelRow] = []
        outer.addLayout(self._session_models_container)
        outer.addSpacing(16)

        # ── Totali ──────────────────────────────────────────────
        total_label = QLabel("Totale storico")
        total_label.setStyleSheet("color: #aaa; font-size: 12px; font-weight: 600;")
        outer.addWidget(total_label)
        outer.addSpacing(4)

        row2 = QHBoxLayout()
        row2.setSpacing(12)
        self._t_input = StatCard("Input Totali")
        self._t_output = StatCard("Output Totali")
        self._t_reqs = StatCard("Richieste Totali")
        self._t_cost = StatCard("Costo Totale")
        for card in (self._t_input, self._t_output, self._t_reqs, self._t_cost):
            row2.addWidget(card)
        outer.addLayout(row2)
        outer.addSpacing(4)

        # Model breakdown totale
        self._total_models_container = QVBoxLayout()
        self._total_models_container.setSpacing(4)
        self._total_model_rows: list[ModelRow] = []
        outer.addLayout(self._total_models_container)
        outer.addSpacing(16)

        # ── Chart ───────────────────────────────────────────────
        self._chart_label = QLabel("Uso giornaliero")
        self._chart_label.setStyleSheet("color: #aaa; font-size: 12px; font-weight: 600;")
        outer.addWidget(self._chart_label)

        chart_card = GlassCard()
        self._chart = MiniBarChart()
        chart_card.body().addWidget(self._chart)
        outer.addWidget(chart_card)

        outer.addStretch()

        scroll.setWidget(container)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

        # Auto refresh
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(3000)
        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self._timer.start(5000)
        self.refresh()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()

    def _selected_provider(self) -> str:
        _map = {"Anthropic": "anthropic", "OpenAI": "openai", "Gemini": "gemini", "Ollama": "ollama"}
        return _map.get(self._provider_combo.currentText(), "ollama")

    def _update_model_rows(self, container: QVBoxLayout, rows: list, models: dict) -> list:
        """Aggiorna le righe modello in un container, riutilizzando o creando widget."""
        model_list = sorted(models.items(), key=lambda x: x[1].get("input", 0), reverse=True)

        # Rimuovi righe in eccesso
        while len(rows) > len(model_list):
            row = rows.pop()
            container.removeWidget(row)
            row.deleteLater()

        # Aggiorna o crea righe
        for i, (model, data) in enumerate(model_list):
            color = _MODEL_COLORS[i % len(_MODEL_COLORS)]
            if i < len(rows):
                row = rows[i]
            else:
                row = ModelRow(color)
                rows.append(row)
                container.addWidget(row)
            cost = _cost_from_models({model: data})
            row.update_data(model, data.get("input", 0), data.get("output", 0),
                            data.get("requests", 0), cost)

        return rows

    def _aggregate_models(self, sessions: list) -> dict:
        """Aggrega i token per modello da tutte le sessioni."""
        agg = {}
        for s in sessions:
            for model, data in s.get("models", {}).items():
                if model not in agg:
                    agg[model] = {"input": 0, "output": 0, "requests": 0}
                agg[model]["input"] += data.get("input", 0)
                agg[model]["output"] += data.get("output", 0)
                agg[model]["requests"] += data.get("requests", 0)
        return agg

    def refresh(self):
        t = self._tracker
        provider = self._selected_provider()

        # ── Sessione corrente ──
        session = t.get_session(provider)
        self._s_input.set_value(f"{session['input']:,}")
        self._s_output.set_value(f"{session['output']:,}")
        self._s_reqs.set_value(str(session.get("requests", 0)))
        self._s_cost.set_value(f"${session['cost']:.4f}")

        # Breakdown modelli sessione
        session_models = self._tracker._session.get(provider, {}).get("models", {})
        self._session_model_rows = self._update_model_rows(
            self._session_models_container, self._session_model_rows, session_models)

        # ── Totali ──
        totals = t.get_totals(provider)
        self._t_input.set_value(f"{totals['total_input']:,}")
        self._t_output.set_value(f"{totals['total_output']:,}")
        self._t_cost.set_value(f"${totals['total_cost']:.4f}")

        sessions = t.get_sessions(provider)

        # Richieste totali
        total_reqs = 0
        for s in sessions:
            for m in s.get("models", {}).values():
                total_reqs += m.get("requests", 0)
        self._t_reqs.set_value(f"{total_reqs:,}")

        # Breakdown modelli totale
        agg_models = self._aggregate_models(sessions)
        self._total_model_rows = self._update_model_rows(
            self._total_models_container, self._total_model_rows, agg_models)

        # ── Chart ──
        mode = self._chart_mode.currentText()
        if mode == "Richieste":
            chart_data = []
            for s in sessions:
                reqs = sum(m.get("requests", 0) for m in s.get("models", {}).values())
                chart_data.append((s["date"], reqs))
            self._chart_label.setText("Uso giornaliero (richieste)")
        elif mode == "Costo":
            chart_data = []
            for s in sessions:
                cost = _cost_from_models(s.get("models", {}))
                chart_data.append((s["date"], cost))
            self._chart_label.setText("Uso giornaliero (costo $)")
        else:  # Token
            chart_data = []
            for s in sessions:
                tokens = sum(m.get("input", 0) + m.get("output", 0)
                             for m in s.get("models", {}).values())
                chart_data.append((s["date"], tokens))
            self._chart_label.setText("Uso giornaliero (token)")
        self._chart.set_data(chart_data)

