"""
Services module

所有服务实例统一通过 DI 容器 (container.py) 获取：
    from container import container
    container.get("memory_service")
    container.get("search_service")
    container.get("ai_client")
    container.get("ocr_engine")
    container.get("embedding_client")
    container.get("keyboard_manager")

模块级不再提供全局实例，避免隐式全局状态和导入时副作用。
"""
from services.memory_service import MemoryService
from services.search_service import SearchService


__all__ = [
    "MemoryService",
    "SearchService",
]
