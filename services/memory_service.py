"""Memory lifecycle orchestration."""

import json
import time
import uuid
from threading import Lock, Semaphore
from typing import TYPE_CHECKING, Callable, List, Optional, Set, Tuple
from weakref import WeakValueDictionary

from utils.logger import get_logger

if TYPE_CHECKING:
    from core.task_queue import TaskQueue
    from db.chroma_manager import ChromaManager
    from db.sqlite_manager import MemoryRecord, SQLiteManager
    from services.ai_client import AIClient
    from services.embedding_client import EmbeddingClient
    from services.ocr_engine import OCREngine


logger = get_logger(__name__)

MAX_CONCURRENT_MEMORIES = 5
SUMMARY_MAX_LENGTH = 4000


class MemoryService:
    """Coordinate OCR, AI summaries, SQLite, and the semantic index."""

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
        self._maintenance_lock = Lock()
        # Backwards-compatible attribute used by a few integration helpers.
        self._repair_lock = self._maintenance_lock

        self._reindex_lock = Lock()
        self._pending_reindexes: Set[str] = set()
        self._running_reindexes: Set[str] = set()
        self._memory_reindex_locks = WeakValueDictionary()

        self._ocr_progress_lock = Lock()
        self._ocr_backfill_progress = self._empty_ocr_backfill_progress()
        self._on_progress: Optional[Callable[[str], None]] = None

    @staticmethod
    def _empty_ocr_backfill_progress() -> dict:
        return {
            "status": "idle",
            "total": 0,
            "processed": 0,
            "succeeded": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "index_failed": 0,
        }

    def set_progress_callback(self, callback: Callable[[str], None]) -> None:
        self._on_progress = callback

    def _report_progress(self, message: str) -> None:
        if self._on_progress:
            self._on_progress(message)

    @staticmethod
    def _embedding_text_for_memory(memory) -> str:
        parts = [
            str(value).strip()
            for value in (memory.ai_summary, memory.text_content)
            if value and str(value).strip()
        ]
        return "\n\n".join(parts)

    @staticmethod
    def _fallback_summary(text_content: str) -> str:
        return text_content.strip()[:200] if text_content.strip() else "无内容"

    def _extract_ocr_text(self, image_paths: List[str]) -> Tuple[str, int]:
        chunks: List[str] = []
        failures = 0
        for image_path in image_paths:
            try:
                text = self._ocr_engine.extract_text(str(image_path))
            except Exception as exc:
                failures += 1
                logger.warning("OCR failed for %s: %s", image_path, exc)
                continue

            normalized = str(text).strip() if text else ""
            if normalized:
                chunks.append(normalized)
        return "\n\n".join(chunks), failures

    @staticmethod
    def _memory_image_paths(memory) -> List[str]:
        image_paths = [str(memory.image_path)]
        if not memory.extra_images:
            return image_paths

        try:
            extra_images = json.loads(memory.extra_images)
        except (TypeError, json.JSONDecodeError):
            logger.warning("Invalid extra_images JSON for memory %s", memory.id)
            return image_paths

        if isinstance(extra_images, list):
            image_paths.extend(str(path) for path in extra_images if path)
        return image_paths

    @staticmethod
    def _emit_memory_updated(memory) -> None:
        if memory is None:
            return
        try:
            from ui.signals import signals

            signals.memory_updated.emit(memory.to_dict())
        except Exception as exc:
            logger.warning("Failed to emit memory_updated for %s: %s", memory.id, exc)

    def _get_memory_reindex_lock(self, memory_id: str):
        """Return the shared serialisation lock for one memory's content/index."""
        with self._reindex_lock:
            memory_lock = self._memory_reindex_locks.get(memory_id)
            if memory_lock is None:
                memory_lock = Lock()
                self._memory_reindex_locks[memory_id] = memory_lock
            return memory_lock

    def _set_index_status_if_current(
        self,
        memory_id: str,
        expected_ai_summary: Optional[str],
        expected_text_content: Optional[str],
        status: str,
        *,
        emit_update: bool,
    ) -> bool:
        if not self._sqlite_manager.compare_and_set_memory_sync_status(
            memory_id,
            expected_ai_summary=expected_ai_summary,
            expected_text_content=expected_text_content,
            sync_status=status,
        ):
            # A newer summary/OCR update arrived during embedding. The coalescing
            # worker will loop and index that newest SQLite value.
            return False
        if emit_update:
            self._emit_memory_updated(self._sqlite_manager.get_memory_by_id(memory_id))
        return status == "SYNCED"

    def _reindex_memory(self, memory_id: str, *, emit_update: bool = True) -> bool:
        # Every entry point (creation, repair, OCR backfill, and summary edits)
        # passes through this per-memory lock. An older embedding can therefore
        # never finish its Chroma upsert after a newer one.
        with self._get_memory_reindex_lock(memory_id):
            return self._reindex_memory_locked(memory_id, emit_update=emit_update)

    def _reindex_memory_locked(
        self,
        memory_id: str,
        *,
        emit_update: bool,
    ) -> bool:
        memory = self._sqlite_manager.get_memory_by_id(memory_id)
        if memory is None:
            return False

        expected_ai_summary = memory.ai_summary
        expected_text_content = memory.text_content
        embedding_text = self._embedding_text_for_memory(memory)
        if not embedding_text:
            self._set_index_status_if_current(
                memory_id,
                expected_ai_summary,
                expected_text_content,
                "FAILED",
                emit_update=emit_update,
            )
            return False

        try:
            embedding = self._embedding_client.get_embedding(embedding_text)
        except Exception as exc:
            logger.warning("Embedding failed for memory %s: %s", memory_id, exc)
            embedding = None

        if not embedding:
            self._set_index_status_if_current(
                memory_id,
                expected_ai_summary,
                expected_text_content,
                "FAILED",
                emit_update=emit_update,
            )
            return False

        try:
            indexed = self._chroma_manager.upsert_memory(
                memory_id=memory.id,
                text=embedding_text,
                embedding=embedding,
                metadata={
                    "memory_id": memory.id,
                    "created_at": memory.created_at,
                    "app_name": memory.app_name,
                    "memory_type": getattr(memory, "memory_type", "screenshot"),
                },
            )
        except Exception as exc:
            logger.warning("Vector upsert failed for memory %s: %s", memory_id, exc)
            indexed = False

        return self._set_index_status_if_current(
            memory_id,
            expected_ai_summary,
            expected_text_content,
            "SYNCED" if indexed else "FAILED",
            emit_update=emit_update,
        )

    def _run_reindex_worker(self, memory_id: str) -> bool:
        last_result = False
        while True:
            with self._reindex_lock:
                if memory_id not in self._pending_reindexes:
                    self._running_reindexes.discard(memory_id)
                    return last_result
                self._pending_reindexes.discard(memory_id)

            last_result = self._reindex_memory(memory_id)

    def schedule_memory_reindex(self, memory_id: str) -> bool:
        """Coalesce rapid edits into one serial worker per memory."""
        if self._task_queue is None:
            return self._reindex_memory(memory_id)

        with self._reindex_lock:
            self._pending_reindexes.add(memory_id)
            if memory_id in self._running_reindexes:
                return True
            self._running_reindexes.add(memory_id)

        task_id = f"memory_reindex_{memory_id}_{uuid.uuid4().hex[:8]}"
        try:
            task = self._task_queue.submit(
                task_id,
                self._run_reindex_worker,
                memory_id,
            )
            if task is not None:
                return True
        except Exception as exc:
            logger.warning("Unable to schedule memory reindex %s: %s", memory_id, exc)

        with self._reindex_lock:
            self._running_reindexes.discard(memory_id)
        return self._run_reindex_worker(memory_id)

    def create_memory(
        self,
        image_path: str,
        app_name: str = "unknown",
        stream_callback: Optional[Callable[[str], None]] = None,
        *,
        memory_id: Optional[str] = None,
    ) -> Optional[str]:
        if memory_id is None:
            memory_id = self.prepare_screenshot_memory(image_path, app_name).id

        acquired = self._semaphore.acquire(timeout=30)
        if not acquired:
            raise RuntimeError("Too many memory creation tasks in progress")

        try:
            with self._active_lock:
                self._active_count += 1
            return self._create_memory_impl(memory_id, image_path, stream_callback)
        except Exception:
            self._sqlite_manager.update_memory_analysis_status(memory_id, "FAILED")
            self._emit_memory_updated(
                self._sqlite_manager.get_memory_by_id(memory_id)
            )
            raise
        finally:
            with self._active_lock:
                self._active_count -= 1
            self._semaphore.release()

    def _create_memory_impl(
        self,
        memory_id: str,
        image_path: str,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        self._report_progress("正在识别文字...")
        text_content, _ = self._extract_ocr_text([image_path])

        self._report_progress("正在生成摘要...")
        if self._ai_client.is_configured():
            ai_summary = self._ai_client.analyze_image(
                image_path,
                prompt=(
                    "请直接描述画面内容和场景，不要提及载体类型（如截图、图片）。"
                    "用简洁的中文描述界面元素、文字信息、操作意图和关键实体："
                ),
                stream_callback=stream_callback,
            )
            ai_summary = (
                str(ai_summary).strip()
                if ai_summary and str(ai_summary).strip()
                else self._fallback_summary(text_content)
            )
        else:
            ai_summary = self._fallback_summary(text_content)

        self._report_progress("正在存储记忆...")
        if not self._sqlite_manager.update_memory_analysis(
            memory_id,
            ai_summary,
            text_content,
        ):
            raise RuntimeError(f"Failed to update memory {memory_id} in SQLite")

        # Analysis and indexing are separate states. Expose OCR/summary output
        # now while the vector index continues under sync_status.
        self._emit_memory_updated(self._sqlite_manager.get_memory_by_id(memory_id))

        # Creation already runs in a background worker. Complete the first index
        # attempt there so memory_saved observers see a final sync status.
        self._reindex_memory(memory_id, emit_update=False)
        self._report_progress("记忆已保存")
        return memory_id

    def create_text_memory(
        self,
        content: str,
        app_name: str = "",
    ) -> Optional[str]:
        """Create a user-authored text memory without OCR or image analysis."""
        if not isinstance(content, str):
            raise ValueError("Text memory content must be a string")
        normalized = content.strip()
        if not normalized or len(normalized) > SUMMARY_MAX_LENGTH:
            raise ValueError(
                f"Text memory must contain between 1 and {SUMMARY_MAX_LENGTH} characters"
            )

        acquired = self._semaphore.acquire(timeout=30)
        if not acquired:
            raise RuntimeError("Too many memory creation tasks in progress")

        try:
            with self._active_lock:
                self._active_count += 1

            memory_id = str(uuid.uuid4())
            created_at = time.strftime("%Y-%m-%d %H:%M:%S")
            from db.sqlite_manager import MemoryRecord

            record = MemoryRecord(
                id=memory_id,
                created_at=created_at,
                image_path="",
                ai_summary=normalized,
                app_name=app_name,
                text_content=None,
                sync_status="PENDING",
                memory_type="text",
            )
            if not self._sqlite_manager.insert_memory(record):
                raise RuntimeError(f"Failed to insert text memory {memory_id} to SQLite")

            # Keep the request open through the first local indexing attempt so
            # exact and semantic search state is final when creation completes.
            self._reindex_memory(memory_id, emit_update=False)
            self._report_progress("文本记忆已保存")
            return memory_id
        finally:
            with self._active_lock:
                self._active_count -= 1
            self._semaphore.release()

    def prepare_screenshot_memory(
        self,
        image_path: str,
        app_name: str = "unknown",
    ) -> "MemoryRecord":
        return self._prepare_image_memory([image_path], app_name)

    def prepare_cluster_memory(
        self,
        image_paths: List[str],
        app_name: str = "unknown",
    ) -> "MemoryRecord":
        if not image_paths:
            raise ValueError("Cluster memory requires at least one image")
        return self._prepare_image_memory(image_paths, app_name)

    def _prepare_image_memory(
        self,
        image_paths: List[str],
        app_name: str,
    ) -> "MemoryRecord":
        """Persist a readable image-memory shell before OCR/AI work starts."""
        from db.sqlite_manager import MemoryRecord

        primary_image = image_paths[0]
        extra_images = image_paths[1:]
        record = MemoryRecord(
            id=str(uuid.uuid4()),
            created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            image_path=str(primary_image),
            ai_summary="",
            app_name=app_name,
            text_content="",
            extra_images=(
                json.dumps(extra_images, ensure_ascii=False)
                if extra_images
                else None
            ),
            sync_status="PENDING",
            analysis_status="PROCESSING",
            memory_type="screenshot",
        )
        if not self._sqlite_manager.insert_memory(record):
            raise RuntimeError(f"Failed to insert memory {record.id} to SQLite")
        return record

    def create_memory_async(
        self,
        image_path: str,
        app_name: str = "unknown",
        on_complete: Optional[Callable[[Optional[str]], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        *,
        memory_id: Optional[str] = None,
    ) -> str:
        if not self._task_queue:
            raise RuntimeError("Task queue not configured for async operations")

        if memory_id is None:
            memory_id = self.prepare_screenshot_memory(image_path, app_name).id

        def task():
            try:
                completed_memory_id = self.create_memory(
                    image_path,
                    app_name,
                    memory_id=memory_id,
                )
                if on_complete:
                    on_complete(completed_memory_id)
            except Exception as exc:
                logger.error("Memory creation error: %s", exc)
                if on_error:
                    on_error(str(exc))

        task_id = f"memory_creation_{uuid.uuid4().hex[:8]}"
        self._task_queue.submit(task_id, task)
        return memory_id

    def create_cluster_memory(
        self,
        image_paths: List[str],
        app_name: str = "unknown",
        stream_callback: Optional[Callable[[str], None]] = None,
        *,
        memory_id: Optional[str] = None,
    ) -> Optional[str]:
        if not image_paths:
            raise ValueError("Cluster memory requires at least one image")
        if memory_id is None:
            memory_id = self.prepare_cluster_memory(image_paths, app_name).id

        acquired = self._semaphore.acquire(timeout=30)
        if not acquired:
            raise RuntimeError("Too many memory creation tasks in progress")

        try:
            with self._active_lock:
                self._active_count += 1
            return self._create_cluster_memory_impl(
                memory_id,
                image_paths,
                stream_callback,
            )
        except Exception:
            self._sqlite_manager.update_memory_analysis_status(memory_id, "FAILED")
            self._emit_memory_updated(
                self._sqlite_manager.get_memory_by_id(memory_id)
            )
            raise
        finally:
            with self._active_lock:
                self._active_count -= 1
            self._semaphore.release()

    def _create_cluster_memory_impl(
        self,
        memory_id: str,
        image_paths: List[str],
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        self._report_progress("正在识别文字...")
        text_content, _ = self._extract_ocr_text(image_paths)

        self._report_progress("正在生成摘要...")
        if self._ai_client.is_configured():
            ai_summary = self._ai_client.analyze_images(
                image_paths,
                prompt=(
                    "请直接描述这些画面中的共同主题和关键内容，不要提及载体类型。"
                    "用简洁的中文概括场景、界面、文字信息和核心实体："
                ),
                stream_callback=stream_callback,
            )
            ai_summary = (
                str(ai_summary).strip()
                if ai_summary and str(ai_summary).strip()
                else self._fallback_summary(text_content)
            )
        else:
            ai_summary = self._fallback_summary(text_content)

        self._report_progress("正在存储记忆...")
        if not self._sqlite_manager.update_memory_analysis(
            memory_id,
            ai_summary,
            text_content,
        ):
            raise RuntimeError(f"Failed to update cluster memory {memory_id} in SQLite")

        self._emit_memory_updated(self._sqlite_manager.get_memory_by_id(memory_id))

        self._reindex_memory(memory_id, emit_update=False)
        self._report_progress("集群记忆已保存")
        return memory_id

    def create_cluster_memory_async(
        self,
        image_paths: List[str],
        app_name: str = "unknown",
        on_complete: Optional[Callable[[Optional[str]], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        *,
        memory_id: Optional[str] = None,
    ) -> str:
        if not self._task_queue:
            raise RuntimeError("Task queue not configured for async operations")
        if memory_id is None:
            memory_id = self.prepare_cluster_memory(image_paths, app_name).id

        def task():
            try:
                completed_memory_id = self.create_cluster_memory(
                    image_paths,
                    app_name,
                    memory_id=memory_id,
                )
                if on_complete:
                    on_complete(completed_memory_id)
            except Exception as exc:
                logger.error("Cluster memory creation error: %s", exc)
                if on_error:
                    on_error(str(exc))

        task_id = f"cluster_memory_{uuid.uuid4().hex[:8]}"
        self._task_queue.submit(task_id, task)
        return memory_id

    def update_memory_summary(
        self,
        memory_id: str,
        summary: str,
    ) -> Optional["MemoryRecord"]:
        normalized = str(summary).strip()
        if not normalized or len(normalized) > SUMMARY_MAX_LENGTH:
            raise ValueError(
                f"Summary must contain between 1 and {SUMMARY_MAX_LENGTH} characters"
            )

        with self._get_memory_reindex_lock(memory_id):
            current = self._sqlite_manager.get_memory_by_id(memory_id)
            if current is None:
                return None
            if current.ai_summary == normalized:
                return current

            if not self._sqlite_manager.update_memory_summary(
                memory_id,
                normalized,
                sync_status="PENDING",
            ):
                raise RuntimeError(f"Failed to update memory {memory_id}")

            updated = self._sqlite_manager.get_memory_by_id(memory_id)
            # Queue the canonical PENDING event before a fast background worker
            # can emit SYNCED/FAILED for the same edit.
            self._emit_memory_updated(updated)
        self.schedule_memory_reindex(memory_id)
        return updated

    def repair_vector_index(
        self,
        batch_size: int = 100,
        force_rebuild: bool = False,
    ) -> dict:
        with self._maintenance_lock:
            return self._repair_vector_index_impl(batch_size, force_rebuild)

    def _repair_vector_index_impl(
        self,
        batch_size: int,
        force_rebuild: bool,
    ) -> dict:
        if force_rebuild and not self._chroma_manager.reset_collection():
            return {
                "status": "failed",
                "processed": 0,
                "indexed": 0,
                "skipped": 0,
                "failed": 0,
                "rebuilt": True,
            }
        if not self._chroma_manager.available:
            return {
                "status": "unavailable",
                "processed": 0,
                "indexed": 0,
                "skipped": 0,
                "failed": 0,
                "rebuilt": force_rebuild,
            }

        total = self._sqlite_manager.get_memories_count()
        existing_ids: Set[str] = set()
        if not force_rebuild:
            offset = 0
            while True:
                ids = self._chroma_manager.get_all_memory_ids(
                    limit=batch_size,
                    offset=offset,
                )
                if not ids:
                    break
                existing_ids.update(ids)
                offset += len(ids)
                if len(ids) < batch_size:
                    break

        processed = 0
        indexed = 0
        skipped = 0
        failed = 0
        offset = 0
        while processed < total:
            memories = self._sqlite_manager.get_all_memories(
                limit=batch_size,
                offset=offset,
            )
            if not memories:
                break

            for memory in memories:
                processed += 1
                is_current = (
                    not force_rebuild
                    and memory.id in existing_ids
                    and memory.sync_status == "SYNCED"
                )
                if is_current:
                    skipped += 1
                    continue

                if self._reindex_memory(memory.id, emit_update=False):
                    indexed += 1
                    existing_ids.add(memory.id)
                else:
                    failed += 1
            offset += len(memories)

        result = {
            "status": "completed",
            "processed": processed,
            "indexed": indexed,
            "skipped": skipped,
            "failed": failed,
            "rebuilt": force_rebuild,
        }
        logger.info(
            "Vector index repair completed: %s indexed, %s skipped, %s failed",
            indexed,
            skipped,
            failed,
        )
        return result

    def maybe_schedule_vector_index_repair(self) -> bool:
        """Queue a non-destructive repair only when persisted state requires it."""
        if not self._task_queue:
            return False

        try:
            sqlite_count = self._sqlite_manager.get_memories_count()
            chroma_count = self._chroma_manager.get_memory_count()
            unsynced_count = self._sqlite_manager.get_unsynced_memories_count()
        except Exception as exc:
            logger.warning("Vector index repair check failed: %s", exc)
            return False

        if sqlite_count == 0 or (
            chroma_count >= sqlite_count and unsynced_count == 0
        ):
            return False

        logger.info(
            "Vector index needs repair (%s/%s, %s unsynced); scheduling",
            chroma_count,
            sqlite_count,
            unsynced_count,
        )
        try:
            task = self._task_queue.submit(
                "vector_index_repair",
                self.repair_vector_index,
            )
        except Exception as exc:
            logger.warning("Unable to schedule vector index repair: %s", exc)
            return False
        return task is not None

    def repair_vector_index_async(self) -> bool:
        """Backward-compatible alias for conditional background repair."""
        return self.maybe_schedule_vector_index_repair()

    def get_vector_index_counts(self) -> dict:
        sqlite_count = self._sqlite_manager.get_memories_count()
        chroma_count = self._chroma_manager.get_memory_count()
        unsynced_count = self._sqlite_manager.get_unsynced_memories_count()
        return {
            "sqlite_count": sqlite_count,
            "chroma_count": chroma_count,
            "unsynced_count": unsynced_count,
            "synced": sqlite_count == chroma_count and unsynced_count == 0,
        }

    def backfill_ocr(self) -> dict:
        """OCR only legacy memories whose recognized text is still empty."""
        with self._maintenance_lock:
            memories = self._sqlite_manager.get_memories_without_text()
            progress = self._empty_ocr_backfill_progress()
            progress.update({"status": "running", "total": len(memories)})
            self._set_ocr_backfill_progress(progress)

            for snapshot in memories:
                current = self._sqlite_manager.get_memory_by_id(snapshot.id)
                if current is None:
                    progress["processed"] += 1
                    progress["skipped"] += 1
                    self._set_ocr_backfill_progress(progress)
                    continue
                if current.text_content and current.text_content.strip():
                    progress["processed"] += 1
                    progress["skipped"] += 1
                    self._set_ocr_backfill_progress(progress)
                    continue
                if getattr(current, "memory_type", "screenshot") == "text":
                    progress["processed"] += 1
                    progress["skipped"] += 1
                    self._set_ocr_backfill_progress(progress)
                    continue

                text_content, ocr_failures = self._extract_ocr_text(
                    self._memory_image_paths(current)
                )
                progress["processed"] += 1
                if not text_content:
                    if ocr_failures:
                        progress["failed"] += 1
                    else:
                        progress["skipped"] += 1
                    self._set_ocr_backfill_progress(progress)
                    continue

                if not self._sqlite_manager.update_memory_text_content(
                    current.id,
                    text_content,
                    sync_status="PENDING",
                ):
                    progress["failed"] += 1
                    self._set_ocr_backfill_progress(progress)
                    continue

                progress["succeeded"] += 1
                progress["updated"] += 1
                pending = self._sqlite_manager.get_memory_by_id(current.id)
                self._emit_memory_updated(pending)
                if not self._reindex_memory(current.id):
                    progress["index_failed"] += 1
                self._set_ocr_backfill_progress(progress)

            progress["status"] = "completed"
            self._set_ocr_backfill_progress(progress)
            return dict(progress)

    def _set_ocr_backfill_progress(self, progress: dict) -> None:
        with self._ocr_progress_lock:
            self._ocr_backfill_progress = dict(progress)

    def get_ocr_backfill_progress(self) -> dict:
        with self._ocr_progress_lock:
            return dict(self._ocr_backfill_progress)

    def delete_memory(self, memory_id: str) -> bool:
        # Serialize deletion with every content/index update for this memory. If
        # a reindex is already running, deletion waits for it and removes the
        # resulting vector afterwards. If deletion wins the lock, later workers
        # observe the missing SQLite row and cannot recreate an orphan vector.
        with self._get_memory_reindex_lock(memory_id):
            deleted_sqlite = self._sqlite_manager.delete_memory(memory_id)
            if not deleted_sqlite:
                return False

            with self._reindex_lock:
                self._pending_reindexes.discard(memory_id)

            try:
                if not self._chroma_manager.delete_memory(memory_id):
                    logger.warning(
                        "Vector cleanup deferred for deleted memory %s",
                        memory_id,
                    )
            except Exception as exc:
                logger.warning(
                    "Vector cleanup failed for deleted memory %s: %s",
                    memory_id,
                    exc,
                )
            return True

    def get_memory(self, memory_id: str) -> Optional["MemoryRecord"]:
        return self._sqlite_manager.get_memory_by_id(memory_id)

    def get_recent_memories(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> List["MemoryRecord"]:
        return self._sqlite_manager.get_all_memories(limit=limit, offset=offset)

    def get_active_count(self) -> int:
        with self._active_lock:
            return self._active_count
