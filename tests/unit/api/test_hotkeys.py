from unittest.mock import MagicMock

from api import hotkeys


class SettingsStub:
    def __init__(self, configured_hotkeys):
        self._configured_hotkeys = configured_hotkeys

    def get(self, key, default=None):
        if key == "hotkeys":
            return self._configured_hotkeys
        return default


def _enable_hotkeys(monkeypatch):
    monkeypatch.setattr(hotkeys, "_hotkeys_enabled", lambda: True)


def test_reload_global_hotkeys_registers_only_screenshot(monkeypatch):
    keyboard_manager = MagicMock()
    keyboard_manager.reload_hotkeys.return_value = True

    _enable_hotkeys(monkeypatch)
    monkeypatch.setattr(
        hotkeys,
        "get_settings_manager",
        lambda: SettingsStub(
            {
                "screenshot": "<ctrl>+<shift>+g",
                "search": "<ctrl>+f",
            }
        ),
    )
    monkeypatch.setattr(hotkeys, "get_keyboard_manager", lambda: keyboard_manager)

    assert hotkeys.reload_global_hotkeys() is True

    (handlers,) = keyboard_manager.reload_hotkeys.call_args.args
    assert list(handlers.keys()) == ["<ctrl>+<shift>+g"]
    assert callable(handlers["<ctrl>+<shift>+g"])


def test_reload_global_hotkeys_registers_nothing_without_screenshot(monkeypatch):
    keyboard_manager = MagicMock()
    keyboard_manager.reload_hotkeys.return_value = True

    _enable_hotkeys(monkeypatch)
    monkeypatch.setattr(
        hotkeys,
        "get_settings_manager",
        lambda: SettingsStub(
            {
                "screenshot": "",
                "search": "<ctrl>+f",
            }
        ),
    )
    monkeypatch.setattr(hotkeys, "get_keyboard_manager", lambda: keyboard_manager)

    assert hotkeys.reload_global_hotkeys() is True

    keyboard_manager.reload_hotkeys.assert_called_once_with({})
