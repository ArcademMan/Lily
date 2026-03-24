"""Floating overlay: small Lily logo in bottom-right when window is hidden."""

import os

from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, Property, QRectF, QPoint,
)
from PySide6.QtGui import QPainter, QColor, QPen, QPixmap, QPainterPath, QFont
from PySide6.QtWidgets import QWidget, QApplication

_ACCENT = QColor("#7C5CFC")
_SIZE = 64
_MARGIN = 20


class LilyOverlay(QWidget):
    """Tiny always-on-top overlay with animated state feedback."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self._state = "idle"
        self._countdown = -1
        self._window_visible = True
        self._window_foreground = True
        self._on_relevant_page = True

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(_SIZE, _SIZE)

        # load circular icon
        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "assets", "lily.png",
        )
        self._icon = self._make_circle_icon(icon_path, 44)

        # animatable properties
        self._pulse = 0.0
        self._arc_angle = 0.0
        self._glow = 0.0

        # pulse animation (listening)
        self._pulse_anim = QPropertyAnimation(self, b"pulse", self)
        self._pulse_anim.setDuration(1200)
        self._pulse_anim.setStartValue(0.0)
        self._pulse_anim.setEndValue(1.0)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulse_anim.setLoopCount(-1)

        # arc animation (processing / loading)
        self._arc_anim = QPropertyAnimation(self, b"arc_angle", self)
        self._arc_anim.setDuration(1200)
        self._arc_anim.setStartValue(0.0)
        self._arc_anim.setEndValue(360.0)
        self._arc_anim.setLoopCount(-1)

        # glow animation (dictation / confirming)
        self._glow_anim = QPropertyAnimation(self, b"glow", self)
        self._glow_anim.setDuration(1800)
        self._glow_anim.setStartValue(0.0)
        self._glow_anim.setEndValue(1.0)
        self._glow_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._glow_anim.setLoopCount(-1)

        # repaint timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)

    @staticmethod
    def _make_circle_icon(path: str, size: int) -> QPixmap:
        src = QPixmap(path).scaled(
            size, size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        if src.width() != size or src.height() != size:
            x = (src.width() - size) // 2
            y = (src.height() - size) // 2
            src = src.copy(x, y, size, size)

        result = QPixmap(size, size)
        result.fill(Qt.GlobalColor.transparent)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addEllipse(0, 0, size, size)
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, src)
        painter.end()
        return result

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

    def _get_glow(self):
        return self._glow

    def _set_glow(self, v):
        self._glow = v

    glow = Property(float, _get_glow, _set_glow)

    # ── visibility logic ──────────────────────────────────────────
    def set_window_visible(self, visible: bool):
        self._window_visible = visible
        self._update_visibility()

    def set_window_foreground(self, foreground: bool):
        self._window_foreground = foreground
        self._update_visibility()

    def set_on_relevant_page(self, relevant: bool):
        self._on_relevant_page = relevant
        self._update_visibility()

    def set_countdown(self, seconds: int):
        self._countdown = seconds
        self.update()

    def set_state(self, state: str):
        if state == self._state:
            return
        self._state = state
        self._countdown = -1
        self._pulse_anim.stop()
        self._arc_anim.stop()
        self._glow_anim.stop()
        self._pulse = 0.0
        self._arc_angle = 0.0
        self._glow = 0.0

        if state == "listening":
            self._pulse_anim.start()
        elif state in ("processing", "loading", "transcribing"):
            self._arc_anim.start()
        elif state in ("dictation", "confirming"):
            self._glow_anim.start()

        self._update_visibility()

    def _update_visibility(self):
        window_accessible = (
            self._window_visible
            and self._window_foreground
            and self._on_relevant_page
        )
        should_show = (
            self._config.overlay_enabled
            and not window_accessible
            and self._state != "idle"
        )
        if should_show and not self.isVisible():
            self._position_bottom_right()
            self.show()
            self._timer.start(16)
        elif not should_show and self.isVisible():
            self.hide()
            self._timer.stop()

    def _position_bottom_right(self):
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.right() - _SIZE - _MARGIN
            y = geo.bottom() - _SIZE - _MARGIN
            self.move(x, y)

    # ── painting ──────────────────────────────────────────────────
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = _SIZE / 2, _SIZE / 2
        r = _SIZE / 2
        show_cd = self._countdown >= 0 and self._state == "dictation"

        # dark circle background
        p.setBrush(QColor(25, 25, 35, 220))
        p.setPen(QPen(QColor(124, 92, 252, 80), 2))
        p.drawEllipse(QRectF(2, 2, _SIZE - 4, _SIZE - 4))

        # listening: expanding rings
        if self._state == "listening":
            for i in range(2):
                offset = (self._pulse + i * 0.5) % 1.0
                ring_r = r - 2 + offset * 12
                alpha = int(140 * (1.0 - offset))
                ring_pen = QPen(QColor(124, 92, 252, alpha), 2)
                p.setPen(ring_pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2))

        # processing / loading: rotating arc (purple)
        elif self._state in ("processing", "loading"):
            arc_pen = QPen(_ACCENT, 3)
            arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(arc_pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            arc_r = r - 1
            rect = QRectF(cx - arc_r, cy - arc_r, arc_r * 2, arc_r * 2)
            start = int(self._arc_angle * 16)
            p.drawArc(rect, start, 90 * 16)

        # transcribing: rotating arc (cyan) — distinct from dictation glow
        elif self._state == "transcribing":
            arc_pen = QPen(QColor(80, 200, 220), 3)
            arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(arc_pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            arc_r = r - 1
            rect = QRectF(cx - arc_r, cy - arc_r, arc_r * 2, arc_r * 2)
            start = int(self._arc_angle * 16)
            p.drawArc(rect, start, 90 * 16)

        # dictation: breathing glow ring
        elif self._state == "dictation":
            t = self._glow
            brightness = 1.0 - abs(t * 2.0 - 1.0)
            alpha = int(40 + 120 * brightness)
            width = 1.5 + 1.5 * brightness
            p.setPen(QPen(QColor(100, 220, 160, alpha), width))
            p.setBrush(Qt.BrushStyle.NoBrush)
            glow_r = r - 1
            p.drawEllipse(QRectF(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2))

        # confirming: blinking amber ring
        elif self._state == "confirming":
            t = self._glow
            brightness = 1.0 - abs(t * 2.0 - 1.0)
            alpha = int(50 + 160 * brightness)
            width = 1.5 + 1.5 * brightness
            p.setPen(QPen(QColor(255, 180, 50, alpha), width))
            p.setBrush(Qt.BrushStyle.NoBrush)
            glow_r = r - 1
            p.drawEllipse(QRectF(cx - glow_r, cy - glow_r, glow_r * 2, glow_r * 2))

        # icon (hidden when countdown is shown, replaced by the number)
        if show_cd:
            # semi-transparent scrim over icon area
            p.setBrush(QColor(25, 25, 35, 180))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(6, 6, _SIZE - 12, _SIZE - 12))
            # countdown number
            font = QFont("Segoe UI", 18, QFont.Weight.Bold)
            p.setFont(font)
            p.setPen(QColor(100, 220, 160))
            p.drawText(QRectF(0, 0, _SIZE, _SIZE),
                       Qt.AlignmentFlag.AlignCenter, str(self._countdown))
        else:
            ix = int(cx - self._icon.width() / 2)
            iy = int(cy - self._icon.height() / 2)
            p.drawPixmap(ix, iy, self._icon)

        p.end()
