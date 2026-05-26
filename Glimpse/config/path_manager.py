"""
Path Manager - 核心路径路由中心
强制所有数据写入 ./GlimpseData 目录
"""
from pathlib import Path
from typing import Union
import os


class PathManager:
    """路径管理器 - 单例模式"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._project_root = Path(__file__).parent.parent.resolve()
        self._data_root = self._project_root / "GlimpseData"

        self._create_directories()

    def _create_directories(self):
        """创建所有必需的目录"""
        dirs = [
            self.screenshots_dir,
            self.database_dir,
            self.logs_dir,
            self.cache_dir,
            self.config_dir,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    @property
    def project_root(self) -> Path:
        return self._project_root

    @property
    def data_root(self) -> Path:
        return self._data_root

    @property
    def screenshots_dir(self) -> Path:
        return self._data_root / "screenshots"

    @property
    def database_dir(self) -> Path:
        return self._data_root / "database"

    @property
    def logs_dir(self) -> Path:
        return self._data_root / "logs"

    @property
    def cache_dir(self) -> Path:
        return self._data_root / "cache"

    @property
    def config_dir(self) -> Path:
        return self._data_root / "config"

    @property
    def sqlite_path(self) -> Path:
        return self.database_dir / "glimpse.db"

    @property
    def chroma_path(self) -> Path:
        return self.database_dir / "chroma"

    @property
    def log_file(self) -> Path:
        return self.logs_dir / "glimpse.log"

    def get_screenshot_path(self, filename: str) -> Path:
        return self.screenshots_dir / filename

    def resolve(self, *parts: str) -> Path:
        return self.data_root.joinpath(*parts)


path_manager = PathManager()
