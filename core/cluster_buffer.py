"""
Cluster Buffer - 集群截图缓冲区
管理多张截图的收集、超时自动提交、手动提交/取消
"""
import json
from typing import List, Callable, Optional
from PySide6.QtCore import QObject, Signal, QTimer


class ClusterBuffer(QObject):
    """集群截图缓冲区 - Qt信号驱动状态机"""

    flushed = Signal(list)           # 提交时发射: [image_path, ...]
    discarded = Signal()             # 取消时发射
    state_changed = Signal(str, int, int)  # state, count, max_count
    countdown_changed = Signal(int)  # 剩余秒数

    def __init__(self, settings_manager):
        super().__init__()
        self._settings_manager = settings_manager
        self._images: List[str] = []
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        self._countdown_timer = QTimer()
        self._countdown_timer.timeout.connect(self._on_countdown_tick)
        self._remaining_seconds = 0

    def is_collecting(self) -> bool:
        return len(self._images) > 0

    def add_image(self, image_path: str) -> bool:
        """添加截图到集群缓冲区

        Returns:
            True 表示已启动收集（第一张图）
            False 表示已加入现有集群
        """
        max_images = self._settings_manager.get("cluster.cluster_max_images", 5)
        timeout = self._settings_manager.get("cluster.cluster_timeout", 5)

        first_image = len(self._images) == 0
        self._images.append(image_path)
        self.state_changed.emit("COLLECTING", len(self._images), max_images)

        # 重置倒计时
        self._timer.stop()
        self._timer.start(timeout * 1000)
        self._remaining_seconds = timeout
        self._countdown_timer.start(1000)
        self.countdown_changed.emit(self._remaining_seconds)

        # 检查是否达到上限
        if len(self._images) >= max_images:
            self.flush()
            return first_image

        return first_image

    def flush(self):
        """手动提交当前集群"""
        if not self._images:
            return
        images = self._images.copy()
        self._clear()
        self.flushed.emit(images)

    def discard(self):
        """取消当前集群"""
        if not self._images:
            return
        self._clear()
        self.discarded.emit()

    def _on_timeout(self):
        auto_submit = self._settings_manager.get("cluster.cluster_auto_submit", True)
        if auto_submit and self._images:
            self.flush()
        else:
            # 手动模式下超时不自动提交，只停止倒计时
            self._countdown_timer.stop()

    def _on_countdown_tick(self):
        self._remaining_seconds -= 1
        self.countdown_changed.emit(self._remaining_seconds)
        if self._remaining_seconds <= 0:
            self._countdown_timer.stop()

    def _clear(self):
        self._timer.stop()
        self._countdown_timer.stop()
        self._images.clear()
        self._remaining_seconds = 0
        self.state_changed.emit("IDLE", 0, self._settings_manager.get("cluster.cluster_max_images", 5))

    def get_images(self) -> List[str]:
        return self._images.copy()

    def get_count(self) -> int:
        return len(self._images)
