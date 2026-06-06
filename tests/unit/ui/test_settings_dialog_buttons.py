import copy
import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt


class FakeSettingsManager:
    def __init__(self, settings=None):
        self._settings = settings or {
            "hotkeys": {"screenshot": "<ctrl>+<shift>+g", "search": "<ctrl>+<f>"},
            "screenshot": {"capture_limit_window_seconds": 5.0, "max_captures_per_window": 10},
            "cluster": {
                "cluster_mode": False,
                "cluster_auto_submit": True,
                "cluster_max_images": 5,
                "cluster_timeout": 5,
            },
            "ai": {
                "provider": "OpenAI",
                "provider_type": "openai_compatible",
                "base_url": "https://api.openai.com/v1",
                "api_key": "sk-test",
                "model": "gpt-4o-mini",
                "timeout": 30,
            },
            "ocr": {"engine": "rapidocr", "language": "ch"},
            "ui": {
                "theme": "light",
                "auto_hide": False,
                "start_minimized": False,
                "close_action": "ask",
            },
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
        settings_dialog._capture_limit_window_seconds.setValue(10.0)
        with patch.object(QMessageBox, "information") as mock_info:
            result = settings_dialog._on_save()
            assert result is True
            mock_info.assert_not_called()

    def test_save_cluster_settings(self, settings_dialog, qtbot):
        """Cluster capture controls are persisted under the cluster settings section."""
        settings_dialog._cluster_mode.setChecked(True)
        settings_dialog._cluster_auto_submit.setChecked(False)
        settings_dialog._cluster_max_images.setValue(7)
        settings_dialog._cluster_timeout.setValue(4)

        result = settings_dialog._on_save()

        assert result is True
        assert settings_dialog._settings_manager._settings["cluster"] == {
            "cluster_mode": True,
            "cluster_auto_submit": False,
            "cluster_max_images": 7,
            "cluster_timeout": 4,
        }

    def test_save_close_action_setting(self, settings_dialog, qtbot):
        """Close behavior can be changed from the Interface settings tab."""
        idx = settings_dialog._ui_close_action.findData("exit")
        settings_dialog._ui_close_action.setCurrentIndex(idx)

        result = settings_dialog._on_save()

        assert result is True
        assert settings_dialog._settings_manager._settings["ui"]["close_action"] == "exit"


class TestOnApply:
    def test_apply_no_changes_closes_silently(self, settings_dialog, qtbot):
        """No changes -> accept() called, no popup."""
        from unittest.mock import patch
        with patch.object(QMessageBox, "information") as mock_info, \
             patch.object(QMessageBox, "question") as mock_question, \
             patch.object(QMessageBox, "warning") as mock_warning:
            settings_dialog._on_apply()
        assert settings_dialog.result() == 1
        mock_info.assert_not_called()
        mock_question.assert_not_called()
        mock_warning.assert_not_called()

    def test_apply_with_changes_closes(self, settings_dialog, qtbot):
        """Changes + no conflicts -> accept() called, no confirmation popup."""
        settings_dialog._capture_limit_window_seconds.setValue(10.0)
        from unittest.mock import patch
        with patch.object(QMessageBox, "information") as mock_info, \
             patch.object(QMessageBox, "question") as mock_question, \
             patch.object(QMessageBox, "warning") as mock_warning:
            settings_dialog._on_apply()
        assert settings_dialog.result() == 1
        mock_question.assert_not_called()
        assert settings_dialog._settings_manager._settings["screenshot"]["capture_limit_window_seconds"] == 10.0

    def test_apply_with_conflict_shows_dialog(self, settings_dialog, qtbot):
        """Changes + conflict -> shows conflict dialog, user confirms -> accept()."""
        settings_dialog._capture_limit_window_seconds.setValue(10.0)
        from unittest.mock import patch
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes) as mock_question, \
             patch.object(QMessageBox, "information") as mock_info, \
             patch.object(QMessageBox, "warning") as mock_warning:
            with patch.object(settings_dialog, "_detect_conflicts", return_value=["Test conflict"]):
                settings_dialog._on_apply()
        assert settings_dialog.result() == 1
        mock_question.assert_called_once()


class TestCloseEvent:
    def test_close_with_changes_no_prompt(self, settings_dialog, qtbot):
        """Closing with unsaved changes should NOT prompt (no dirty check)."""
        settings_dialog._capture_limit_window_seconds.setValue(99.0)
        from unittest.mock import patch
        with patch.object(QMessageBox, "question") as mock_question:
            settings_dialog.close()
        mock_question.assert_not_called()
