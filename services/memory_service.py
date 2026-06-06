"""
Memory Service - 记忆流程编排服务
协调截图、AI摘要生成、存储的完整记忆流程
支持构造函数注入依赖，支持多实例隔离
"""
import json
import time
import uuid
from typing import Optional, Callable, List, TYPE_CHECKING
from threading import Semaphore, Lock

from utils.logger import get_logger

if TYPE_CHECKING:
    from db.sqlite_manager import SQLiteManager
    from db.chroma_manager import ChromaManager
    from services.ocr_engine import OCREngine
    from services.ai_client import AIClient
    from services.embedding_client import EmbeddingClient
    from core.task_queue import TaskQueue

logger = get_logger(__name__)


MAX_CONCURRENT_MEMORIES = 5


def _rollback_sqlite(sqlite_manager, memory_id: str) -> None:
    try:
        sqlite_manager.delete_memory(memory_id)
    except Exception as e:
        logger.error("Rollback failed for memory %s: %s", memory_id, e)


class MemoryService:
    """记忆服务 - 编排记忆的完整生命周期"""

    def __init__(
        self,
        sqlite_manager: "SQLiteManager",
        chroma_manager: "ChromaManager",
        ocr_engine: "OCREngine",
        ai_client: "AIClient",
        embedding_client: "EmbeddingClient",
        task_queue: Optional["TaskQueue"] = None,
    ):
        self._sqlite_manager = sqlite_manager
        self._chroma_manager = chroma_manager
        self._ocr_engine = ocr_engine
        self._ai_client = ai_client
        self._embedding_client = embedding_client
        self._task_queue = task_queue

        self._semaphore = Semaphore(MAX_CONCURRENT_MEMORIES)
        self._active_count = 0
        self._active_lock = Lock()
        self._on_progress: Optional[Callable[[str], None]] = None

    def set_progress_callback(self, callback: Callable[[str], None]) -> None:
        self._on_progress = callback

    def _report_progress(self, message: str) -> None:
        if self._on_progress:
            self._on_progress(message)

    def create_memory(
        self,
        image_path: str,
        app_name: str = "unknown",
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        acquired = self._semaphore.acquire(timeout=30)
        if not acquired:
            raise RuntimeError("Too many memory creation tasks in progress")

        try:
            with self._active_lock:
                self._active_count += 1

            return self._create_memory_impl(image_path, app_name, stream_callback)
        finally:
            with self._active_lock:
                self._active_count -= 1
            self._semaphore.release()

    def _create_memory_impl(
        self,
        image_path: str,
        app_name: str,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        memory_id = str(uuid.uuid4())
        created_at = time.strftime("%Y-%m-%d %H:%M:%S")

        text_content = ""

        self._report_progress("正在生成摘要...")
        if self._ai_client.is_configured():
            ai_summary = self._ai_client.analyze_image(
                image_path,
                prompt="请直接描述画面内容和场景，不要提及载体类型（如截图、图片）。用简洁的中文描述界面元素、文字信息、操作意图和关键实体：",
                stream_callback=stream_callback,
            )
        else:
            ai_summary = text_content[:200] if text_content else "无内容"

        self._report_progress("正在存储记忆...")
        from db.sqlite_manager import MemoryRecord
        record = MemoryRecord(
            id=memory_id,
            created_at=created_at,
            image_path=str(image_path),
            ai_summary=ai_summary,
            app_name=app_name,
            text_content=text_content,
            sync_status="PENDING",
        )

        sqlite_success = self._sqlite_manager.insert_memory(record)
        if not sqlite_success:
            raise RuntimeError(f"Failed to insert memory {memory_id} to SQLite")

        chroma_success = True
        if text_content or ai_summary:
            embedding_text = f"{ai_summary} {text_content}".strip()
            embedding = self._embedding_client.get_embedding(embedding_text)
            if embedding:
                chroma_success = self._chroma_manager.add_memory(
                    memory_id=memory_id,
                    text=embedding_text,
                    embedding=embedding,
                    metadata={
                        "app_name": app_name,
                        "created_at": created_at,
                    },
                )

            if not chroma_success:
                _rollback_sqlite(self._sqlite_manager, memory_id)
                raise RuntimeError(f"Failed to insert memory {memory_id} to ChromaDB")

        self._report_progress("记忆已保存")
        return memory_id

    def create_memory_async(
        self,
        image_path: str,
        app_name: str = "unknown",
        on_complete: Optional[Callable[[Optional[str]], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        if not self._task_queue:
            raise RuntimeError("Task queue not configured for async operations")

        def task():
            try:
                memory_id = self.create_memory(image_path, app_name)
                if on_complete:
                    on_complete(memory_id)
            except Exception as e:
                logger.error("Memory creation error: %s", e)
                if on_error:
                    on_error(str(e))

        task_id = f"memory_creation_{uuid.uuid4().hex[:8]}"
        self._task_queue.submit(task_id, task)

    def create_cluster_memory(
        self,
        image_paths: List[str],
        app_name: str = "unknown",
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        acquired = self._semaphore.acquire(timeout=30)
        if not acquired:
            raise RuntimeError("Too many memory creation tasks in progress")

        try:
            with self._active_lock:
                self._active_count += 1

            return self._create_cluster_memory_impl(image_paths, app_name, stream_callback)
        finally:
            with self._active_lock:
                self._active_count -= 1
            self._semaphore.release()

    def _create_cluster_memory_impl(
        self,
        image_paths: List[str],
        app_name: str,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        memory_id = str(uuid.uuid4())
        created_at = time.strftime("%Y-%m-%d %H:%M:%S")
        primary_image = image_paths[0]
        extra_images = image_paths[1:] if len(image_paths) > 1 else []

        text_content = ""

        self._report_progress("正在生成摘要...")
        if self._ai_client.is_configured():
            ai_summary = self._ai_client.analyze_images(
                image_paths,
                prompt="请直接描述这些画面中的共同主题和关键内容，不要提及载体类型。用简洁的中文概括场景、界面、文字信息和核心实体：",
                stream_callback=stream_callback,
            )
        else:
            ai_summary = text_content[:200] if text_content else "无内容"

        self._report_progress("正在存储记忆...")
        from db.sqlite_manager import MemoryRecord
        record = MemoryRecord(
            id=memory_id,
            created_at=created_at,
            image_path=str(primary_image),
            ai_summary=ai_summary,
            app_name=app_name,
            text_content=text_content,
            extra_images=json.dumps(extra_images) if extra_images else None,
            sync_status="PENDING",
        )

        sqlite_success = self._sqlite_manager.insert_memory(record)
        if not sqlite_success:
            raise RuntimeError(f"Failed to insert cluster memory {memory_id} to SQLite")

        chroma_success = True
        if text_content or ai_summary:
            embedding_text = f"{ai_summary} {text_content}".strip()
            embedding = self._embedding_client.get_embedding(embedding_text)
            if embedding:
                chroma_success = self._chroma_manager.add_memory(
                    memory_id=memory_id,
                    text=embedding_text,
                    embedding=embedding,
                    metadata={
                        "app_name": app_name,
                        "created_at": created_at,
                    },
                )

            if not chroma_success:
                _rollback_sqlite(self._sqlite_manager, memory_id)
                raise RuntimeError(f"Failed to insert cluster memory {memory_id} to ChromaDB")

        self._report_progress("集群记忆已保存")
        return memory_id

    def create_cluster_memory_async(
        self,
        image_paths: List[str],
        app_name: str = "unknown",
        on_complete: Optional[Callable[[Optional[str]], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        if not self._task_queue:
            raise RuntimeError("Task queue not configured for async operations")

        def task():
            try:
                memory_id = self.create_cluster_memory(image_paths, app_name)
                if on_complete:
                    on_complete(memory_id)
            except Exception as e:
                logger.error("Cluster memory creation error: %s", e)
                if on_error:
                    on_error(str(e))

        task_id = f"cluster_memory_{uuid.uuid4().hex[:8]}"
        self._task_queue.submit(task_id, task)

    def delete_memory(self, memory_id: str) -> bool:
        deleted_sqlite = self._sqlite_manager.delete_memory(memory_id)
        deleted_chroma = self._chroma_manager.delete_memory(memory_id)
        return deleted_sqlite or deleted_chroma

    def get_memory(self, memory_id: str) -> Optional["MemoryRecord"]:
        return self._sqlite_manager.get_memory_by_id(memory_id)

    def get_recent_memories(self, limit: int = 100, offset: int = 0) -> List["MemoryRecord"]:
        return self._sqlite_manager.get_all_memories(limit=limit, offset=offset)

    def get_active_count(self) -> int:
        with self._active_lock:
            return self._active_count
