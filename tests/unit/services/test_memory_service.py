"""
Unit tests for services/memory_service.py
"""
import pytest
from unittest.mock import MagicMock, patch, call


@pytest.fixture
def mock_services():
    sqlite_mgr = MagicMock()
    sqlite_mgr.insert_memory.return_value = True
    sqlite_mgr.delete_memory.return_value = True

    chroma_mgr = MagicMock()
    chroma_mgr.add_memory.return_value = True
    chroma_mgr.upsert_memory.return_value = True
    chroma_mgr.reset_collection.return_value = True
    chroma_mgr.delete_memory.return_value = True
    chroma_mgr.available = True

    ocr_engine = MagicMock()
    ocr_engine.extract_text.return_value = "extracted text"

    ai_client = MagicMock()
    ai_client.is_configured.return_value = True
    ai_client.analyze_image.return_value = "AI summary"

    embedding_client = MagicMock()
    embedding_client.get_embedding.return_value = [0.1] * 384

    task_queue = MagicMock()
    return {
        "sqlite_manager": sqlite_mgr,
        "chroma_manager": chroma_mgr,
        "ocr_engine": ocr_engine,
        "ai_client": ai_client,
        "embedding_client": embedding_client,
        "task_queue": task_queue,
    }


class TestMemoryServiceInit:
    def test_init_stores_dependencies(self, mock_services):
        from services.memory_service import MemoryService
        ms = MemoryService(
            sqlite_manager=mock_services["sqlite_manager"],
            chroma_manager=mock_services["chroma_manager"],
            ocr_engine=mock_services["ocr_engine"],
            ai_client=mock_services["ai_client"],
            embedding_client=mock_services["embedding_client"],
        )
        assert ms._sqlite_manager is mock_services["sqlite_manager"]
        assert ms._ai_client is mock_services["ai_client"]

    def test_init_with_task_queue(self, mock_services):
        from services.memory_service import MemoryService
        ms = MemoryService(
            sqlite_manager=mock_services["sqlite_manager"],
            chroma_manager=mock_services["chroma_manager"],
            ocr_engine=mock_services["ocr_engine"],
            ai_client=mock_services["ai_client"],
            embedding_client=mock_services["embedding_client"],
            task_queue=mock_services["task_queue"],
        )
        assert ms._task_queue is mock_services["task_queue"]

    def test_progress_callback(self, mock_services):
        from services.memory_service import MemoryService
        ms = MemoryService(**{k: v for k, v in mock_services.items() if k != "task_queue"})
        cb = MagicMock()
        ms.set_progress_callback(cb)
        ms._report_progress("test")
        cb.assert_called_once_with("test")


class TestMemoryServiceCreateMemory:
    def test_create_memory_success(self, mock_services):
        from services.memory_service import MemoryService
        ms = MemoryService(
            sqlite_manager=mock_services["sqlite_manager"],
            chroma_manager=mock_services["chroma_manager"],
            ocr_engine=mock_services["ocr_engine"],
            ai_client=mock_services["ai_client"],
            embedding_client=mock_services["embedding_client"],
        )
        memory_id = ms.create_memory("/fake/path.png", app_name="chrome")
        assert memory_id is not None
        mock_services["sqlite_manager"].insert_memory.assert_called_once()
        mock_services["chroma_manager"].add_memory.assert_called_once()

    def test_create_memory_ai_not_configured(self, mock_services):
        from services.memory_service import MemoryService
        mock_services["ai_client"].is_configured.return_value = False
        ms = MemoryService(
            sqlite_manager=mock_services["sqlite_manager"],
            chroma_manager=mock_services["chroma_manager"],
            ocr_engine=mock_services["ocr_engine"],
            ai_client=mock_services["ai_client"],
            embedding_client=mock_services["embedding_client"],
        )
        memory_id = ms.create_memory("/fake/path.png")
        assert memory_id is not None
        mock_services["sqlite_manager"].insert_memory.assert_called_once()

    def test_create_memory_chroma_fail_rolls_back(self, mock_services):
        from services.memory_service import MemoryService
        mock_services["chroma_manager"].add_memory.return_value = False
        ms = MemoryService(
            sqlite_manager=mock_services["sqlite_manager"],
            chroma_manager=mock_services["chroma_manager"],
            ocr_engine=mock_services["ocr_engine"],
            ai_client=mock_services["ai_client"],
            embedding_client=mock_services["embedding_client"],
        )
        with pytest.raises(RuntimeError, match="ChromaDB"):
            ms.create_memory("/fake/path.png")
        # Rollback should delete from SQLite
        mock_services["sqlite_manager"].delete_memory.assert_called_once()

    def test_create_memory_does_not_extract_ocr_text(self, mock_services):
        from services.memory_service import MemoryService
        mock_services["ocr_engine"].extract_text.return_value = "Hello World"
        ms = MemoryService(
            sqlite_manager=mock_services["sqlite_manager"],
            chroma_manager=mock_services["chroma_manager"],
            ocr_engine=mock_services["ocr_engine"],
            ai_client=mock_services["ai_client"],
            embedding_client=mock_services["embedding_client"],
        )
        ms.create_memory("/fake/path.png")
        mock_services["ocr_engine"].extract_text.assert_not_called()
        record = mock_services["sqlite_manager"].insert_memory.call_args[0][0]
        assert record.text_content == ""


class TestMemoryServiceAsync:
    def test_create_memory_async_no_queue_raises(self, mock_services):
        from services.memory_service import MemoryService
        ms = MemoryService(
            sqlite_manager=mock_services["sqlite_manager"],
            chroma_manager=mock_services["chroma_manager"],
            ocr_engine=mock_services["ocr_engine"],
            ai_client=mock_services["ai_client"],
            embedding_client=mock_services["embedding_client"],
        )
        with pytest.raises(RuntimeError, match="not configured"):
            ms.create_memory_async("/fake/path.png")

    def test_create_memory_async_submits_task(self, mock_services):
        from services.memory_service import MemoryService
        ms = MemoryService(
            sqlite_manager=mock_services["sqlite_manager"],
            chroma_manager=mock_services["chroma_manager"],
            ocr_engine=mock_services["ocr_engine"],
            ai_client=mock_services["ai_client"],
            embedding_client=mock_services["embedding_client"],
            task_queue=mock_services["task_queue"],
        )
        ms.create_memory_async("/fake/path.png")
        mock_services["task_queue"].submit.assert_called_once()
        args, kwargs = mock_services["task_queue"].submit.call_args
        assert len(args) == 2
        assert isinstance(args[0], str)
        assert args[0].startswith("memory_creation_")
        assert callable(args[1])


class TestMemoryServiceVectorRepair:
    def test_repair_vector_index_indexes_missing_memories(self, mock_services):
        from db.sqlite_manager import MemoryRecord
        from services.memory_service import MemoryService

        existing = MemoryRecord(
            id="existing",
            created_at="now",
            image_path="path",
            ai_summary="old summary",
            app_name="app",
        )
        missing = MemoryRecord(
            id="missing",
            created_at="later",
            image_path="path",
            ai_summary="new summary",
            app_name="app",
        )
        mock_services["sqlite_manager"].get_memories_count.return_value = 2
        mock_services["sqlite_manager"].get_all_memories.return_value = [existing, missing]
        mock_services["chroma_manager"].get_all_memory_ids.return_value = ["existing"]

        ms = MemoryService(**mock_services)
        result = ms.repair_vector_index()

        assert result["indexed"] == 1
        assert result["skipped"] == 1
        mock_services["chroma_manager"].upsert_memory.assert_called_once()
        kwargs = mock_services["chroma_manager"].upsert_memory.call_args.kwargs
        assert kwargs["memory_id"] == "missing"
        assert kwargs["text"] == "new summary"

    def test_repair_vector_index_force_rebuild_indexes_all_memories(self, mock_services):
        from db.sqlite_manager import MemoryRecord
        from services.memory_service import MemoryService

        memory = MemoryRecord(
            id="mem-1",
            created_at="now",
            image_path="path",
            ai_summary="summary",
            app_name="app",
        )
        mock_services["sqlite_manager"].get_memories_count.return_value = 1
        mock_services["sqlite_manager"].get_all_memories.return_value = [memory]
        mock_services["chroma_manager"].get_all_memory_ids.return_value = ["mem-1"]

        ms = MemoryService(**mock_services)
        result = ms.repair_vector_index(force_rebuild=True)

        assert result["rebuilt"] is True
        assert result["indexed"] == 1
        assert result["skipped"] == 0
        mock_services["chroma_manager"].reset_collection.assert_called_once()
        mock_services["chroma_manager"].upsert_memory.assert_called_once()

    def test_repair_vector_index_async_skips_when_counts_match(self, mock_services):
        from services.memory_service import MemoryService

        mock_services["sqlite_manager"].get_memories_count.return_value = 3
        mock_services["chroma_manager"].get_memory_count.return_value = 3

        ms = MemoryService(**mock_services)
        assert ms.repair_vector_index_async() is False
        mock_services["task_queue"].submit.assert_not_called()

    def test_repair_vector_index_async_schedules_when_chroma_is_behind(self, mock_services):
        from services.memory_service import MemoryService

        mock_services["sqlite_manager"].get_memories_count.return_value = 3
        mock_services["chroma_manager"].get_memory_count.return_value = 1

        ms = MemoryService(**mock_services)
        assert ms.repair_vector_index_async() is True
        mock_services["task_queue"].submit.assert_called_once_with(
            "vector_index_repair",
            ms.repair_vector_index,
        )


class TestMemoryServiceDelete:
    def test_delete_memory_success(self, mock_services):
        from services.memory_service import MemoryService
        ms = MemoryService(
            sqlite_manager=mock_services["sqlite_manager"],
            chroma_manager=mock_services["chroma_manager"],
            ocr_engine=mock_services["ocr_engine"],
            ai_client=mock_services["ai_client"],
            embedding_client=mock_services["embedding_client"],
        )
        result = ms.delete_memory("test-id")
        assert result is True
        mock_services["sqlite_manager"].delete_memory.assert_called_with("test-id")
        mock_services["chroma_manager"].delete_memory.assert_called_with("test-id")

    def test_delete_memory_both_fail(self, mock_services):
        from services.memory_service import MemoryService
        mock_services["sqlite_manager"].delete_memory.return_value = False
        mock_services["chroma_manager"].delete_memory.return_value = False
        ms = MemoryService(
            sqlite_manager=mock_services["sqlite_manager"],
            chroma_manager=mock_services["chroma_manager"],
            ocr_engine=mock_services["ocr_engine"],
            ai_client=mock_services["ai_client"],
            embedding_client=mock_services["embedding_client"],
        )
        result = ms.delete_memory("test-id")
        assert result is False


class TestMemoryServiceQuery:
    def test_get_memory(self, mock_services):
        from services.memory_service import MemoryService
        from db.sqlite_manager import MemoryRecord
        mock_record = MagicMock(spec=MemoryRecord)
        mock_services["sqlite_manager"].get_memory_by_id.return_value = mock_record
        ms = MemoryService(
            sqlite_manager=mock_services["sqlite_manager"],
            chroma_manager=mock_services["chroma_manager"],
            ocr_engine=mock_services["ocr_engine"],
            ai_client=mock_services["ai_client"],
            embedding_client=mock_services["embedding_client"],
        )
        result = ms.get_memory("test-id")
        assert result is mock_record

    def test_get_recent_memories(self, mock_services):
        from services.memory_service import MemoryService
        mock_services["sqlite_manager"].get_all_memories.return_value = []
        ms = MemoryService(
            sqlite_manager=mock_services["sqlite_manager"],
            chroma_manager=mock_services["chroma_manager"],
            ocr_engine=mock_services["ocr_engine"],
            ai_client=mock_services["ai_client"],
            embedding_client=mock_services["embedding_client"],
        )
        result = ms.get_recent_memories(limit=50)
        assert result == []
        mock_services["sqlite_manager"].get_all_memories.assert_called_with(limit=50, offset=0)

    def test_get_active_count_initial(self, mock_services):
        from services.memory_service import MemoryService
        ms = MemoryService(
            sqlite_manager=mock_services["sqlite_manager"],
            chroma_manager=mock_services["chroma_manager"],
            ocr_engine=mock_services["ocr_engine"],
            ai_client=mock_services["ai_client"],
            embedding_client=mock_services["embedding_client"],
        )
        assert ms.get_active_count() == 0
