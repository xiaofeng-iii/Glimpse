"""
UI Signals - 跨线程通信的全局信号总线
"""
from PySide6.QtCore import QObject, Signal


class UISignals(QObject):
    """全局信号总线 - 单例模式"""

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    screenshot_requested = Signal()
    screenshot_completed = Signal(str)
    memory_saved = Signal(str)
    memory_deleted = Signal(str)
    search_requested = Signal(str)
    search_completed = Signal(list)
    error_occurred = Signal(str)
    status_updated = Signal(str)
    progress_updated = Signal(int, str)


signals = UISignals.get_instance()
