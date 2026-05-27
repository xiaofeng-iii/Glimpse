"""
Animated segmented control for search source filtering.
"""
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Signal, Qt
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QPushButton, QWidget


class SegmentedFilterControl(QWidget):
    """Three-option source filter with a sliding selection indicator."""

    source_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("slidingButtonGroup")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(self.sizePolicy().Policy.Fixed, self.sizePolicy().Policy.Fixed)

        self._sources = ("all", "ocr", "semantic")
        self._buttons: dict[str, QPushButton] = {}
        self._active_source = "all"

        self._indicator = QFrame(self)
        self._indicator.setObjectName("segmentIndicator")
        self._indicator.lower()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)

        for source in self._sources:
            button = QPushButton()
            button.setCheckable(True)
            button.setObjectName("segmentButton")
            button.clicked.connect(lambda checked=False, value=source: self.set_active_source(value))
            self._button_group.addButton(button)
            self._buttons[source] = button
            layout.addWidget(button)

        self._buttons[self._active_source].setChecked(True)

        self._animation = QPropertyAnimation(self._indicator, b"geometry", self)
        self._animation.setDuration(180)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        QTimer.singleShot(0, lambda: self._move_indicator(animate=False))

    def set_labels(self, labels: dict[str, str], tooltips: dict[str, str] | None = None) -> None:
        for source, text in labels.items():
            if source in self._buttons:
                self._buttons[source].setText(text)
        if tooltips:
            for source, tooltip in tooltips.items():
                if source in self._buttons:
                    self._buttons[source].setToolTip(tooltip)
        QTimer.singleShot(0, lambda: self._move_indicator(animate=False))

    def set_active_source(self, source: str, animate: bool = True) -> None:
        if source not in self._buttons:
            source = "all"

        self._active_source = source
        self._buttons[source].setChecked(True)
        self._move_indicator(animate=animate and self.isVisible())
        self.source_selected.emit(source)

    def active_source(self) -> str:
        return self._active_source

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._move_indicator(animate=False)

    def showEvent(self, event):
        super().showEvent(event)
        self._move_indicator(animate=False)

    def _move_indicator(self, animate: bool) -> None:
        button = self._buttons.get(self._active_source)
        if button is None or button.width() <= 0:
            return

        target = button.geometry()
        if animate:
            self._animation.stop()
            self._animation.setStartValue(self._indicator.geometry())
            self._animation.setEndValue(target)
            self._animation.start()
        else:
            self._animation.stop()
            self._indicator.setGeometry(target)
        self._indicator.lower()
