"""
Settings Manager - 配置读写管理
支持构造函数注入PathManager依赖
"""
import copy
import json
from pathlib import Path
from urllib.parse import urlparse
from typing import Dict, Any, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from config.path_manager import PathManager


SETTINGS_SCHEMA: Set[str] = {
    "hotkeys",
    "screenshot",
    "ai",
    "ocr",
    "database",
    "ui",
    "cluster"
}

HOTKEY_DEFAULTS = {
    "screenshot": "<ctrl>+<shift>+g",
    "search": "<ctrl>+<f>",
}


class SettingsManager:
    """设置管理器 - 支持构造函数注入依赖"""

    def __init__(self, path_manager: "PathManager"):
        self._path_manager = path_manager
        self._settings_file = path_manager.config_dir / "settings.json"
        self._settings = self._load_settings()

    def _deep_copy_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        return copy.deepcopy(settings)

    def _load_settings(self) -> Dict[str, Any]:
        if not self._settings_file.exists():
            return self._get_default_settings()

        try:
            with open(self._settings_file, 'r', encoding='utf-8') as f:
                loaded_settings = json.load(f)
            merged_settings = self._merge_with_defaults(loaded_settings)
            if merged_settings != loaded_settings:
                self._save_settings(merged_settings)
            return merged_settings
        except (json.JSONDecodeError, IOError):
            return self._get_default_settings()

    def _merge_with_defaults(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        defaults = self._build_default_settings()
        if not isinstance(settings, dict):
            return defaults
        merged = self._deep_merge(defaults, settings)
        merged["hotkeys"] = self._sanitize_hotkeys(merged.get("hotkeys"))
        return merged

    def _deep_merge(self, base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        merged = self._deep_copy_settings(base)
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    def _build_default_settings(self) -> Dict[str, Any]:
        return {
            "hotkeys": copy.deepcopy(HOTKEY_DEFAULTS),
            "screenshot": {
                "debounce_interval": 5.0,
                "max_captures_per_window": 10
            },
            "ai": {
                "provider": "OpenAI",
                "provider_type": "openai_compatible",
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
                "model": "gpt-4o-mini",
                "timeout": 30
            },
            "ocr": {
                "engine": "rapidocr",
                "language": "ch"
            },
            "database": {
                "sqlite_timeout": 30,
                "chroma_collection": "memories"
            },
            "ui": {
                "theme": "light",
                "auto_hide": False,
                "start_minimized": False,
                "close_action": "ask"
            },
            "cluster": {
                "cluster_mode": False,
                "cluster_auto_submit": True,
                "cluster_max_images": 5,
                "cluster_timeout": 5
            }
        }

    def _get_default_settings(self) -> Dict[str, Any]:
        default_settings = self._build_default_settings()

        self._save_settings(default_settings)
        return default_settings

    def _save_settings(self, settings: Dict[str, Any]):
        try:
            with open(self._settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
        except IOError:
            pass

    def _validate_settings(self, settings: Dict[str, Any], allow_partial: bool = False) -> bool:
        if not isinstance(settings, dict):
            return False

        for key in SETTINGS_SCHEMA:
            if key not in settings:
                if allow_partial:
                    continue
                return False

            section = settings[key]
            if not isinstance(section, dict):
                return False

            if key == "hotkeys":
                if not self._validate_hotkeys(section, allow_partial):
                    return False
            elif key == "screenshot":
                if not self._validate_screenshot(section, allow_partial):
                    return False
            elif key == "ai":
                if not self._validate_ai(section, allow_partial):
                    return False
            elif key == "ocr":
                if not self._validate_ocr(section, allow_partial):
                    return False
            elif key == "database":
                if not self._validate_database(section, allow_partial):
                    return False
            elif key == "ui":
                if not self._validate_ui(section, allow_partial):
                    return False
            elif key == "cluster":
                if not self._validate_cluster(section, allow_partial):
                    return False

        return True

    def _validate_hotkeys(self, section: Dict[str, Any], required_keys: bool = True) -> bool:
        if not isinstance(section, dict):
            return False
        if required_keys:
            required = set(HOTKEY_DEFAULTS.keys())
            missing = required - set(section.keys())
            if missing:
                return False
        allowed = set(HOTKEY_DEFAULTS.keys())
        if any(key not in allowed for key in section.keys()):
            return False
        for key, value in section.items():
            if not isinstance(key, str) or not isinstance(value, str):
                return False
        return True

    def _sanitize_hotkeys(self, section: Optional[Dict[str, Any]]) -> Dict[str, str]:
        if not isinstance(section, dict):
            return copy.deepcopy(HOTKEY_DEFAULTS)

        sanitized = copy.deepcopy(HOTKEY_DEFAULTS)
        for key in HOTKEY_DEFAULTS:
            value = section.get(key)
            if isinstance(value, str) and value:
                sanitized[key] = value
        return sanitized

    def _validate_screenshot(self, section: Dict[str, Any], required_keys: bool = True) -> bool:
        if not isinstance(section, dict):
            return False
        if required_keys:
            required = {"debounce_interval", "max_captures_per_window"}
            missing = required - set(section.keys())
            if missing:
                return False
        if "debounce_interval" in section:
            if not isinstance(section["debounce_interval"], (int, float)):
                return False
            if section["debounce_interval"] <= 0:
                return False
        if "max_captures_per_window" in section:
            if not isinstance(section["max_captures_per_window"], int):
                return False
            if section["max_captures_per_window"] <= 0:
                return False
        return True

    def _validate_ai(self, section: Dict[str, Any], required_keys: bool = True) -> bool:
        if not isinstance(section, dict):
            return False
        if required_keys:
            required = {"provider", "provider_type", "base_url", "api_key", "model", "timeout"}
            missing = required - set(section.keys())
            if missing:
                return False
        for key in ("provider", "provider_type", "base_url", "api_key", "model"):
            if key in section and not isinstance(section[key], str):
                return False
        if "provider" in section and not section["provider"].strip():
            return False
        if "model" in section and not section["model"].strip():
            return False
        if section.get("provider_type") and section["provider_type"] != "openai_compatible":
            return False
        if "api_key" in section and section["api_key"].strip() and not section.get("base_url", "").strip():
            return False
        if "base_url" in section and section["base_url"].strip():
            if not self._is_allowed_base_url(section["base_url"].strip()):
                return False
        if "timeout" in section:
            if not isinstance(section["timeout"], int):
                return False
            if section["timeout"] <= 0:
                return False
        return True

    def _is_allowed_base_url(self, base_url: str) -> bool:
        parsed = urlparse(base_url)
        if parsed.scheme == "https" and parsed.netloc:
            return True
        if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}:
            return True
        return False

    def _validate_ocr(self, section: Dict[str, Any], required_keys: bool = True) -> bool:
        if not isinstance(section, dict):
            return False
        if required_keys:
            required = {"engine", "language"}
            missing = required - set(section.keys())
            if missing:
                return False
        if "engine" in section and not isinstance(section["engine"], str):
            return False
        if "language" in section and not isinstance(section["language"], str):
            return False
        return True

    def _validate_database(self, section: Dict[str, Any], required_keys: bool = False) -> bool:
        if not isinstance(section, dict):
            return False
        if "sqlite_timeout" in section:
            if not isinstance(section["sqlite_timeout"], (int, float)):
                return False
        if "chroma_collection" in section and not isinstance(section["chroma_collection"], str):
            return False
        return True

    def _validate_ui(self, section: Dict[str, Any], required_keys: bool = True) -> bool:
        if not isinstance(section, dict):
            return False
        if required_keys:
            required = {"theme", "auto_hide", "start_minimized", "close_action"}
            missing = required - set(section.keys())
            if missing:
                return False
        if "theme" in section and not isinstance(section["theme"], str):
            return False
        if "auto_hide" in section and not isinstance(section["auto_hide"], bool):
            return False
        if "start_minimized" in section and not isinstance(section["start_minimized"], bool):
            return False
        if "close_action" in section:
            if not isinstance(section["close_action"], str):
                return False
            if section["close_action"] not in {"ask", "minimize", "exit"}:
                return False
        return True

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        value = self._settings

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> bool:
        keys = key.split('.')
        settings = self._settings

        for k in keys[:-1]:
            if k not in settings:
                settings[k] = {}
            settings = settings[k]

        settings[keys[-1]] = value

        self._save_settings(self._settings)
        return True

    def get_all(self) -> Dict[str, Any]:
        return self._deep_copy_settings(self._settings)

    def update(self, settings: Dict[str, Any]) -> bool:
        if not self._validate_settings(settings, allow_partial=True):
            return False

        temp_settings = self._deep_copy_settings(self._settings)
        try:
            for key, value in settings.items():
                if isinstance(value, dict) and key in temp_settings and isinstance(temp_settings[key], dict):
                    temp_settings[key].update(value)
                    if key == "hotkeys":
                        temp_settings[key] = self._sanitize_hotkeys(temp_settings[key])
                else:
                    temp_settings[key] = value

            self._save_settings(temp_settings)
            self._settings = temp_settings
            return True
        except (json.JSONDecodeError, IOError, OSError) as e:
            print(f"Settings save error: {e}")
            return False

    def reset(self):
        self._settings = self._get_default_settings()

    def reload(self):
        try:
            self._settings = self._load_settings()
        except Exception:
            self._settings = self._get_default_settings()

    def _validate_cluster(self, section: Dict[str, Any], required_keys: bool = True) -> bool:
        if not isinstance(section, dict):
            return False
        if required_keys:
            required = {"cluster_mode", "cluster_auto_submit", "cluster_max_images", "cluster_timeout"}
            missing = required - set(section.keys())
            if missing:
                return False
        if "cluster_mode" in section and not isinstance(section["cluster_mode"], bool):
            return False
        if "cluster_auto_submit" in section and not isinstance(section["cluster_auto_submit"], bool):
            return False
        if "cluster_max_images" in section:
            if not isinstance(section["cluster_max_images"], int):
                return False
            if not (1 <= section["cluster_max_images"] <= 10):
                return False
        if "cluster_timeout" in section:
            if not isinstance(section["cluster_timeout"], int):
                return False
            if not (1 <= section["cluster_timeout"] <= 10):
                return False
        return True

    def has_changes(self, new_settings: Dict[str, Any]) -> bool:
        return self._settings != new_settings


settings_manager: Optional["SettingsManager"] = None  # populated by container
