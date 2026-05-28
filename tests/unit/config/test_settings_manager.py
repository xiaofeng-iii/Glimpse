"""
Unit tests for config/settings_manager.py
"""
import json
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_path_manager(tmp_path):
    pm = MagicMock()
    pm.project_root = tmp_path
    pm.data_root = tmp_path / "GlimpseData"
    pm.config_dir = pm.data_root / "config"
    pm.config_dir.mkdir(parents=True, exist_ok=True)
    return pm


class TestSettingsManagerInit:
    def test_init_creates_instance(self, mock_path_manager):
        from config.settings_manager import SettingsManager
        sm = SettingsManager(mock_path_manager)
        assert sm is not None

    def test_default_settings_loaded(self, mock_path_manager):
        from config.settings_manager import SettingsManager
        sm = SettingsManager(mock_path_manager)
        assert sm.get("hotkeys.screenshot") == "<ctrl>+<shift>+g"
        assert set(sm.get("hotkeys").keys()) == {"screenshot", "search"}
        assert sm.get("ai.provider") == "OpenAI"
        assert sm.get("ai.provider_type") == "openai_compatible"
        assert sm.get("ai.base_url") == "https://api.openai.com/v1"
        assert sm.get("ai.model") == "gpt-4o-mini"

    def test_old_settings_migrated_with_ai_defaults(self, mock_path_manager):
        from config.settings_manager import SettingsManager

        settings_file = mock_path_manager.config_dir / "settings.json"
        old_settings = {
            "hotkeys": {
                "screenshot": "<ctrl>+<shift>+g",
                "search": "<ctrl>+<f>",
                "clear": "<escape>",
            },
            "screenshot": {
                "debounce_interval": 5.0,
                "max_captures_per_window": 10,
            },
            "ai": {
                "api_key": "sk-existing",
                "model": "custom-model",
                "timeout": 45,
            },
            "ocr": {
                "engine": "rapidocr",
                "language": "ch",
            },
            "database": {
                "sqlite_timeout": 30,
                "chroma_collection": "memories",
            },
            "ui": {
                "theme": "light",
                "auto_hide": False,
                "start_minimized": False,
            },
        }
        settings_file.write_text(json.dumps(old_settings), encoding="utf-8")

        sm = SettingsManager(mock_path_manager)

        assert sm.get("ai.provider") == "OpenAI"
        assert sm.get("ai.provider_type") == "openai_compatible"
        assert sm.get("ai.base_url") == "https://api.openai.com/v1"
        assert sm.get("ai.api_key") == "sk-existing"
        assert sm.get("ai.model") == "custom-model"
        assert sm.get("ai.timeout") == 45
        assert sm.get("hotkeys.clear") is None
        assert sm.get("ui.close_action") == "ask"

        persisted = json.loads(settings_file.read_text(encoding="utf-8"))
        assert persisted["ai"]["provider"] == "OpenAI"
        assert persisted["ai"]["api_key"] == "sk-existing"
        assert "clear" not in persisted["hotkeys"]

    def test_get_with_default(self, mock_path_manager):
        from config.settings_manager import SettingsManager
        sm = SettingsManager(mock_path_manager)
        result = sm.get("nonexistent.key", "fallback")
        assert result == "fallback"

    def test_get_nonexistent_no_default(self, mock_path_manager):
        from config.settings_manager import SettingsManager
        sm = SettingsManager(mock_path_manager)
        result = sm.get("nonexistent.key")
        assert result is None


class TestSettingsManagerGetSet:
    def test_set_and_get_simple(self, mock_path_manager):
        from config.settings_manager import SettingsManager
        sm = SettingsManager(mock_path_manager)
        sm.set("hotkeys.screenshot", "<ctrl>+g")
        assert sm.get("hotkeys.screenshot") == "<ctrl>+g"

    def test_set_creates_intermediate_path(self, mock_path_manager):
        from config.settings_manager import SettingsManager
        sm = SettingsManager(mock_path_manager)
        result = sm.set("completely.nonexistent.key", "value")
        assert result is True
        assert sm.get("completely.nonexistent.key") == "value"

    def test_get_top_level_section(self, mock_path_manager):
        from config.settings_manager import SettingsManager
        sm = SettingsManager(mock_path_manager)
        hotkeys = sm.get("hotkeys")
        assert isinstance(hotkeys, dict)
        assert "screenshot" in hotkeys

    def test_get_all_returns_dict(self, mock_path_manager):
        from config.settings_manager import SettingsManager
        sm = SettingsManager(mock_path_manager)
        all_settings = sm.get_all()
        assert isinstance(all_settings, dict)
        assert "hotkeys" in all_settings


class TestSettingsManagerUpdate:
    def test_update_partial_section_fails_validation(self, mock_path_manager):
        from config.settings_manager import SettingsManager
        sm = SettingsManager(mock_path_manager)
        # Partial sub-sections fail validation (all sub-keys required)
        result = sm.update({"hotkeys": {"screenshot": "<ctrl>+x"}})
        assert result is False
        assert sm.get("hotkeys.screenshot") == "<ctrl>+<shift>+g"

    def test_update_full_section(self, mock_path_manager):
        from config.settings_manager import SettingsManager
        sm = SettingsManager(mock_path_manager)
        result = sm.update({
            "ui": {
                "theme": "dark",
                "auto_hide": True,
                "start_minimized": True,
                "close_action": "minimize",
            }
        })
        assert result is True
        assert sm.get("ui.theme") == "dark"
        assert sm.get("ui.close_action") == "minimize"

    def test_update_invalid_no_change(self, mock_path_manager):
        from config.settings_manager import SettingsManager
        sm = SettingsManager(mock_path_manager)
        original = sm.get("hotkeys.screenshot")
        sm.update({"hotkeys": {"nonexistent": "value"}})
        # Invalid partial update rejected, original preserved
        assert sm.get("hotkeys.screenshot") == original

    @pytest.mark.parametrize(
        "ai_settings",
        [
            {
                "provider": "Anthropic",
                "provider_type": "anthropic",
                "base_url": "https://api.anthropic.com",
                "api_key": "sk-test",
                "model": "claude",
                "timeout": 30,
            },
            {
                "provider": 123,
                "provider_type": "openai_compatible",
                "base_url": "https://api.example.com/v1",
                "api_key": "sk-test",
                "model": "custom-model",
                "timeout": 30,
            },
            {
                "provider": "Custom",
                "provider_type": "openai_compatible",
                "base_url": "http://api.example.com/v1",
                "api_key": "sk-test",
                "model": "custom-model",
                "timeout": 30,
            },
            {
                "provider": "Custom",
                "provider_type": "openai_compatible",
                "base_url": "",
                "api_key": "sk-test",
                "model": "custom-model",
                "timeout": 30,
            },
            {
                "provider": "   ",
                "provider_type": "openai_compatible",
                "base_url": "https://api.example.com/v1",
                "api_key": "sk-test",
                "model": "custom-model",
                "timeout": 30,
            },
            {
                "provider": "Custom",
                "provider_type": "openai_compatible",
                "base_url": "https://api.example.com/v1",
                "api_key": "sk-test",
                "model": "   ",
                "timeout": 30,
            },
        ],
    )
    def test_update_invalid_ai_config_rejected(self, mock_path_manager, ai_settings):
        from config.settings_manager import SettingsManager

        sm = SettingsManager(mock_path_manager)
        original = sm.get_all()

        assert sm.update({"ai": ai_settings}) is False
        assert sm.get_all() == original

    def test_update_allows_local_http_base_url(self, mock_path_manager):
        from config.settings_manager import SettingsManager

        sm = SettingsManager(mock_path_manager)

        assert sm.update({
            "ai": {
                "provider": "Local",
                "provider_type": "openai_compatible",
                "base_url": "http://localhost:11434/v1",
                "api_key": "local-key",
                "model": "local-model",
                "timeout": 30,
            }
        }) is True
        assert sm.get("ai.base_url") == "http://localhost:11434/v1"


class TestSettingsManagerReset:
    def test_reset_restores_defaults(self, mock_path_manager):
        from config.settings_manager import SettingsManager
        sm = SettingsManager(mock_path_manager)
        sm.set("hotkeys.screenshot", "<ctrl>+x")
        sm.reset()
        assert sm.get("hotkeys.screenshot") == "<ctrl>+<shift>+g"

    def test_reload_reads_from_disk(self, mock_path_manager):
        from config.settings_manager import SettingsManager
        sm = SettingsManager(mock_path_manager)
        sm.set("hotkeys.screenshot", "<ctrl>+x")
        # reload reads the persisted file (which now has the modified value)
        sm.reload()
        assert sm.get("hotkeys.screenshot") == "<ctrl>+x"


class TestSettingsManagerHasChanges:
    def test_has_changes_true(self, mock_path_manager):
        from config.settings_manager import SettingsManager
        sm = SettingsManager(mock_path_manager)
        current = sm.get_all()
        modified = dict(current)
        modified["hotkeys"] = dict(current["hotkeys"])
        modified["hotkeys"]["screenshot"] = "<ctrl>+x"
        assert sm.has_changes(modified) is True

    def test_has_changes_false(self, mock_path_manager):
        from config.settings_manager import SettingsManager
        sm = SettingsManager(mock_path_manager)
        current = sm.get_all()
        assert sm.has_changes(current) is False


class TestSettingsManagerGlobal:
    def test_global_is_none_initially(self):
        from config.settings_manager import settings_manager
        assert settings_manager is None


class TestSettingsManagerCluster:
    def test_default_cluster_settings(self, mock_path_manager):
        from config.settings_manager import SettingsManager
        sm = SettingsManager(mock_path_manager)
        assert sm.get("cluster.cluster_mode") is False
        assert sm.get("cluster.cluster_auto_submit") is True
        assert sm.get("cluster.cluster_max_images") == 5
        assert sm.get("cluster.cluster_timeout") == 5

    def test_update_valid_cluster_settings(self, mock_path_manager):
        from config.settings_manager import SettingsManager
        sm = SettingsManager(mock_path_manager)
        result = sm.update({
            "cluster": {
                "cluster_mode": True,
                "cluster_auto_submit": False,
                "cluster_max_images": 8,
                "cluster_timeout": 3
            }
        })
        assert result is True
        assert sm.get("cluster.cluster_mode") is True
        assert sm.get("cluster.cluster_auto_submit") is False
        assert sm.get("cluster.cluster_max_images") == 8
        assert sm.get("cluster.cluster_timeout") == 3

    @pytest.mark.parametrize(
        "invalid_cluster",
        [
            # Invalid types
            {"cluster_mode": "not_bool", "cluster_auto_submit": True, "cluster_max_images": 5, "cluster_timeout": 5},
            {"cluster_mode": True, "cluster_auto_submit": 123, "cluster_max_images": 5, "cluster_timeout": 5},
            {"cluster_mode": True, "cluster_auto_submit": True, "cluster_max_images": "5", "cluster_timeout": 5},
            {"cluster_mode": True, "cluster_auto_submit": True, "cluster_max_images": 5, "cluster_timeout": 5.5},
            # Out of bounds max_images
            {"cluster_mode": True, "cluster_auto_submit": True, "cluster_max_images": 0, "cluster_timeout": 5},
            {"cluster_mode": True, "cluster_auto_submit": True, "cluster_max_images": 11, "cluster_timeout": 5},
            # Out of bounds timeout
            {"cluster_mode": True, "cluster_auto_submit": True, "cluster_max_images": 5, "cluster_timeout": 0},
            {"cluster_mode": True, "cluster_auto_submit": True, "cluster_max_images": 5, "cluster_timeout": 11},
        ]
    )
    def test_update_invalid_cluster_settings_rejected(self, mock_path_manager, invalid_cluster):
        from config.settings_manager import SettingsManager
        sm = SettingsManager(mock_path_manager)
        original = sm.get_all()
        assert sm.update({"cluster": invalid_cluster}) is False
        assert sm.get_all() == original

