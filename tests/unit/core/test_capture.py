"""
CaptureManager 单元测试

测试核心模块 core/capture.py
覆盖: CaptureResult, CaptureManager 初始化/截图/滑动窗口限流/设置
"""
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

from core.capture import CaptureResult, CaptureManager


def configure_mock_screenshot(mock_mss, width=2, height=2):
    mock_mss_instance = mock_mss.return_value.__enter__.return_value
    mock_mss_instance.monitors = [{}, {"width": width, "height": height}]

    mock_screenshot = MagicMock()
    mock_screenshot.size = (width, height)
    mock_screenshot.rgb = b"\x00" * (width * height * 3)
    mock_screenshot.width = width
    mock_screenshot.height = height
    mock_mss_instance.grab.return_value = mock_screenshot
    return mock_mss_instance


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

    def test_init_stores_path_manager(self, mock_path_manager):
        """验证: __init__ 存储 path_manager"""
        mgr = CaptureManager(mock_path_manager)
        assert mgr._path_manager is mock_path_manager

    def test_default_settings(self, mock_path_manager):
        """验证: 默认滑动窗口限流设置"""
        mgr = CaptureManager(mock_path_manager)
        settings = mgr.get_settings()
        assert settings["capture_limit_window_seconds"] == 5.0
        assert settings["max_captures_per_window"] == 10
        assert "debounce_interval" not in settings


class TestCaptureManagerSlidingWindow:
    """CaptureManager 滑动窗口限流测试"""

    @patch("core.capture.mss.mss")
    def test_consecutive_fullscreen_captures_are_allowed(self, mock_mss, mock_path_manager):
        """验证: 连续截图不会被旧防抖拦截"""
        configure_mock_screenshot(mock_mss)
        mgr = CaptureManager(mock_path_manager)

        first = mgr.capture_fullscreen()
        second = mgr.capture_fullscreen()

        assert first is not None
        assert second is not None
        assert mock_mss.return_value.__enter__.return_value.grab.call_count == 2

    def test_limit_blocks_when_recent_window_is_full(self, mock_path_manager):
        """验证: 最近窗口内达到最大截图数后限流"""
        mgr = CaptureManager(mock_path_manager)
        mgr.update_settings({
            "capture_limit_window_seconds": 5.0,
            "max_captures_per_window": 2,
        })

        with patch("core.capture.time.time", side_effect=[100.0, 101.0, 102.0]):
            assert mgr._try_reserve_capture_slot() is not None
            assert mgr._try_reserve_capture_slot() is not None
            assert mgr._try_reserve_capture_slot() is None

    def test_old_timestamps_are_pruned_after_window_moves(self, mock_path_manager):
        """验证: 时间推进后，窗口外旧时间戳被清理，新截图可通过"""
        mgr = CaptureManager(mock_path_manager)
        mgr.update_settings({
            "capture_limit_window_seconds": 5.0,
            "max_captures_per_window": 2,
        })

        with patch("core.capture.time.time", side_effect=[100.0, 101.0, 105.0]):
            assert mgr._try_reserve_capture_slot() is not None
            assert mgr._try_reserve_capture_slot() is not None
            assert mgr._try_reserve_capture_slot() is not None

        assert [record[0] for record in mgr._capture_timestamps] == [101.0, 105.0]

    @patch("core.capture.mss.mss")
    def test_capture_failure_releases_reserved_slot(self, mock_mss, mock_path_manager):
        """验证: 截图失败会释放预占限流槽"""
        mock_mss_instance = mock_mss.return_value.__enter__.return_value
        mock_mss_instance.monitors = [{}, {"width": 2, "height": 2}]
        mock_mss_instance.grab.side_effect = RuntimeError("boom")
        mgr = CaptureManager(mock_path_manager)

        with patch("core.capture.traceback.print_exc"):
            result = mgr.capture_fullscreen()

        assert result is None
        assert len(mgr._capture_timestamps) == 0

    @patch("core.capture.mss.mss")
    def test_capture_fullscreen_works_from_worker_thread(self, mock_mss, mock_path_manager):
        """验证: 在线程池中使用同一个管理器也能截图"""
        configure_mock_screenshot(mock_mss)
        mgr = CaptureManager(mock_path_manager)

        with ThreadPoolExecutor(max_workers=1) as executor:
            result = executor.submit(lambda: mgr.capture_fullscreen()).result()

        assert result is not None
        assert "screenshot_" in result.image_path


class TestCaptureManagerSettings:
    """CaptureManager 设置管理测试"""

    def test_set_capture_limit_window_seconds_valid(self, mock_path_manager):
        """验证: set_capture_limit_window_seconds 接受有效值"""
        mgr = CaptureManager(mock_path_manager)
        assert mgr.set_capture_limit_window_seconds(3.0) is True
        assert mgr.get_settings()["capture_limit_window_seconds"] == 3.0

    def test_set_capture_limit_window_seconds_invalid(self, mock_path_manager):
        """验证: set_capture_limit_window_seconds 拒绝无效值"""
        mgr = CaptureManager(mock_path_manager)
        assert mgr.set_capture_limit_window_seconds("invalid") is False
        assert mgr.get_settings()["capture_limit_window_seconds"] == 5.0

    def test_set_debounce_interval_is_compatibility_alias(self, mock_path_manager):
        """验证: set_debounce_interval 保留为旧接口兼容别名"""
        mgr = CaptureManager(mock_path_manager)
        assert mgr.set_debounce_interval(4.0) is True
        assert mgr.get_settings()["capture_limit_window_seconds"] == 4.0

    def test_set_max_captures_per_window(self, mock_path_manager):
        """验证: set_max_captures_per_window"""
        mgr = CaptureManager(mock_path_manager)
        assert mgr.set_max_captures_per_window(20) is True
        assert mgr.get_settings()["max_captures_per_window"] == 20

    def test_update_settings_partial_new_field(self, mock_path_manager):
        """验证: update_settings 部分更新新限流窗口字段"""
        mgr = CaptureManager(mock_path_manager)
        result = mgr.update_settings({"capture_limit_window_seconds": 10.0})
        assert result is True
        settings = mgr.get_settings()
        assert settings["capture_limit_window_seconds"] == 10.0
        assert settings["max_captures_per_window"] == 10

    def test_update_settings_migrates_old_debounce_field(self, mock_path_manager):
        """验证: update_settings 接收旧 debounce_interval 字段作为兼容输入"""
        mgr = CaptureManager(mock_path_manager)
        result = mgr.update_settings({"debounce_interval": 9.0})
        assert result is True
        settings = mgr.get_settings()
        assert settings["capture_limit_window_seconds"] == 9.0
        assert "debounce_interval" not in settings

    def test_update_settings_invalid_rollback(self, mock_path_manager):
        """验证: update_settings 无效值时回滚"""
        mgr = CaptureManager(mock_path_manager)
        original = mgr.get_settings()
        result = mgr.update_settings({"capture_limit_window_seconds": -1.0})
        assert result is False
        assert mgr.get_settings() == original

    def test_update_settings_all(self, mock_path_manager):
        """验证: update_settings 全部更新"""
        mgr = CaptureManager(mock_path_manager)
        result = mgr.update_settings({
            "capture_limit_window_seconds": 8.0,
            "max_captures_per_window": 15,
        })
        assert result is True
        settings = mgr.get_settings()
        assert settings["capture_limit_window_seconds"] == 8.0
        assert settings["max_captures_per_window"] == 15


class TestCaptureManagerClose:
    """CaptureManager.close 测试"""

    def test_close_is_noop(self, mock_path_manager):
        """验证: close() 在按次创建 mss 会话后保持幂等"""
        mgr = CaptureManager(mock_path_manager)
        assert mgr.close() is None


class TestCaptureManagerGlobal:
    """capture_manager 全局实例测试"""

    def test_capture_manager_global_is_none(self):
        """验证: 全局 capture_manager 初始为 None"""
        from core.capture import capture_manager
        assert capture_manager is None
