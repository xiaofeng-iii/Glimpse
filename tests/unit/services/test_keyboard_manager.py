"""
KeyboardManager 单元测试

测试服务模块 services/keyboard_manager.py
覆盖: KeyboardManager 单例, 快捷键注册/注销, 监听生命周期
"""
import pytest
from unittest.mock import MagicMock, patch, call
from threading import Thread

from services.keyboard_manager import KeyboardManager, keyboard_manager


def _create_mock_listener():
    """创建 mock GlobalHotKeys 监听器"""
    listener = MagicMock()
    listener.start.return_value = None
    listener.stop.return_value = None
    return listener


class TestKeyboardManagerSingleton:
    """KeyboardManager 单例测试"""

    def test_singleton_same_instance(self):
        """验证: 多次构造返回同一实例"""
        km1 = KeyboardManager()
        km2 = KeyboardManager()
        assert km1 is km2

    def test_global_instance(self):
        """验证: 全局 keyboard_manager 是 KeyboardManager 实例"""
        assert isinstance(keyboard_manager, KeyboardManager)


class TestKeyboardManagerHotkeyRegistration:
    """快捷键注册测试"""

    @pytest.fixture
    def manager(self):
        """提供一个干净的 KeyboardManager（清空快捷键）"""
        km = KeyboardManager()
        km.clear_hotkeys()
        return km

    def test_register_hotkey(self, manager):
        """验证: register_hotkey 注册快捷键"""
        cb = lambda: None
        manager.register_hotkey("<ctrl>+g", cb)
        hotkeys = manager.get_hotkeys()
        assert "<ctrl>+g" in hotkeys
        assert hotkeys["<ctrl>+g"] is cb

    def test_register_multiple_hotkeys(self, manager):
        """验证: 注册多个快捷键"""
        cb1 = lambda: None
        cb2 = lambda: None
        manager.register_hotkey("<ctrl>+a", cb1)
        manager.register_hotkey("<ctrl>+b", cb2)
        assert len(manager.get_hotkeys()) == 2

    def test_unregister_hotkey(self, manager):
        """验证: unregister_hotkey 注销快捷键"""
        manager.register_hotkey("<ctrl>+x", lambda: None)
        manager.unregister_hotkey("<ctrl>+x")
        assert "<ctrl>+x" not in manager.get_hotkeys()

    def test_unregister_nonexistent_is_noop(self, manager):
        """验证: 注销不存在的快捷键不抛异常"""
        manager.unregister_hotkey("nonexistent")  # 不应抛出异常

    def test_clear_hotkeys(self, manager):
        """验证: clear_hotkeys 清空所有快捷键"""
        manager.register_hotkey("<ctrl>+1", lambda: None)
        manager.register_hotkey("<ctrl>+2", lambda: None)
        manager.clear_hotkeys()
        assert manager.get_hotkeys() == {}

    def test_get_hotkeys_returns_copy(self, manager):
        """验证: get_hotkeys 返回副本，修改不会影响原数据"""
        manager.register_hotkey("<ctrl>+h", lambda: None)
        hotkeys = manager.get_hotkeys()
        hotkeys["new"] = lambda: None
        assert "new" not in manager.get_hotkeys()


class TestKeyboardManagerListening:
    """监听生命周期测试"""

    @pytest.fixture
    def manager(self):
        km = KeyboardManager()
        km.stop_listening()
        km.clear_hotkeys()
        return km

    def test_is_running_initially_false(self, manager):
        """验证: 新实例监听未运行"""
        # 确保停止状态
        assert manager.is_running() is False

    def test_start_listening_no_hotkeys(self, manager):
        """验证: 无快捷键时 start_listening 不创建监听器"""
        manager.start_listening()
        assert manager.is_running() is False

    @patch("pynput.keyboard.GlobalHotKeys")
    def test_start_listening_with_hotkeys(self, mock_ghk, manager):
        """验证: 有快捷键时 start_listening 启动监听"""
        mock_ghk.return_value = _create_mock_listener()
        manager.register_hotkey("<ctrl>+g", lambda: None)
        manager.start_listening()
        assert manager.is_running() is True

    @patch("pynput.keyboard.GlobalHotKeys")
    def test_start_listening_already_running(self, mock_ghk, manager):
        """验证: 已运行时 start_listening 不重复启动"""
        mock_ghk.return_value = _create_mock_listener()
        manager.register_hotkey("<ctrl>+g", lambda: None)
        manager.start_listening()
        first_listener = manager._listener
        manager.start_listening()  # 应该不执行任何操作
        assert manager._listener is first_listener

    @patch("pynput.keyboard.GlobalHotKeys")
    def test_stop_listening(self, mock_ghk, manager):
        """验证: stop_listening 停止监听"""
        mock_ghk.return_value = _create_mock_listener()
        manager.register_hotkey("<ctrl>+g", lambda: None)
        manager.start_listening()
        manager.stop_listening()
        assert manager.is_running() is False
        assert manager._listener is None

    @patch("pynput.keyboard.GlobalHotKeys")
    def test_restart_listening_recreates_listener(self, mock_ghk, manager):
        """验证: restart_listening 重新创建监听器"""
        mock_ghk.return_value = _create_mock_listener()
        manager.register_hotkey("<ctrl>+g", lambda: None)
        manager.start_listening()
        old_listener = manager._listener
        manager.restart_listening()
        assert manager.is_running() is True
        # 因为 mock 返回同一实例，我们主要验证运行状态

    @patch("pynput.keyboard.GlobalHotKeys")
    def test_restart_listening_stops_old_starts_new(self, mock_ghk, manager):
        """验证: restart_listening 先停后启"""
        old_listener = _create_mock_listener()
        new_listener = _create_mock_listener()
        mock_ghk.side_effect = [old_listener, new_listener]

        manager.register_hotkey("<ctrl>+g", lambda: None)
        manager.start_listening()
        manager.restart_listening()

        old_listener.stop.assert_called_once()
        new_listener.start.assert_called_once()


class TestKeyboardManagerReload:
    """reload_hotkeys 热更新测试"""

    @pytest.fixture
    def manager(self):
        km = KeyboardManager()
        km.stop_listening()
        km.clear_hotkeys()
        return km

    def test_reload_hotkeys_no_running_listener(self, manager):
        """验证: 监听未运行时 reload 正常"""
        new_hotkeys = {"<ctrl>+g": lambda: None}
        result = manager.reload_hotkeys(new_hotkeys)
        assert result is True
        assert manager.get_hotkeys() == new_hotkeys

    @patch("pynput.keyboard.GlobalHotKeys")
    def test_reload_hotkeys_with_running_listener(self, mock_ghk, manager):
        """验证: 监听运行中 reload 替换快捷键"""
        mock_ghk.return_value = _create_mock_listener()
        manager.register_hotkey("<ctrl>+o", lambda: None)
        manager.start_listening()

        new_hotkeys = {"<ctrl>+n": lambda: None}
        result = manager.reload_hotkeys(new_hotkeys)
        assert result is True
        assert list(manager.get_hotkeys().keys()) == ["<ctrl>+n"]

    def test_reload_hotkeys_bad_key_returns_false_preserves_old(self, manager):
        """验证: reload 非法热键返回 False 且旧 hotkeys 不变"""
        old_cb = lambda: None
        manager.register_hotkey("<ctrl>+o", old_cb)
        old_hotkeys = manager.get_hotkeys()

        result = manager.reload_hotkeys({"<ctrl>+badkey": lambda: None})
        assert result is False
        assert manager.get_hotkeys() == old_hotkeys

    def test_reload_hotkeys_empty_dict(self, manager):
        """验证: reload 空 dict 返回 True"""
        result = manager.reload_hotkeys({})
        assert result is True


class TestKeyboardManagerGlobal:
    """全局 keyboard_manager 测试"""

    def test_global_is_keyboard_manager(self):
        """验证: 全局实例是 KeyboardManager 类型"""
        assert isinstance(keyboard_manager, KeyboardManager)
