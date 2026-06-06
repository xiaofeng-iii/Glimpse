"""
pytest 全局配置

为所有测试提供共享 fixtures：
- tmp_path (pytest 内置): 临时目录
- mock_path_manager: 模拟的 PathManager
- mock_settings_manager: 模拟的 SettingsManager
"""

import sys
import types
import importlib.util
from pathlib import Path

import pytest

# 确保项目根目录在 sys.path 中
_project_root = Path(__file__).parent.parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

if importlib.util.find_spec("openai") is None:
    openai_stub = types.ModuleType("openai")

    class _OpenAI:
        def __init__(self, *args, **kwargs):
            pass

    openai_stub.OpenAI = _OpenAI
    sys.modules["openai"] = openai_stub

if importlib.util.find_spec("pynput") is None:
    pynput_stub = types.ModuleType("pynput")
    keyboard_stub = types.ModuleType("pynput.keyboard")

    class GlobalHotKeys:
        def __init__(self, hotkeys=None):
            self.hotkeys = hotkeys

        def start(self):
            return None

        def stop(self):
            return None

    keyboard_stub.GlobalHotKeys = GlobalHotKeys
    pynput_stub.keyboard = keyboard_stub
    sys.modules["pynput.keyboard"] = keyboard_stub
    sys.modules["pynput"] = pynput_stub


@pytest.fixture
def project_root() -> Path:
    """返回项目根目录路径"""
    return _project_root


@pytest.fixture
def mock_path_manager(tmp_path: Path):
    """创建一个模拟的 PathManager，所有路径指向临时目录。

    Returns:
        一个带有 PathManager 接口的 Mock 对象
    """
    from unittest.mock import MagicMock

    screenshots_dir = tmp_path / "screenshots"
    database_dir = tmp_path / "database"
    logs_dir = tmp_path / "logs"
    cache_dir = tmp_path / "cache"
    config_dir = tmp_path / "config"

    for d in [screenshots_dir, database_dir, logs_dir, cache_dir, config_dir]:
        d.mkdir(parents=True, exist_ok=True)

    mock = MagicMock()
    mock.project_root = tmp_path
    mock.data_root = tmp_path / "GlimpseData"
    mock.screenshots_dir = screenshots_dir
    mock.database_dir = database_dir
    mock.logs_dir = logs_dir
    mock.cache_dir = cache_dir
    mock.config_dir = config_dir
    mock.sqlite_path = database_dir / "glimpse.db"
    mock.chroma_path = database_dir / "chroma"
    mock.log_file = logs_dir / "glimpse.log"

    def _get_screenshot_path(filename: str) -> Path:
        return screenshots_dir / filename

    mock.get_screenshot_path = _get_screenshot_path

    def _resolve(*parts: str) -> Path:
        return mock.data_root.joinpath(*parts)

    mock.resolve = _resolve

    return mock


@pytest.fixture
def mock_settings_manager():
    """创建一个模拟的 SettingsManager。

    Returns:
        一个带有 SettingsManager 接口的 Mock 对象
    """
    from unittest.mock import MagicMock

    default_settings = {
        "hotkeys": {
            "screenshot": "<ctrl>+<shift>+g",
            "search": "<ctrl>+<f>",
        },
        "screenshot": {
            "capture_limit_window_seconds": 5.0,
            "max_captures_per_window": 10,
        },
        "ai": {
            "provider": "OpenAI",
            "provider_type": "openai_compatible",
            "base_url": "https://api.openai.com/v1",
            "api_key": "",
            "model": "gpt-4o-mini",
            "timeout": 30,
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
            "close_action": "ask",
        },
    }

    mock = MagicMock()

    def _get(key: str, default=None):
        parts = key.split(".")
        value = default_settings
        for k in parts:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    mock.get = _get
    mock.get_all.return_value = default_settings
    mock.set.return_value = True
    mock.update.return_value = True
    mock.has_changes.return_value = False

    return mock
