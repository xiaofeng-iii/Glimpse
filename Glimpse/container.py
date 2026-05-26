"""
DI Container - dependency injection container with dual-mode support.

Supports two modes:
  - Real mode:  container.initialize_defaults() wires all real backend services
  - Preview mode: container.initialize_preview_mode() registers mock services for UI development

Usage:
  # Real backend
  from container import container
  container.initialize_defaults()

  # Standalone preview
  from container import container
  container.initialize_preview_mode()
"""
import threading
from collections import namedtuple
from typing import Optional, Callable, Any, List, Dict
from enum import Enum


# ============================================================
# Lifetime & DI Container core (from ourdemo)
# ============================================================

class Lifetime(Enum):
    SINGLETON = "singleton"
    SCOPED = "scoped"
    TRANSIENT = "transient"


class DIContainer:
    """Thread-safe dependency injection container with multiple lifetimes."""

    _instance: Optional["DIContainer"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        with DIContainer._lock:
            if self._initialized:
                return
            self._initialized = True
            self._services: Dict[str, Any] = {}
            self._factories: Dict[str, Callable[[], Any]] = {}
            self._lifetimes: Dict[str, Lifetime] = {}
            self._scoped_instances: Dict[str, Dict[str, Any]] = {}
            self._scoped_lock = threading.Lock()
            self._service_lock = threading.Lock()
            self._shutdown_handlers: List[Callable[[], None]] = []
            self._current_scope: Optional[str] = None

    def register_singleton(self, name: str, instance: Any) -> None:
        with self._service_lock:
            self._services[name] = instance
            self._lifetimes[name] = Lifetime.SINGLETON

    def register_singleton_factory(self, name: str, factory: Callable[[], Any]) -> None:
        with self._service_lock:
            self._factories[name] = factory
            self._lifetimes[name] = Lifetime.SINGLETON

    def register_shutdown_handler(self, handler: Callable[[], None]) -> None:
        with self._service_lock:
            self._shutdown_handlers.append(handler)

    def get(self, name: str, default=None):
        try:
            lifetime = self._lifetimes.get(name)

            if lifetime == Lifetime.SINGLETON:
                return self._get_singleton(name)
            if lifetime == Lifetime.SCOPED:
                return self._get_scoped(name, self._current_scope or "default")
            if lifetime == Lifetime.TRANSIENT:
                return self._create_transient(name)
            if name in self._services:
                return self._services[name]
            if name in self._factories:
                with self._service_lock:
                    if name in self._factories:
                        instance = self._factories[name]()
                        self._services[name] = instance
                        return instance

            return default
        except Exception:
            return default

    def _get_singleton(self, name: str) -> Any:
        if name in self._services:
            return self._services[name]
        with self._service_lock:
            if name in self._services:
                return self._services[name]
            if name in self._factories:
                instance = self._factories[name]()
                self._services[name] = instance
                return instance
        raise KeyError(f"Singleton '{name}' not registered")

    def _get_scoped(self, name: str, scope_id: str) -> Any:
        with self._scoped_lock:
            if scope_id not in self._scoped_instances:
                self._scoped_instances[scope_id] = {}
            scope = self._scoped_instances[scope_id]
            if name in scope:
                return scope[name]
            if name in self._factories:
                instance = self._factories[name]()
                scope[name] = instance
                return instance
        raise KeyError(f"Scoped service '{name}' not registered")

    def _create_transient(self, name: str) -> Any:
        if name in self._factories:
            return self._factories[name]()
        raise KeyError(f"Transient service '{name}' not registered")

    def has(self, name: str) -> bool:
        with self._service_lock:
            return name in self._services or name in self._factories

    # ============================================================
    # Real backend initialization
    # ============================================================

    def initialize_defaults(self) -> None:
        """Wire all real backend services."""
        from config.path_manager import path_manager
        self.register_singleton("path_manager", path_manager)

        from config.settings_manager import SettingsManager
        self.register_singleton_factory("settings_manager", lambda: SettingsManager(self.get("path_manager")))

        from services.ai_client import AIClient
        self.register_singleton_factory("ai_client", lambda: AIClient(self.get("settings_manager")))

        from services.keyboard_manager import keyboard_manager
        self.register_singleton("keyboard_manager", keyboard_manager)

        from services.ocr_engine import ocr_engine
        self.register_singleton("ocr_engine", ocr_engine)

        from services.embedding_client import EmbeddingClient
        self.register_singleton_factory("embedding_client", lambda: EmbeddingClient())

        from core.task_queue import task_queue
        self.register_singleton("task_queue", task_queue)

        from core.capture import CaptureManager
        self.register_singleton_factory("capture_manager", lambda: CaptureManager(self.get("path_manager")))

        from db.sqlite_manager import SQLiteManager
        self.register_singleton_factory("sqlite_manager", lambda: SQLiteManager(self.get("path_manager")))

        from db.chroma_manager import ChromaManager
        self.register_singleton_factory("chroma_manager", lambda: ChromaManager(self.get("path_manager")))

        from services.memory_service import MemoryService
        self.register_singleton_factory("memory_service", lambda: MemoryService(
            sqlite_manager=self.get("sqlite_manager"),
            chroma_manager=self.get("chroma_manager"),
            ocr_engine=self.get("ocr_engine"),
            ai_client=self.get("ai_client"),
            embedding_client=self.get("embedding_client"),
            task_queue=self.get("task_queue"),
        ))

        from services.search_service import SearchService
        self.register_singleton_factory("search_service", lambda: SearchService(
            sqlite_manager=self.get("sqlite_manager"),
            chroma_manager=self.get("chroma_manager"),
            embedding_client=self.get("embedding_client"),
        ))

        self.register_shutdown_handler(self._shutdown_keyboard_manager)
        self.register_shutdown_handler(self._shutdown_task_queue)
        self.register_shutdown_handler(self._shutdown_capture_manager)

    # ============================================================
    # Preview mode initialization (mock services for UI dev)
    # ============================================================

    def initialize_preview_mode(self) -> None:
        """Register mock services for standalone frontend preview."""
        self.register_singleton("search_service", _MockSearchService())
        self.register_singleton("settings_manager", _MockSettingsManager())
        self.register_singleton("keyboard_manager", _MockKeyboardManager())
        self.register_singleton("capture_manager", _MockCaptureManager())
        self.register_singleton("task_queue", _MockTaskQueue())
        self.register_singleton("memory_service", _MockMemoryService())
        self.register_singleton("ai_client", _MockAIClient())
        self.register_singleton("ocr_engine", _MockOCREngine())

    # ============================================================
    # Shutdown
    # ============================================================

    def _shutdown_keyboard_manager(self) -> None:
        if self.has("keyboard_manager"):
            try:
                self.get("keyboard_manager").stop_listening()
            except Exception:
                pass

    def _shutdown_task_queue(self) -> None:
        if self.has("task_queue"):
            try:
                self.get("task_queue").shutdown()
            except Exception:
                pass

    def _shutdown_capture_manager(self) -> None:
        if self.has("capture_manager"):
            try:
                self.get("capture_manager").close()
            except Exception:
                pass

    def shutdown(self) -> None:
        handlers = []
        with self._service_lock:
            handlers = list(reversed(self._shutdown_handlers))
        for handler in handlers:
            try:
                handler()
            except Exception as e:
                print(f"Shutdown handler error: {e}")
        with self._scoped_lock:
            for scope_instances in self._scoped_instances.values():
                for instance in scope_instances.values():
                    if hasattr(instance, "close"):
                        try:
                            instance.close()
                        except Exception:
                            pass
            self._scoped_instances.clear()
        with self._service_lock:
            self._services.clear()
            self._factories.clear()
            self._lifetimes.clear()


# ============================================================
# Mock services for standalone preview mode
# ============================================================

MockMemory = namedtuple("MockMemory", [
    "id", "created_at", "image_path", "ai_summary",
    "app_name", "text_content", "match_sources", "extra_images"
])

_DEMO_MEMORIES = [
    MockMemory(
        id="mem_001", created_at="2026-05-26 14:32:10",
        image_path="./GlimpseData/screenshots/cap_001.png",
        ai_summary="在 Chrome 浏览器中查看了一个关于 Python 异步编程的技术文章，讨论了 asyncio 和协程的使用模式",
        app_name="Chrome",
        text_content="Python asyncio 异步编程指南 - 协程、事件循环和任务调度",
        match_sources=["OCR", "语义"], extra_images=None,
    ),
    MockMemory(
        id="mem_002", created_at="2026-05-26 13:15:42",
        image_path="./GlimpseData/screenshots/cap_002.png",
        ai_summary="VS Code 中正在编辑一个 React 组件，使用了 TypeScript 和 Tailwind CSS 的样式方案",
        app_name="Code",
        text_content="React component with TypeScript and Tailwind",
        match_sources=["OCR"], extra_images=None,
    ),
    MockMemory(
        id="mem_003", created_at="2026-05-26 11:08:33",
        image_path="./GlimpseData/screenshots/cap_003.png",
        ai_summary="微信聊天窗口中与团队成员讨论了 Glimpse 项目的 UI 设计方案，确定了配色和组件布局",
        app_name="WeChat",
        text_content="讨论 Glimpse UI 设计方案的团队聊天记录",
        match_sources=["语义"], extra_images=None,
    ),
    MockMemory(
        id="mem_004", created_at="2026-05-25 18:45:01",
        image_path="./GlimpseData/screenshots/cap_004.png",
        ai_summary="终端中运行 pytest 测试套件，所有 47 个测试通过，包括搜索服务和 OCR 引擎的单元测试",
        app_name="Terminal",
        text_content="pytest results: 47 passed, 0 failed",
        match_sources=["OCR", "语义"], extra_images=None,
    ),
    MockMemory(
        id="mem_005", created_at="2026-05-25 16:22:18",
        image_path="./GlimpseData/screenshots/cap_005.png",
        ai_summary="在 Figma 中查看了 Glimpse 应用的原型设计稿，包含主窗口布局和设置对话框的界面",
        app_name="Figma",
        text_content="Glimpse app prototype design in Figma",
        match_sources=["OCR"], extra_images=None,
    ),
]


class _MockSearchService:
    def get_recent_memories(self, limit=100):
        return _DEMO_MEMORIES[:limit]

    def search(self, query, source_filter="all"):
        query_lower = query.lower()
        results = []
        for m in _DEMO_MEMORIES:
            text = (m.ai_summary + m.text_content + m.app_name).lower()
            if query_lower in text:
                if source_filter == "ocr" and "OCR" not in m.match_sources:
                    continue
                if source_filter == "semantic" and "语义" not in m.match_sources:
                    continue
                results.append(m)
        return results

    def get_memory_by_id(self, memory_id: str):
        for m in _DEMO_MEMORIES:
            if m.id == memory_id:
                return m
        return None


_MOCK_DEFAULTS = {
    "hotkeys.screenshot": "<ctrl>+<shift>+g",
    "hotkeys.search": "<ctrl>+f",
    "hotkeys.clear": "<escape>",
    "screenshot.debounce_interval": 5.0,
    "screenshot.cluster_threshold": 2.0,
    "screenshot.max_captures_per_window": 10,
    "ai.api_key": "",
    "ai.model": "gpt-4o-mini",
    "ai.timeout": 30,
    "ocr.engine": "rapidocr",
    "ocr.language": "ch",
    "ui.theme": "light",
    "ui.auto_hide": False,
    "ui.start_minimized": False,
    "cluster.cluster_mode": False,
    "cluster.cluster_auto_submit": True,
}


class _MockSettingsManager:
    def get(self, key, default=None):
        return _MOCK_DEFAULTS.get(key, default)

    def get_all(self):
        return {
            "hotkeys": {"screenshot": "<ctrl>+<shift>+g", "search": "<ctrl>+f", "clear": "<escape>"},
            "screenshot": {"debounce_interval": 5.0, "cluster_threshold": 2.0, "max_captures_per_window": 10},
            "ai": {"api_key": "", "model": "gpt-4o-mini", "timeout": 30},
            "ocr": {"engine": "rapidocr", "language": "ch"},
            "ui": {"theme": "light", "auto_hide": False, "start_minimized": False},
        }

    def update(self, settings):
        return True

    def reset(self):
        pass

    def has_changes(self, settings):
        return settings != self.get_all()


class _MockKeyboardManager:
    def stop_listening(self):
        pass
    def get_hotkeys(self):
        return {"<ctrl>+<shift>+g": lambda: None}
    def reload_hotkeys(self, hotkeys):
        return True


class _MockCaptureManager:
    def capture_fullscreen(self, delay=0, force_bypass_debounce=False):
        return None

    def update_settings(self, settings):
        return True

    def get_settings(self):
        return {"debounce_interval": 5.0, "cluster_threshold": 2.0, "max_captures_per_window": 10}

    def close(self):
        pass


class _MockTaskQueue:
    def submit(self, *args, **kwargs):
        pass
    def shutdown(self):
        pass
    def wait_for_tasks_completion(self, timeout=None):
        return True
    def cancel_all_pending(self):
        return 0


class _MockMemoryService:
    def create_memory_async(self, image_path, app_name="unknown", on_complete=None, on_error=None):
        if on_complete:
            on_complete(None)

    def create_cluster_memory_async(self, image_paths, app_name="unknown", on_complete=None, on_error=None):
        if on_complete:
            on_complete(None)


class _MockAIClient:
    def is_configured(self):
        return False


class _MockOCREngine:
    def extract_text(self, image_path):
        return ""


# ============================================================
# Global container instance
# ============================================================

container = DIContainer()
