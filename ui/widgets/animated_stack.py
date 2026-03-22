"""QStackedWidget with fade transition between pages."""

from PySide6.QtCore import (
    QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, Qt,
)
from PySide6.QtWidgets import QStackedWidget, QGraphicsOpacityEffect


_DURATION = 150  # ms


class AnimatedStack(QStackedWidget):
    """Drop-in replacement for QStackedWidget with a crossfade effect."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._animating = False

    def setCurrentIndex(self, index: int):
        if index == self.currentIndex() or self._animating:
            return

        old_widget = self.currentWidget()
        new_widget = self.widget(index)
        if old_widget is None or new_widget is None:
            super().setCurrentIndex(index)
            return

        self._animating = True

        # Setup opacity effects
        old_effect = QGraphicsOpacityEffect(old_widget)
        old_widget.setGraphicsEffect(old_effect)

        new_effect = QGraphicsOpacityEffect(new_widget)
        new_widget.setGraphicsEffect(new_effect)
        new_effect.setOpacity(0.0)

        # Show the new widget on top
        super().setCurrentIndex(index)

        # Animate: old fades out, new fades in
        fade_out = QPropertyAnimation(old_effect, b"opacity", self)
        fade_out.setDuration(_DURATION)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.OutCubic)

        fade_in = QPropertyAnimation(new_effect, b"opacity", self)
        fade_in.setDuration(_DURATION)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.InCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(fade_out)
        group.addAnimation(fade_in)

        def _cleanup():
            # Remove effects to avoid rendering overhead after animation
            old_widget.setGraphicsEffect(None)
            new_widget.setGraphicsEffect(None)
            self._animating = False

        group.finished.connect(_cleanup)
        group.start()
