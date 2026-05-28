"""
UI Signals - pure Python global event bus.
"""
import threading

from event_bus import EventSignal


class UISignals:
    """Global signal bus exposed with a Qt-like API."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.screenshot_requested = EventSignal("screenshot_requested")
        self.screenshot_completed = EventSignal("screenshot_completed")
        self.memory_saved = EventSignal("memory_saved")
        self.memory_deleted = EventSignal("memory_deleted")
        self.search_requested = EventSignal("search_requested")
        self.search_completed = EventSignal("search_completed")
        self.error_occurred = EventSignal("error_occurred")
        self.status_updated = EventSignal("status_updated")
        self.progress_updated = EventSignal("progress_updated")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance


signals = UISignals.get_instance()

__all__ = ["UISignals", "signals"]
