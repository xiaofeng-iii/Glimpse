"""
Unit tests for config/path_manager.py
"""
import pytest
from pathlib import Path


class TestPathManagerSingleton:
    def test_singleton_same_instance(self):
        from config.path_manager import PathManager
        pm1 = PathManager()
        pm2 = PathManager()
        assert pm1 is pm2

    def test_global_instance_exists(self):
        from config.path_manager import path_manager
        from config.path_manager import PathManager
        assert isinstance(path_manager, PathManager)


class TestPathManagerDirectories:
    def test_project_root_is_path(self):
        from config.path_manager import PathManager
        pm = PathManager()
        assert isinstance(pm.project_root, Path)

    def test_data_root_ends_with_glimpse_data(self):
        from config.path_manager import PathManager
        pm = PathManager()
        assert pm.data_root.name == "GlimpseData"

    def test_screenshots_dir_under_data_root(self, tmp_path):
        from config.path_manager import PathManager
        pm = PathManager()
        assert pm.screenshots_dir.name == "screenshots"
        assert pm.screenshots_dir.parent == pm.data_root

    def test_database_dir_exists(self):
        from config.path_manager import PathManager
        pm = PathManager()
        assert pm.database_dir.exists()
        assert pm.database_dir.name == "database"

    def test_logs_dir_created(self):
        from config.path_manager import PathManager
        pm = PathManager()
        assert pm.logs_dir.exists()
        assert pm.logs_dir.name == "logs"

    def test_cache_dir_created(self):
        from config.path_manager import PathManager
        pm = PathManager()
        assert pm.cache_dir.exists()
        assert pm.cache_dir.name == "cache"

    def test_config_dir_created(self):
        from config.path_manager import PathManager
        pm = PathManager()
        assert pm.config_dir.exists()
        assert pm.config_dir.name == "config"


class TestPathManagerPaths:
    def test_sqlite_path(self):
        from config.path_manager import PathManager
        pm = PathManager()
        assert pm.sqlite_path.name == "glimpse.db"
        assert pm.sqlite_path.parent == pm.database_dir

    def test_chroma_path(self):
        from config.path_manager import PathManager
        pm = PathManager()
        assert pm.chroma_path.name == "chroma"
        assert pm.chroma_path.parent == pm.database_dir

    def test_log_file(self):
        from config.path_manager import PathManager
        pm = PathManager()
        assert pm.log_file.name == "glimpse.log"
        assert pm.log_file.parent == pm.logs_dir

    def test_get_screenshot_path(self):
        from config.path_manager import PathManager
        pm = PathManager()
        result = pm.get_screenshot_path("test.png")
        assert result.name == "test.png"
        assert result.parent == pm.screenshots_dir

    def test_resolve_method(self):
        from config.path_manager import PathManager
        pm = PathManager()
        result = pm.resolve("subdir", "file.txt")
        assert result == pm.data_root / "subdir" / "file.txt"
