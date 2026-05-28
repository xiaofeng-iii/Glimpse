"""
API Dependencies - Dependency injection for FastAPI routes
Reuses existing DIContainer for minimal code changes
"""
from typing import Optional
from container import container


def get_search_service():
    """Get search service from container"""
    return container.get("search_service")


def get_memory_service():
    """Get memory service from container"""
    return container.get("memory_service")


def get_capture_manager():
    """Get capture manager from container"""
    return container.get("capture_manager")


def get_settings_manager():
    """Get settings manager from container"""
    return container.get("settings_manager")


def get_ai_client():
    """Get AI client from container"""
    return container.get("ai_client")


def get_cluster_buffer():
    """Get cluster buffer from container"""
    return container.get("cluster_buffer")


def get_keyboard_manager():
    """Get keyboard manager from container"""
    return container.get("keyboard_manager")


def get_task_queue():
    """Get task queue from container"""
    return container.get("task_queue")


def get_path_manager():
    """Get path manager from container"""
    return container.get("path_manager")