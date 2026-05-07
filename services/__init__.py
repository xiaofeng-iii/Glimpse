"""
Services module
"""
from services.ai_client import ai_client
from services.ocr_engine import ocr_engine
from services.embedding_client import embedding_client
from services.keyboard_manager import keyboard_manager
from services.memory_service import MemoryService
from services.search_service import SearchService

# 延迟导入全局单例 — 这些需要在容器初始化后才能获取
# 通过 container.get("xxx") 方式访问是推荐做法
_memory_service = None
_search_service = None


def get_memory_service():
    """获取全局 MemoryService 实例（通过容器）"""
    global _memory_service
    if _memory_service is None:
        from container import container
        _memory_service = container.get("memory_service")
    return _memory_service


def get_search_service():
    """获取全局 SearchService 实例（通过容器）"""
    global _search_service
    if _search_service is None:
        from container import container
        _search_service = container.get("search_service")
    return _search_service


# 兼容属性访问 — memory_service / search_service 通过属性延迟解析
import sys as _sys


class _LazyServiceProxy:
    def __init__(self, getter):
        self._getter = getter

    def __getattr__(self, name):
        return getattr(self._getter(), name)

    def __repr__(self):
        return repr(self._getter())


memory_service = _LazyServiceProxy(get_memory_service)
search_service = _LazyServiceProxy(get_search_service)

__all__ = [
    "ai_client",
    "ocr_engine",
    "embedding_client",
    "keyboard_manager",
    "memory_service",
    "MemoryService",
    "get_memory_service",
    "search_service",
    "SearchService",
    "get_search_service",
]
