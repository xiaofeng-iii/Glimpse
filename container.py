"""
DI Container - 依赖注入容器
支持单例、作用域、瞬态三种生命周期
统一管理所有组件的创建、复用、销毁
"""
import threading
from typing import Optional, Callable, Any, List, Dict
from enum import Enum

from utils.logger import get_logger

logger = get_logger(__name__)


class Lifetime(Enum):
    SINGLETON = "singleton"
    SCOPED = "scoped"
    TRANSIENT = "transient"


class DIContainer:
    """依赖注入容器 - 支持多种生命周期的线程安全容器"""

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
            self._service_lock = threading.RLock()
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

    def register_scoped(self, name: str, factory: Callable[[], Any]) -> None:
        with self._service_lock:
            self._factories[name] = factory
            self._lifetimes[name] = Lifetime.SCOPED

    def register_transient(self, name: str, factory: Callable[[], Any]) -> None:
        with self._service_lock:
            self._factories[name] = factory
            self._lifetimes[name] = Lifetime.TRANSIENT

    def register_shutdown_handler(self, handler: Callable[[], None]) -> None:
        with self._service_lock:
            self._shutdown_handlers.append(handler)

    def get(self, name: str, scope_id: Optional[str] = None) -> Any:
        lifetime = self._lifetimes.get(name)

        if lifetime == Lifetime.SINGLETON:
            return self._get_singleton(name)

        if lifetime == Lifetime.SCOPED:
            return self._get_scoped(name, scope_id or self._current_scope or "default")

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

        raise KeyError(f"Service '{name}' not found in container")

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

    def create_scope(self, scope_id: Optional[str] = None) -> "Scope":
        if scope_id is None:
            scope_id = str(id(threading.current_thread()))
        return Scope(self, scope_id)

    def release_scope(self, scope_id: str) -> None:
        with self._scoped_lock:
            if scope_id in self._scoped_instances:
                for instance in self._scoped_instances[scope_id].values():
                    if hasattr(instance, "close"):
                        try:
                            instance.close()
                        except Exception:
                            pass
                del self._scoped_instances[scope_id]

    def has(self, name: str) -> bool:
        with self._service_lock:
            return name in self._services or name in self._factories

    def initialize_defaults(self) -> None:
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

        from core.cluster_buffer import ClusterBuffer
        self.register_singleton_factory("cluster_buffer", lambda: ClusterBuffer(self.get("settings_manager")))

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
        self.register_shutdown_handler(self._shutdown_cluster_buffer)

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

    def _shutdown_cluster_buffer(self) -> None:
        if self.has("cluster_buffer"):
            try:
                self.get("cluster_buffer").close()
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
                logger.error("Shutdown handler error: %s", e)

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


class Scope:
    """作用域管理器 - 提供独立的作用域实例"""

    def __init__(self, container: DIContainer, scope_id: str):
        self._container = container
        self._scope_id = scope_id

    def get(self, name: str) -> Any:
        return self._container.get(name, self._scope_id)

    def release(self) -> None:
        self._container.release_scope(self._scope_id)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


container = DIContainer()
