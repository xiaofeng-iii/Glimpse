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

from PySide6.QtCore import QObject, Signal


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
        self.register_singleton("cluster_buffer", _MockClusterBuffer())

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
        ai_summary="Browsing a technical article about Python async programming on Chrome, covering asyncio, coroutines, and event loop patterns.",
        app_name="Chrome",
        text_content="Python asyncio - A Guide to Async Programming: Coroutines, Event Loops, and Task Scheduling",
        match_sources=["OCR", "Semantic"], extra_images=None,
    ),
    MockMemory(
        id="mem_002", created_at="2026-05-26 13:15:42",
        image_path="./GlimpseData/screenshots/cap_002.png",
        ai_summary="Editing a React component in VS Code using TypeScript with Tailwind CSS for styling.",
        app_name="VS Code",
        text_content="React component with TypeScript and Tailwind CSS",
        match_sources=["OCR"], extra_images=None,
    ),
    MockMemory(
        id="mem_003", created_at="2026-05-26 11:08:33",
        image_path="./GlimpseData/screenshots/cap_003.png",
        ai_summary="Team discussion in Slack about the Glimpse project UI design, finalizing the color scheme and component layout.",
        app_name="Slack",
        text_content="Team chat discussing Glimpse UI design direction and component architecture",
        match_sources=["Semantic"], extra_images=None,
    ),
    MockMemory(
        id="mem_004", created_at="2026-05-25 18:45:01",
        image_path="./GlimpseData/screenshots/cap_004.png",
        ai_summary="Running pytest test suite in Terminal — all 47 tests passing, including unit tests for search service and OCR engine.",
        app_name="Terminal",
        text_content="pytest results: 47 passed, 0 failed in 12.34s",
        match_sources=["OCR", "Semantic"], extra_images=None,
    ),
    MockMemory(
        id="mem_005", created_at="2026-05-25 16:22:18",
        image_path="./GlimpseData/screenshots/cap_005.png",
        ai_summary="Reviewing the Glimpse app prototype design in Figma, including the main window layout and settings dialog interface.",
        app_name="Figma",
        text_content="Glimpse app prototype — main window and settings dialog mockups",
        match_sources=["OCR"], extra_images=None,
    ),
    MockMemory(
        id="mem_006", created_at="2026-05-25 10:05:37",
        image_path="./GlimpseData/screenshots/cap_006.png",
        ai_summary="Reading API documentation for OpenAI's GPT-4o model, noting the new vision capabilities and reduced latency.",
        app_name="Chrome",
        text_content="OpenAI API Reference — GPT-4o model with vision, 128K context, improved multilingual support",
        match_sources=["OCR", "Semantic"], extra_images=None,
    ),
    MockMemory(
        id="mem_007", created_at="2026-05-24 15:20:55",
        image_path="./GlimpseData/screenshots/cap_007.png",
        ai_summary="Composing an email in Outlook about the Q3 product roadmap, including milestones for the memory assistant feature.",
        app_name="Outlook",
        text_content="Q3 Roadmap — Memory Assistant MVP, Search improvements, Cloud sync beta",
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
                if source_filter == "semantic" and "Semantic" not in m.match_sources:
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


MockCaptureResult = namedtuple("MockCaptureResult", ["image_path", "app_name"])


class _MockCaptureManager:
    _counter = 0

    def capture_fullscreen(self, delay=0, force_bypass_debounce=False):
        _MockCaptureManager._counter += 1
        return MockCaptureResult(
            image_path=f"./GlimpseData/screenshots/cap_00{((_MockCaptureManager._counter - 1) % 7) + 1}.png",
            app_name="Preview",
        )

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
    _counter = 0

    def create_memory_async(self, image_path, app_name="unknown", on_complete=None, on_error=None):
        _MockMemoryService._counter += 1
        mem_id = f"mem_{_MockMemoryService._counter:03d}"
        if on_complete:
            on_complete(mem_id)

    def create_cluster_memory_async(self, image_paths, app_name="unknown", on_complete=None, on_error=None):
        _MockMemoryService._counter += 1
        mem_id = f"cluster_{_MockMemoryService._counter:03d}"
        if on_complete:
            on_complete(mem_id)


class _MockAIClient:
    def is_configured(self):
        return False


class _MockOCREngine:
    def extract_text(self, image_path):
        return ""


class _MockClusterBuffer(QObject):
    """Mock cluster buffer with Qt signals for UI preview."""

    def __init__(self):
        super().__init__()
        self._collecting = False
        self._images = []
        self._max_count = 10

    def is_collecting(self):
        return self._collecting

    def add_image(self, image_path):
        if not self._collecting:
            self._collecting = True
        self._images.append(image_path)
        self.state_changed.emit("COLLECTING", len(self._images), self._max_count)

    def flush(self):
        paths = list(self._images)
        self._images.clear()
        self._collecting = False
        self.state_changed.emit("IDLE", 0, self._max_count)
        self.flushed.emit(paths)

    def discard(self):
        self._images.clear()
        self._collecting = False
        self.state_changed.emit("IDLE", 0, self._max_count)
        self.discarded.emit()


# Define signals on the class (must be at class level for Qt)
_MockClusterBuffer.state_changed = Signal(str, int, int)
_MockClusterBuffer.countdown_changed = Signal(int)
_MockClusterBuffer.flushed = Signal(list)
_MockClusterBuffer.discarded = Signal()


# ============================================================
# Global container instance
# ============================================================

container = DIContainer()
