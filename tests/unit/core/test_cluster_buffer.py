"""
Asyncio-backed cluster buffer unit tests.
"""
import time
from unittest.mock import MagicMock

import pytest

from core.cluster_buffer import ClusterBuffer


def wait_until(predicate, timeout=3.0, interval=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(interval)
    assert predicate()


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
    yield buffer
    buffer.close()


class TestClusterBuffer:
    """测试 ClusterBuffer 核心功能"""

    def test_initial_state(self, cluster_buffer):
        assert not cluster_buffer.is_collecting()
        assert cluster_buffer.get_count() == 0
        assert cluster_buffer.get_images() == []
        assert cluster_buffer.get_remaining_seconds() == 0

    def test_add_first_image(self, cluster_buffer):
        states = []
        cluster_buffer.state_changed.connect(lambda s, c, m: states.append((s, c, m)))

        first = cluster_buffer.add_image("/path/to/img1.png")

        assert first is True
        assert cluster_buffer.is_collecting()
        assert cluster_buffer.get_count() == 1
        assert ("COLLECTING", 1, 3) in states

    def test_add_subsequent_images(self, cluster_buffer):
        cluster_buffer.add_image("/path/to/img1.png")
        states = []
        cluster_buffer.state_changed.connect(lambda s, c, m: states.append((s, c, m)))

        first = cluster_buffer.add_image("/path/to/img2.png")

        assert first is False
        assert cluster_buffer.get_count() == 2
        assert ("COLLECTING", 2, 3) in states

    def test_auto_flush_on_max_images(self, cluster_buffer):
        flushed_images = []
        cluster_buffer.flushed.connect(lambda imgs: flushed_images.append(imgs))

        cluster_buffer.add_image("img1.png")
        cluster_buffer.add_image("img2.png")
        cluster_buffer.add_image("img3.png")

        assert len(flushed_images) == 1
        assert flushed_images[0] == ["img1.png", "img2.png", "img3.png"]
        assert not cluster_buffer.is_collecting()

    def test_manual_flush(self, cluster_buffer):
        flushed_images = []
        cluster_buffer.flushed.connect(lambda imgs: flushed_images.append(imgs))

        cluster_buffer.add_image("img1.png")
        cluster_buffer.flush()

        assert flushed_images[0] == ["img1.png"]
        assert not cluster_buffer.is_collecting()

    def test_discard(self, cluster_buffer):
        discarded = []
        cluster_buffer.discarded.connect(lambda: discarded.append(True))

        cluster_buffer.add_image("img1.png")
        cluster_buffer.discard()

        assert discarded == [True]
        assert not cluster_buffer.is_collecting()
        assert cluster_buffer.get_count() == 0

    def test_auto_flush_on_timeout(self, cluster_buffer):
        flushed_images = []
        cluster_buffer.flushed.connect(lambda imgs: flushed_images.append(imgs))

        cluster_buffer.add_image("img1.png")
        wait_until(lambda: len(flushed_images) > 0, timeout=4.0)

        assert flushed_images[0] == ["img1.png"]
        assert not cluster_buffer.is_collecting()

    def test_timeout_no_auto_submit(self):
        sm = MagicMock()
        sm.get = lambda key, default=None: {
            "cluster.cluster_auto_submit": False,
            "cluster.cluster_max_images": 3,
            "cluster.cluster_timeout": 1,
        }.get(key, default)

        buffer = ClusterBuffer(sm)
        try:
            flushed = []
            discarded = []
            buffer.flushed.connect(lambda imgs: flushed.append(imgs))
            buffer.discarded.connect(lambda: discarded.append(True))

            buffer.add_image("img1.png")
            wait_until(lambda: not buffer.has_active_timer(), timeout=2.0)

            assert len(flushed) == 0
            assert len(discarded) == 0
            assert buffer.is_collecting()
            assert buffer.get_remaining_seconds() == 0
        finally:
            buffer.close()

    def test_countdown_signal(self, cluster_buffer):
        countdowns = []
        cluster_buffer.countdown_changed.connect(lambda s: countdowns.append(s))

        cluster_buffer.add_image("img1.png")
        wait_until(lambda: len(countdowns) >= 2, timeout=2.0)

        assert countdowns[0] == 2
        assert countdowns[1] == 1

    def test_exceed_max_images_starts_new_cluster(self, cluster_buffer):
        flushed_images = []
        cluster_buffer.flushed.connect(lambda imgs: flushed_images.append(imgs))

        cluster_buffer.add_image("img1.png")
        cluster_buffer.add_image("img2.png")
        cluster_buffer.add_image("img3.png")

        assert flushed_images[0] == ["img1.png", "img2.png", "img3.png"]

        cluster_buffer.add_image("img4.png")
        assert cluster_buffer.get_count() == 1
        assert cluster_buffer.get_images() == ["img4.png"]
