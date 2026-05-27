"""
集群截图缓冲区单元测试
"""
import pytest
from unittest.mock import MagicMock
from PySide6.QtCore import QTimer

from core.cluster_buffer import ClusterBuffer


@pytest.fixture
def mock_settings_manager():
    """模拟 SettingsManager"""
    settings = {
        "cluster.cluster_mode": True,
        "cluster.cluster_auto_submit": True,
        "cluster.cluster_max_images": 3,
        "cluster.cluster_timeout": 2,
    }
    sm = MagicMock()
    sm.get = lambda key, default=None: settings.get(key, default)
    return sm


@pytest.fixture
def cluster_buffer(mock_settings_manager):
    """创建 ClusterBuffer 实例"""
    buffer = ClusterBuffer(mock_settings_manager)
    return buffer


class TestClusterBuffer:
    """测试 ClusterBuffer 核心功能"""

    def test_initial_state(self, cluster_buffer):
        """初始状态应为空闲"""
        assert not cluster_buffer.is_collecting()
        assert cluster_buffer.get_count() == 0
        assert cluster_buffer.get_images() == []

    def test_add_first_image(self, cluster_buffer, qtbot):
        """添加第一张图应进入收集状态"""
        states = []
        cluster_buffer.state_changed.connect(lambda s, c, m: states.append((s, c, m)))

        first = cluster_buffer.add_image("/path/to/img1.png")

        assert first is True
        assert cluster_buffer.is_collecting()
        assert cluster_buffer.get_count() == 1
        assert ("COLLECTING", 1, 3) in states

    def test_add_subsequent_images(self, cluster_buffer, qtbot):
        """添加后续图片应增加计数"""
        cluster_buffer.add_image("/path/to/img1.png")
        states = []
        cluster_buffer.state_changed.connect(lambda s, c, m: states.append((s, c, m)))

        first = cluster_buffer.add_image("/path/to/img2.png")

        assert first is False
        assert cluster_buffer.get_count() == 2
        assert ("COLLECTING", 2, 3) in states

    def test_auto_flush_on_max_images(self, cluster_buffer, qtbot):
        """达到最大图片数应自动触发 flush"""
        flushed_images = []
        cluster_buffer.flushed.connect(lambda imgs: flushed_images.append(imgs))

        cluster_buffer.add_image("img1.png")
        cluster_buffer.add_image("img2.png")
        cluster_buffer.add_image("img3.png")

        qtbot.waitUntil(lambda: len(flushed_images) > 0, timeout=1000)

        assert len(flushed_images) == 1
        assert flushed_images[0] == ["img1.png", "img2.png", "img3.png"]
        assert not cluster_buffer.is_collecting()

    def test_manual_flush(self, cluster_buffer, qtbot):
        """手动 flush 应发射 flushed 信号"""
        flushed_images = []
        cluster_buffer.flushed.connect(lambda imgs: flushed_images.append(imgs))

        cluster_buffer.add_image("img1.png")
        cluster_buffer.flush()

        qtbot.waitUntil(lambda: len(flushed_images) > 0, timeout=500)

        assert flushed_images[0] == ["img1.png"]
        assert not cluster_buffer.is_collecting()

    def test_discard(self, cluster_buffer, qtbot):
        """discard 应发射 discarded 信号并清空缓冲区"""
        discarded = []
        cluster_buffer.discarded.connect(lambda: discarded.append(True))

        cluster_buffer.add_image("img1.png")
        cluster_buffer.discard()

        qtbot.waitUntil(lambda: len(discarded) > 0, timeout=500)

        assert not cluster_buffer.is_collecting()
        assert cluster_buffer.get_count() == 0

    def test_auto_flush_on_timeout(self, cluster_buffer, qtbot):
        """超时后应自动触发 flush（当 auto_submit 为 True）"""
        flushed_images = []
        cluster_buffer.flushed.connect(lambda imgs: flushed_images.append(imgs))

        cluster_buffer.add_image("img1.png")

        # 等待超时（2秒）
        qtbot.waitUntil(lambda: len(flushed_images) > 0, timeout=4000)

        assert flushed_images[0] == ["img1.png"]
        assert not cluster_buffer.is_collecting()

    def test_timeout_no_auto_submit(self, qtbot):
        """auto_submit 为 False 时超时不应 flush"""
        sm = MagicMock()
        sm.get = lambda key, default=None: {
            "cluster.cluster_auto_submit": False,
            "cluster.cluster_max_images": 3,
            "cluster.cluster_timeout": 1,
        }.get(key, default)

        buffer = ClusterBuffer(sm)

        flushed = []
        discarded = []
        buffer.flushed.connect(lambda imgs: flushed.append(imgs))
        buffer.discarded.connect(lambda: discarded.append(True))

        buffer.add_image("img1.png")

        # 等待超过超时时间
        qtbot.wait(2000)

        # 不应 flush 也不应 discard
        assert len(flushed) == 0
        assert len(discarded) == 0
        # 但倒计时应该停止了
        assert not buffer._countdown_timer.isActive()

    def test_countdown_signal(self, cluster_buffer, qtbot):
        """倒计时信号应正确发射"""
        countdowns = []
        cluster_buffer.countdown_changed.connect(lambda s: countdowns.append(s))

        cluster_buffer.add_image("img1.png")

        # 等待至少两个 countdown 信号（初始值 + tick）
        qtbot.waitUntil(lambda: len(countdowns) >= 2, timeout=1500)

        assert len(countdowns) >= 2
        assert countdowns[0] == 2  # 初始值
        assert countdowns[1] == 1  # 第一次 tick

    def test_exceed_max_images_splits(self, cluster_buffer, qtbot):
        """超过最大图片数应自动 flush 后继续收集"""
        flushed_images = []
        cluster_buffer.flushed.connect(lambda imgs: flushed_images.append(imgs))

        cluster_buffer.add_image("img1.png")
        cluster_buffer.add_image("img2.png")
        cluster_buffer.add_image("img3.png")  # 触发 flush

        qtbot.waitUntil(lambda: len(flushed_images) > 0, timeout=1000)
        assert flushed_images[0] == ["img1.png", "img2.png", "img3.png"]

        # 继续添加应开始新集群
        cluster_buffer.add_image("img4.png")
        assert cluster_buffer.get_count() == 1
        assert cluster_buffer.get_images() == ["img4.png"]
