"""
Qt bridge that safely forwards pure-Python events back to the UI thread.
"""
from typing import Optional

from PySide6.QtCore import QObject, Signal

from ui.signals import signals


class QtEventBridge(QObject):
    """Re-emits event-bus messages as Qt signals."""

    screenshot_requested = Signal()
    screenshot_completed = Signal(str)
    memory_saved = Signal(str)
    search_completed = Signal(list)
    error_occurred = Signal(str)
    status_updated = Signal(str)

    cluster_state_changed = Signal(str, int, int)
    cluster_countdown_changed = Signal(int)
    cluster_flushed = Signal(list)
    cluster_discarded = Signal()

    def __init__(self, cluster_buffer=None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._cluster_buffer = None
        self._bind_global_signals()
        if cluster_buffer is not None:
            self.bind_cluster_buffer(cluster_buffer)

    def bind_cluster_buffer(self, cluster_buffer) -> None:
        if cluster_buffer is self._cluster_buffer:
            return
        self._cluster_buffer = cluster_buffer
        cluster_buffer.state_changed.connect(self._forward_cluster_state_changed)
        cluster_buffer.countdown_changed.connect(self._forward_cluster_countdown_changed)
        cluster_buffer.flushed.connect(self._forward_cluster_flushed)
        cluster_buffer.discarded.connect(self._forward_cluster_discarded)

    def _bind_global_signals(self) -> None:
        signals.screenshot_requested.connect(self._forward_screenshot_requested)
        signals.screenshot_completed.connect(self._forward_screenshot_completed)
        signals.memory_saved.connect(self._forward_memory_saved)
        signals.search_completed.connect(self._forward_search_completed)
        signals.error_occurred.connect(self._forward_error_occurred)
        signals.status_updated.connect(self._forward_status_updated)

    def _forward_screenshot_requested(self):
        self.screenshot_requested.emit()

    def _forward_screenshot_completed(self, image_path: str):
        self.screenshot_completed.emit(image_path)

    def _forward_memory_saved(self, memory_id: str):
        self.memory_saved.emit(memory_id)

    def _forward_search_completed(self, results: list):
        self.search_completed.emit(results)

    def _forward_error_occurred(self, message: str):
        self.error_occurred.emit(message)

    def _forward_status_updated(self, status: str):
        self.status_updated.emit(status)

    def _forward_cluster_state_changed(self, state: str, count: int, max_count: int):
        self.cluster_state_changed.emit(state, count, max_count)

    def _forward_cluster_countdown_changed(self, seconds: int):
        self.cluster_countdown_changed.emit(seconds)

    def _forward_cluster_flushed(self, image_paths: list):
        self.cluster_flushed.emit(image_paths)

    def _forward_cluster_discarded(self):
        self.cluster_discarded.emit()
