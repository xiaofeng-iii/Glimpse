"""
LoadingSpinner - animated loading overlay with spinner and status text.
Inspired by Floral Notepaper's animation patterns (shimmer, fade-up).
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGraphicsOpacityEffect
from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QRectF, Property, Signal,
)
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath

from ui.locale_manager import t


class _SpinnerWheel(QWidget):
    """A rotating arc spinner drawn entirely with QPainter (no external assets)."""

    _angle = 0.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 36)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._anim = QPropertyAnimation(self, b"_angle")
        self._anim.setDuration(1000)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(360.0)
        self._anim.setLoopCount(-1)

    def get_angle(self) -> float:
        return self._angle

    def set_angle(self, value: float):
        self._angle = value
        self.update()

    angle = Property(float, get_angle, set_angle)

    def start(self):
        self._anim.start()

    def stop(self):
        self._anim.stop()

    def _tick(self):
        pass

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Track arc (faint)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#E2E8F0"))
        painter.drawEllipse(2, 2, 32, 32)

        # Spinning arc
        pen = QPen(QColor("#6366F1"), 3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        rect = QRectF(4, 4, 28, 28)
        span_angle = int(90 + 60 * abs((self._angle % 180 - 90) / 90))
        painter.drawArc(rect, int(-self._angle * 16), int(span_angle * 16))

        # Center dot
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#6366F1"))
        painter.drawEllipse(14, 14, 8, 8)

        painter.end()


class LoadingSpinner(QWidget):
    """Semi-transparent overlay with a spinner and status message."""

    shown = Signal()
    hidden = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        # Semi-transparent background
        self.setStyleSheet("background-color: rgba(248, 249, 250, 0.75);")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        self._spinner = _SpinnerWheel()
        layout.addWidget(self._spinner, 0, Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel(t("status.loading"))
        self._label.setObjectName("subtitle")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont("Segoe UI", 13)
        self._label.setFont(font)
        layout.addWidget(self._label)

        self._cancel_btn = None

    def set_cancel_callback(self, callback, label: str = ""):
        """Add an optional cancel button."""
        if self._cancel_btn is None:
            from PySide6.QtWidgets import QPushButton
            self._cancel_btn = QPushButton(label or t("status.cancel"))
            self._cancel_btn.setObjectName("ghostBtn")
            self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._cancel_btn.clicked.connect(callback)
            self.layout().addWidget(self._cancel_btn, 0, Qt.AlignmentFlag.AlignCenter)

    def set_text(self, text: str):
        """Update the status message."""
        self._label.setText(text)

    def show(self):
        """Fade in the overlay."""
        self.setGeometry(self.parent().rect())
        self._spinner.start()
        self.setVisible(True)
        self.raise_()
        self.shown.emit()

    def hide(self):
        """Fade out and stop spinner."""
        self._spinner.stop()
        self.setVisible(False)
        self.hidden.emit()

    def resizeEvent(self, event):
        """Track parent size."""
        if self.parent():
            self.setGeometry(self.parent().rect())
        super().resizeEvent(event)
