"""
集成测试 fixtures 配置

提供真实 SQLite/ChromaDB 实例（临时目录）+ Mock AI/OCR 客户端，
用于测试模块间交互流程。
"""
import sys
from pathlib import Path

import pytest

_project_root = Path(__file__).parent.parent.parent.resolve()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


class _MockPathManager:
    """模拟 PathManager，所有路径指向临时目录"""

    def __init__(self, base_dir: Path):
        self.project_root = base_dir
        self.data_root = base_dir / "GlimpseData"
        self.screenshots_dir = base_dir / "screenshots"
        self.database_dir = base_dir / "database"
        self.logs_dir = base_dir / "logs"
        self.cache_dir = base_dir / "cache"
        self.config_dir = base_dir / "config"

        for d in [
            self.screenshots_dir,
            self.database_dir,
            self.logs_dir,
            self.cache_dir,
            self.config_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

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


@pytest.fixture(scope="function")
def path_manager(tmp_path):
    """创建指向临时目录的 PathManager"""
    pm = _MockPathManager(tmp_path)
    return pm


@pytest.fixture(scope="function")
def sqlite_manager(path_manager):
    """创建真实的 SQLite 管理器（临时目录）"""
    from db.sqlite_manager import SQLiteManager

    manager = SQLiteManager(path_manager)
    yield manager
    manager.close()


@pytest.fixture(scope="function")
def chroma_manager(path_manager):
    """创建真实的 ChromaDB 管理器（临时目录）"""
    from db.chroma_manager import ChromaManager

    manager = ChromaManager(path_manager)
    yield manager
    manager.close()


@pytest.fixture(scope="function")
def mock_ocr_engine():
    """创建模拟 OCR 引擎 - 返回预设文本"""
    from unittest.mock import MagicMock

    engine = MagicMock()
    engine.extract_text.return_value = "测试 OCR 识别文本内容"
    engine.extract_text_boxes.return_value = [
        ("测试", (10, 10, 50, 30)),
        ("OCR", (60, 10, 100, 30)),
    ]
    return engine


@pytest.fixture(scope="function")
def mock_ai_client():
    """创建模拟 AI 客户端 - 返回预设摘要"""
    from unittest.mock import MagicMock

    client = MagicMock()
    client.is_configured.return_value = True
    client.analyze_image.return_value = "这是一张包含文字内容的截图摘要"
    client.generate_summary.return_value = "文本摘要内容"
    client.test_connection.return_value = True
    return client


@pytest.fixture(scope="function")
def mock_embedding_client():
    """创建模拟嵌入客户端 - 返回模拟向量"""
    from unittest.mock import MagicMock

    client = MagicMock()
    client.get_embedding.return_value = [0.1] * 384
    client.get_embeddings.return_value = [[0.1] * 384]
    client.calculate_similarity.return_value = 0.85
    return client


@pytest.fixture(scope="function")
def memory_service(sqlite_manager, chroma_manager, mock_ocr_engine, mock_ai_client, mock_embedding_client):
    """创建 MemoryService（真实DB + 模拟AI/OCR）"""
    from services.memory_service import MemoryService

    service = MemoryService(
        sqlite_manager=sqlite_manager,
        chroma_manager=chroma_manager,
        ocr_engine=mock_ocr_engine,
        ai_client=mock_ai_client,
        embedding_client=mock_embedding_client,
        task_queue=None,
    )
    return service


@pytest.fixture(scope="function")
def search_service(sqlite_manager, chroma_manager, mock_embedding_client):
    """创建 SearchService（真实DB + 模拟嵌入）"""
    from services.search_service import SearchService

    service = SearchService(
        sqlite_manager=sqlite_manager,
        chroma_manager=chroma_manager,
        embedding_client=mock_embedding_client,
    )
    return service


@pytest.fixture(scope="function")
def sample_image_path(tmp_path):
    """创建一张简单的测试图片"""
    from PIL import Image

    img = Image.new("RGB", (100, 100), color=(73, 109, 137))
    filepath = tmp_path / "test_screenshot.png"
    img.save(str(filepath), "PNG")
    return str(filepath)


@pytest.fixture(scope="function")
def populated_memory_service(memory_service, sample_image_path):
    """创建已填充一条记忆的 MemoryService"""
    memory_id = memory_service.create_memory(sample_image_path, app_name="test_app")
    return memory_service, memory_id
