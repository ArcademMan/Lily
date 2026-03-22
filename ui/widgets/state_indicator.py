"""Animated circle indicator: idle / listening / processing."""

import os
from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, Property, QRectF,
)
from PySide6.QtGui import QPainter, QColor, QRadialGradient, QPen, QPixmap
from PySide6.QtWidgets import QWidget

_ACCENT = QColor("#7C5CFC")
_ACCENT_DIM = QColor(124, 92, 252, 60)
_SIZE = 160


class StateIndicator(QWidget):
    """Custom-painted animated state indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(_SIZE, _SIZE)
        self._state = "idle"

        # animatable properties
        self._pulse = 0.0
        self._arc_angle = 0.0

        # load icon
        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "assets", "lily.png",
        )
        self._icon = QPixmap(icon_path).scaled(
            64, 64, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        # pulse animation (listening)
        self._pulse_anim = QPropertyAnimation(self, b"pulse", self)
        self._pulse_anim.setDuration(1000)
        self._pulse_anim.setStartValue(0.0)
        self._pulse_anim.setEndValue(1.0)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulse_anim.setLoopCount(-1)

        # arc animation (processing)
        self._arc_anim = QPropertyAnimation(self, b"arc_angle", self)
        self._arc_anim.setDuration(1200)
        self._arc_anim.setStartValue(0.0)
        self._arc_anim.setEndValue(360.0)
        self._arc_anim.setLoopCount(-1)

        # repaint timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(16)  # ~60 fps

    # ── Qt properties for QPropertyAnimation ──────────────────────
    def _get_pulse(self):
        return self._pulse

    def _set_pulse(self, v):
        self._pulse = v

    pulse = Property(float, _get_pulse, _set_pulse)

    def _get_arc_angle(self):
        return self._arc_angle

    def _set_arc_angle(self, v):
        self._arc_angle = v

    arc_angle = Property(float, _get_arc_angle, _set_arc_angle)

    # ── public API ────────────────────────────────────────────────
    def set_state(self, state: str):
        if state == self._state:
            return
        self._state = state
        self._pulse_anim.stop()
        self._arc_anim.stop()
        self._pulse = 0.0
        self._arc_angle = 0.0

        if state == "listening":
            self._pulse_anim.start()
        elif state in ("processing", "loading"):
            self._arc_anim.start()
        self.update()

    # ── painting ──────────────────────────────────────────────────
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = _SIZE / 2, _SIZE / 2
        r = _SIZE / 2 - 10

        # background glow
        grad = QRadialGradient(cx, cy, r)
        if self._state == "idle":
            grad.setColorAt(0, QColor(124, 92, 252, 25))
            grad.setColorAt(1, QColor(124, 92, 252, 0))
        elif self._state == "listening":
            alpha = int(25 + 40 * self._pulse)
            grad.setColorAt(0, QColor(124, 92, 252, alpha))
            grad.setColorAt(1, QColor(124, 92, 252, 0))
        else:
            grad.setColorAt(0, QColor(124, 92, 252, 35))
            grad.setColorAt(1, QColor(124, 92, 252, 0))
        p.setBrush(grad)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(10, 10, r * 2, r * 2))

        # main circle
        p.setBrush(QColor(30, 30, 45, 200))
        pen = QPen(_ACCENT_DIM, 2)
        p.setPen(pen)
        inner_r = 50
        p.drawEllipse(QRectF(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2))

        # listening: pulsing rings
        if self._state == "listening":
            for i in range(3):
                offset = (self._pulse + i * 0.33) % 1.0
                ring_r = inner_r + offset * 25
                alpha = int(120 * (1.0 - offset))
                ring_pen = QPen(QColor(124, 92, 252, alpha), 2)
                p.setPen(ring_pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2))

        # processing: rotating arc
        if self._state == "processing":
            arc_pen = QPen(_ACCENT, 3)
            arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(arc_pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            arc_r = inner_r + 10
            rect = QRectF(cx - arc_r, cy - arc_r, arc_r * 2, arc_r * 2)
            start = int(self._arc_angle * 16)
            p.drawArc(rect, start, 90 * 16)

        # icon
        ix = int(cx - self._icon.width() / 2)
        iy = int(cy - self._icon.height() / 2)
        p.drawPixmap(ix, iy, self._icon)
        p.end()
