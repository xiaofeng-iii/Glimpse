import copy
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt


class FakeSettingsManager:
    def __init__(self, settings=None):
        self._settings = settings or {
            "hotkeys": {"screenshot": "<ctrl>+<shift>+g", "search": "<ctrl>+<f>"},
            "screenshot": {"debounce_interval": 5.0, "cluster_threshold": 2.0, "max_captures_per_window": 10},
            "ai": {"api_key": "sk-test", "model": "gpt-4o-mini", "timeout": 30},
            "ocr": {"engine": "rapidocr", "language": "ch"},
            "ui": {"theme": "light", "auto_hide": False, "start_minimized": False},
        }

    def get_all(self):
        return copy.deepcopy(self._settings)

    def update(self, settings):
        self._settings = copy.deepcopy(settings)
        return True

    def get(self, key, default=None):
        keys = key.split(".")
        val = self._settings
        for k in keys:
            val = val.get(k, {})
        return val if val != {} else default


@pytest.fixture
def settings_dialog(qtbot):
    from ui.settings_dialog import SettingsDialog
    sm = FakeSettingsManager()
    with patch("ui.settings_dialog.ThemeManager"):
        dlg = SettingsDialog(settings_manager=sm)
    qtbot.addWidget(dlg)
    return dlg


class TestOnSave:
    def test_save_no_changes_silent(self, settings_dialog, qtbot):
        """When no settings changed, _on_save returns True silently (no QMessageBox)."""
        with patch.object(QMessageBox, "information") as mock_info:
            result = settings_dialog._on_save()
            assert result is True
            mock_info.assert_not_called()

    def test_save_with_changes_succeeds(self, settings_dialog, qtbot):
        """When settings changed, _on_save saves and returns True silently (no popup)."""
        settings_dialog._debounce_interval.setValue(10.0)
        with patch.object(QMessageBox, "information") as mock_info:
            result = settings_dialog._on_save()
            assert result is True
            mock_info.assert_not_called()
