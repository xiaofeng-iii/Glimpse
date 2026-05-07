"""
CaptureManager 单元测试

测试核心模块 core/capture.py
覆盖: CaptureResult, CaptureManager 初始化/截图/防抖/设置
"""
import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from core.capture import CaptureResult, CaptureManager


class TestCaptureResult:
    """CaptureResult 数据类测试"""

    def test_default_values(self):
        """验证默认值"""
        result = CaptureResult(
            image_path="/tmp/test.png",
            width=1920,
            height=1080,
            timestamp=time.time(),
        )
        assert result.image_path == "/tmp/test.png"
        assert result.width == 1920
        assert result.height == 1080
        assert result.app_name is None

    def test_with_app_name(self):
        """验证 app_name 可选参数"""
        result = CaptureResult(
            image_path="/tmp/test.png",
            width=800,
            height=600,
            timestamp=time.time(),
            app_name="Chrome",
        )
        assert result.app_name == "Chrome"


class TestCaptureManagerInit:
    """CaptureManager 初始化测试"""

    @patch("core.capture.mss.mss")
    def test_init_stores_path_manager(self, mock_mss, mock_path_manager):
        """验证: __init__ 存储 path_manager 并初始化 mss"""
        mgr = CaptureManager(mock_path_manager)
        assert mgr._path_manager is mock_path_manager
        mock_mss.assert_called_once()

    @patch("core.capture.mss.mss")
    def test_default_settings(self, mock_mss, mock_path_manager):
        """验证: 默认防抖/集群/窗口设置"""
        mgr = CaptureManager(mock_path_manager)
        settings = mgr.get_settings()
        assert settings["debounce_interval"] == 5.0
        assert settings["cluster_threshold"] == 2.0
        assert settings["max_captures_per_window"] == 10


class TestCaptureManagerDebounce:
    """CaptureManager 防抖算法测试"""

    @patch("core.capture.mss.mss")
    def setup_method(self, mock_mss, mock_path_manager):
        self.mgr = CaptureManager(mock_path_manager)

    @patch("core.capture.mss.mss")
    def test_check_debounce_first_call_allows(self, mock_mss, mock_path_manager):
        """验证: 首次截图防抖检查通过"""
        mgr = CaptureManager(mock_path_manager)
        assert mgr._check_debounce(is_fullscreen=True) is True
        assert mgr._check_debounce(is_fullscreen=False) is True

    @patch("core.capture.mss.mss")
    def test_check_debounce_within_interval_blocks(self, mock_mss, mock_path_manager):
        """验证: 防抖间隔内第二次截图被阻止"""
        mgr = CaptureManager(mock_path_manager)
        mgr._fullscreen_debounce_time = time.time()
        assert mgr._check_debounce(is_fullscreen=True) is False

    @patch("core.capture.mss.mss")
    def test_check_debounce_after_interval_allows(self, mock_mss, mock_path_manager):
        """验证: 超过防抖间隔后截图通过"""
        mgr = CaptureManager(mock_path_manager)
        mgr._fullscreen_debounce_time = time.time() - 10.0  # 10 秒前
        assert mgr._check_debounce(is_fullscreen=True) is True

    @patch("core.capture.mss.mss")
    def test_fullscreen_and_region_independent_debounce(self, mock_mss, mock_path_manager):
        """验证: 全屏和区域截图有独立的防抖计时器"""
        mgr = CaptureManager(mock_path_manager)
        mgr._fullscreen_debounce_time = time.time()  # 刚截过全屏
        # 区域截图应该不受影响
        assert mgr._check_debounce(is_fullscreen=False) is True


class TestCaptureManagerClusterDetection:
    """CaptureManager 集群防抖测试"""

    @patch("core.capture.mss.mss")
    def test_is_clustered_first_region_allows(self, mock_mss, mock_path_manager):
        """验证: 首个区域截图不触发集群判定"""
        mgr = CaptureManager(mock_path_manager)
        assert mgr._is_clustered_region((0, 0, 100, 100)) is False

    @patch("core.capture.mss.mss")
    def test_is_clustered_same_region_blocks(self, mock_mss, mock_path_manager):
        """验证: 相同区域快速连续截图被阻止"""
        mgr = CaptureManager(mock_path_manager)
        mgr._last_region = (0, 0, 100, 100)
        mgr._last_capture_time = time.time()
        assert mgr._is_clustered_region((0, 0, 100, 100)) is True

    @patch("core.capture.mss.mss")
    def test_is_clustered_different_region_allows(self, mock_mss, mock_path_manager):
        """验证: 不同区域截图不触发集群判定"""
        mgr = CaptureManager(mock_path_manager)
        mgr._last_region = (0, 0, 100, 100)
        mgr._last_capture_time = time.time()
        assert mgr._is_clustered_region((500, 500, 100, 100)) is False

    @patch("core.capture.mss.mss")
    def test_is_clustered_timeout_allows(self, mock_mss, mock_path_manager):
        """验证: 超过集群阈值后允许截图"""
        mgr = CaptureManager(mock_path_manager)
        mgr._last_region = (0, 0, 100, 100)
        mgr._last_capture_time = time.time() - 5.0  # 超过 cluster_threshold=2.0
        assert mgr._is_clustered_region((0, 0, 100, 100)) is False


class TestCaptureManagerForceSplit:
    """CaptureManager 窗口截图数限制测试"""

    @patch("core.capture.mss.mss")
    def test_force_split_under_limit(self, mock_mss, mock_path_manager):
        """验证: 窗口内截图数未超限不触发强制分片"""
        mgr = CaptureManager(mock_path_manager)
        mgr._fullscreen_count = 5
        mgr._region_count = 4  # total=9 < max(10)
        assert mgr._check_force_split() is False

    @patch("core.capture.mss.mss")
    def test_force_split_at_limit(self, mock_mss, mock_path_manager):
        """验证: 窗口内截图数达到上限触发强制分片"""
        mgr = CaptureManager(mock_path_manager)
        mgr._capture_window_start = time.time()  # 保持在当前窗口内
        mgr._fullscreen_count = 5
        mgr._region_count = 5  # total=10 >= max(10)
        assert mgr._check_force_split() is True

    @patch("core.capture.mss.mss")
    def test_force_split_window_reset(self, mock_mss, mock_path_manager):
        """验证: 防抖间隔过后窗口计数器重置"""
        mgr = CaptureManager(mock_path_manager)
        mgr._capture_window_start = time.time() - 10.0  # 超过 debounce_interval
        mgr._fullscreen_count = 100
        mgr._region_count = 100
        assert mgr._check_force_split() is False  # 窗口重置


class TestCaptureManagerSettings:
    """CaptureManager 设置管理测试"""

    @patch("core.capture.mss.mss")
    def test_set_debounce_interval_valid(self, mock_mss, mock_path_manager):
        """验证: set_debounce_interval 接受有效值"""
        mgr = CaptureManager(mock_path_manager)
        assert mgr.set_debounce_interval(3.0) is True
        assert mgr._debounce_interval == 3.0

    @patch("core.capture.mss.mss")
    def test_set_debounce_interval_invalid(self, mock_mss, mock_path_manager):
        """验证: set_debounce_interval 拒绝无效值"""
        mgr = CaptureManager(mock_path_manager)
        assert mgr.set_debounce_interval("invalid") is False
        assert mgr._debounce_interval == 5.0  # 保持默认

    @patch("core.capture.mss.mss")
    def test_set_cluster_threshold(self, mock_mss, mock_path_manager):
        """验证: set_cluster_threshold"""
        mgr = CaptureManager(mock_path_manager)
        assert mgr.set_cluster_threshold(3.5) is True
        assert mgr._cluster_threshold == 3.5

    @patch("core.capture.mss.mss")
    def test_set_max_captures_per_window(self, mock_mss, mock_path_manager):
        """验证: set_max_captures_per_window"""
        mgr = CaptureManager(mock_path_manager)
        assert mgr.set_max_captures_per_window(20) is True
        assert mgr._max_captures_per_window == 20

    @patch("core.capture.mss.mss")
    def test_update_settings_partial(self, mock_mss, mock_path_manager):
        """验证: update_settings 部分更新"""
        mgr = CaptureManager(mock_path_manager)
        result = mgr.update_settings({"debounce_interval": 10.0})
        assert result is True
        settings = mgr.get_settings()
        assert settings["debounce_interval"] == 10.0
        assert settings["cluster_threshold"] == 2.0  # 未改变
        assert settings["max_captures_per_window"] == 10  # 未改变

    @patch("core.capture.mss.mss")
    def test_update_settings_invalid_rollback(self, mock_mss, mock_path_manager):
        """验证: update_settings 无效值时回滚"""
        mgr = CaptureManager(mock_path_manager)
        original = mgr.get_settings()
        result = mgr.update_settings({"debounce_interval": -1.0})
        assert result is False
        assert mgr.get_settings() == original

    @patch("core.capture.mss.mss")
    def test_update_settings_all(self, mock_mss, mock_path_manager):
        """验证: update_settings 全部更新"""
        mgr = CaptureManager(mock_path_manager)
        result = mgr.update_settings({
            "debounce_interval": 8.0,
            "cluster_threshold": 3.0,
            "max_captures_per_window": 15,
        })
        assert result is True
        settings = mgr.get_settings()
        assert settings["debounce_interval"] == 8.0
        assert settings["cluster_threshold"] == 3.0
        assert settings["max_captures_per_window"] == 15


class TestCaptureManagerClose:
    """CaptureManager.close 测试"""

    @patch("core.capture.mss.mss")
    def test_close_calls_sct_close(self, mock_mss, mock_path_manager):
        """验证: close() 调用 mss.close()"""
        mock_mss_instance = mock_mss.return_value
        mgr = CaptureManager(mock_path_manager)
        mgr.close()
        mock_mss_instance.close.assert_called_once()


class TestCaptureManagerGlobal:
    """capture_manager 全局实例测试"""

    def test_capture_manager_global_is_none(self):
        """验证: 全局 capture_manager 初始为 None"""
        from core.capture import capture_manager
        assert capture_manager is None
