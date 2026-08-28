"""Unit tests for services.memory_service."""

import copy
import json
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import MagicMock, patch

import pytest

from db.sqlite_manager import MemoryRecord
from services.memory_service import MemoryService


@pytest.fixture
def mock_services():
    records = {}
    sqlite_mgr = MagicMock()

    def insert_memory(record):
        if record.id in records:
            return False
        records[record.id] = copy.deepcopy(record)
        return True

    def get_memory(memory_id):
        record = records.get(memory_id)
        return copy.deepcopy(record) if record else None

    def update_summary(memory_id, summary, sync_status="PENDING"):
        record = records.get(memory_id)
        if record is None:
            return False
        record.ai_summary = summary
        record.sync_status = sync_status
        return True

    def update_text(memory_id, text_content, sync_status="PENDING"):
        record = records.get(memory_id)
        if record is None:
            return False
        record.text_content = text_content
        record.sync_status = sync_status
        return True

    def update_status(memory_id, sync_status):
        record = records.get(memory_id)
        if record is None:
            return False
        record.sync_status = sync_status
        return True

    def update_analysis(
        memory_id,
        ai_summary,
        text_content,
        *,
        analysis_status="COMPLETED",
        sync_status="PENDING",
    ):
        record = records.get(memory_id)
        if record is None:
            return False
        record.ai_summary = ai_summary
        record.text_content = text_content
        record.analysis_status = analysis_status
        record.sync_status = sync_status
        return True

    def update_analysis_status(memory_id, analysis_status):
        record = records.get(memory_id)
        if record is None:
            return False
        record.analysis_status = analysis_status
        return True

    def compare_status(
        memory_id,
        *,
        expected_ai_summary,
        expected_text_content,
        sync_status,
    ):
        record = records.get(memory_id)
        if record is None:
            return False
        if (
            record.ai_summary != expected_ai_summary
            or record.text_content != expected_text_content
        ):
            return False
        record.sync_status = sync_status
        return True

    def get_all(limit=100, offset=0):
        values = sorted(records.values(), key=lambda item: item.created_at, reverse=True)
        return copy.deepcopy(values[offset : offset + limit])

    sqlite_mgr.insert_memory.side_effect = insert_memory
    sqlite_mgr.get_memory_by_id.side_effect = get_memory
    sqlite_mgr.update_memory_summary.side_effect = update_summary
    sqlite_mgr.update_memory_text_content.side_effect = update_text
    sqlite_mgr.update_memory_sync_status.side_effect = update_status
    sqlite_mgr.update_memory_analysis.side_effect = update_analysis
    sqlite_mgr.update_memory_analysis_status.side_effect = update_analysis_status
    sqlite_mgr.compare_and_set_memory_sync_status.side_effect = compare_status
    sqlite_mgr.get_all_memories.side_effect = get_all
    sqlite_mgr.get_memories_count.side_effect = lambda: len(records)
    sqlite_mgr.get_unsynced_memories_count.side_effect = lambda: sum(
        record.sync_status != "SYNCED" for record in records.values()
    )
    sqlite_mgr.get_memories_without_text.side_effect = lambda: [
        copy.deepcopy(record)
        for record in records.values()
        if not (record.text_content or "").strip()
    ]
    sqlite_mgr.delete_memory.side_effect = lambda memory_id: records.pop(
        memory_id, None
    ) is not None
    sqlite_mgr._records = records

    chroma_mgr = MagicMock()
    chroma_mgr.upsert_memory.return_value = True
    chroma_mgr.reset_collection.return_value = True
    chroma_mgr.delete_memory.return_value = True
    chroma_mgr.available = True
    chroma_mgr.get_all_memory_ids.return_value = []
    chroma_mgr.get_memory_count.return_value = 0

    ocr_engine = MagicMock()
    ocr_engine.extract_text.return_value = "extracted text"

    ai_client = MagicMock()
    ai_client.is_configured.return_value = True
    ai_client.analyze_image.return_value = "AI summary"
    ai_client.analyze_images.return_value = "Cluster summary"

    embedding_client = MagicMock()
    embedding_client.get_embedding.return_value = [0.1] * 384

    task_queue = MagicMock()
    task_queue.submit.return_value = object()
    return {
        "sqlite_manager": sqlite_mgr,
        "chroma_manager": chroma_mgr,
        "ocr_engine": ocr_engine,
        "ai_client": ai_client,
        "embedding_client": embedding_client,
        "task_queue": task_queue,
    }


def make_service(mock_services, *, with_queue=False):
    values = dict(mock_services)
    if not with_queue:
        values.pop("task_queue")
    return MemoryService(**values)


def add_record(mock_services, **overrides):
    values = {
        "id": "memory-1",
        "created_at": "2026-01-01 12:00:00",
        "image_path": "primary.png",
        "ai_summary": "summary",
        "app_name": "unknown",
        "text_content": "",
        "sync_status": "PENDING",
    }
    values.update(overrides)
    record = MemoryRecord(**values)
    assert mock_services["sqlite_manager"].insert_memory(record)
    return record


class TestMemoryServiceCreate:
    def test_prepare_screenshot_memory_is_immediately_readable(self, mock_services):
        service = make_service(mock_services)

        record = service.prepare_screenshot_memory("capture.png")

        assert record.id in mock_services["sqlite_manager"]._records
        assert record.analysis_status == "PROCESSING"
        assert record.ai_summary == ""
        assert record.image_path == "capture.png"

    def test_prepare_cluster_memory_is_immediately_readable(self, mock_services):
        service = make_service(mock_services)

        record = service.prepare_cluster_memory(["first.png", "second.png"])

        assert record.id in mock_services["sqlite_manager"]._records
        assert record.analysis_status == "PROCESSING"
        assert record.image_path == "first.png"
        assert json.loads(record.extra_images) == ["second.png"]

    def test_single_capture_runs_ocr_before_persisting(self, mock_services):
        service = make_service(mock_services)

        memory_id = service.create_memory("capture.png")

        record = mock_services["sqlite_manager"]._records[memory_id]
        assert record.text_content == "extracted text"
        assert record.analysis_status == "COMPLETED"
        assert record.sync_status == "SYNCED"
        mock_services["ocr_engine"].extract_text.assert_called_once_with("capture.png")
        kwargs = mock_services["chroma_manager"].upsert_memory.call_args.kwargs
        assert kwargs["text"] == "AI summary\n\nextracted text"

    def test_ocr_exception_does_not_block_creation(self, mock_services):
        mock_services["ocr_engine"].extract_text.side_effect = RuntimeError("OCR failed")
        service = make_service(mock_services)

        memory_id = service.create_memory("capture.png")

        record = mock_services["sqlite_manager"]._records[memory_id]
        assert record.text_content == ""
        assert record.ai_summary == "AI summary"

    def test_no_ai_uses_first_200_ocr_characters(self, mock_services):
        mock_services["ai_client"].is_configured.return_value = False
        mock_services["ocr_engine"].extract_text.return_value = "字" * 250
        service = make_service(mock_services)

        memory_id = service.create_memory("capture.png")

        record = mock_services["sqlite_manager"]._records[memory_id]
        assert record.ai_summary == "字" * 200

    def test_index_failure_keeps_sqlite_memory_as_failed(self, mock_services):
        mock_services["chroma_manager"].upsert_memory.return_value = False
        service = make_service(mock_services)

        memory_id = service.create_memory("capture.png")

        assert memory_id in mock_services["sqlite_manager"]._records
        assert (
            mock_services["sqlite_manager"]._records[memory_id].sync_status
            == "FAILED"
        )

    def test_cluster_ocr_preserves_image_order(self, mock_services):
        mock_services["ocr_engine"].extract_text.side_effect = ["first", None, "third"]
        service = make_service(mock_services)

        memory_id = service.create_cluster_memory(["1.png", "2.png", "3.png"])

        record = mock_services["sqlite_manager"]._records[memory_id]
        assert record.text_content == "first\n\nthird"
        assert json.loads(record.extra_images) == ["2.png", "3.png"]
        mock_services["ai_client"].analyze_images.assert_called_once()

    def test_cluster_processing_updates_the_prepared_record_in_place(self, mock_services):
        service = make_service(mock_services)
        pending = service.prepare_cluster_memory(["first.png", "second.png"])

        memory_id = service.create_cluster_memory(
            ["first.png", "second.png"],
            memory_id=pending.id,
        )

        assert memory_id == pending.id
        assert list(mock_services["sqlite_manager"]._records) == [pending.id]
        record = mock_services["sqlite_manager"]._records[pending.id]
        assert record.analysis_status == "COMPLETED"
        assert record.ai_summary == "Cluster summary"

    def test_empty_cluster_is_rejected(self, mock_services):
        service = make_service(mock_services)
        with pytest.raises(ValueError, match="at least one image"):
            service.create_cluster_memory([])

    def test_text_memory_skips_capture_ocr_and_ai(self, mock_services):
        service = make_service(mock_services)

        memory_id = service.create_text_memory("  手动记录的内容  ")

        record = mock_services["sqlite_manager"]._records[memory_id]
        assert record.memory_type == "text"
        assert record.image_path == ""
        assert record.ai_summary == "手动记录的内容"
        assert record.text_content is None
        assert record.sync_status == "SYNCED"
        mock_services["ocr_engine"].extract_text.assert_not_called()
        mock_services["ai_client"].analyze_image.assert_not_called()
        mock_services["ai_client"].analyze_images.assert_not_called()
        assert (
            mock_services["chroma_manager"].upsert_memory.call_args.kwargs["text"]
            == "手动记录的内容"
        )


class TestMemoryServiceAsync:
    def test_create_memory_async_requires_queue(self, mock_services):
        with pytest.raises(RuntimeError, match="not configured"):
            make_service(mock_services).create_memory_async("capture.png")

    def test_create_memory_async_submits_unique_task(self, mock_services):
        service = make_service(mock_services, with_queue=True)
        memory_id = service.create_memory_async("capture.png")

        args = mock_services["task_queue"].submit.call_args.args
        assert args[0].startswith("memory_creation_")
        assert callable(args[1])
        assert mock_services["sqlite_manager"]._records[memory_id].analysis_status == "PROCESSING"

    def test_create_cluster_memory_async_returns_processing_record(self, mock_services):
        service = make_service(mock_services, with_queue=True)

        memory_id = service.create_cluster_memory_async(["first.png", "second.png"])

        args = mock_services["task_queue"].submit.call_args.args
        assert args[0].startswith("cluster_memory_")
        assert callable(args[1])
        record = mock_services["sqlite_manager"]._records[memory_id]
        assert record.analysis_status == "PROCESSING"
        assert json.loads(record.extra_images) == ["second.png"]


class TestMemorySummaryUpdate:
    def test_update_trims_summary_and_queues_reindex(self, mock_services):
        add_record(mock_services, sync_status="SYNCED")
        service = make_service(mock_services, with_queue=True)

        updated = service.update_memory_summary("memory-1", "  new summary  ")

        assert updated.ai_summary == "new summary"
        assert updated.sync_status == "PENDING"
        mock_services["task_queue"].submit.assert_called_once()
        assert mock_services["task_queue"].submit.call_args.args[0].startswith(
            "memory_reindex_memory-1_"
        )

    @pytest.mark.parametrize("summary", ["", "   ", "x" * 4001])
    def test_update_rejects_invalid_summary(self, mock_services, summary):
        add_record(mock_services)
        service = make_service(mock_services, with_queue=True)
        with pytest.raises(ValueError):
            service.update_memory_summary("memory-1", summary)

    def test_identical_update_is_idempotent(self, mock_services):
        add_record(mock_services, ai_summary="same", sync_status="SYNCED")
        service = make_service(mock_services, with_queue=True)

        updated = service.update_memory_summary("memory-1", "same")

        assert updated.sync_status == "SYNCED"
        mock_services["sqlite_manager"].update_memory_summary.assert_not_called()
        mock_services["task_queue"].submit.assert_not_called()

    def test_missing_memory_returns_none(self, mock_services):
        service = make_service(mock_services, with_queue=True)
        assert service.update_memory_summary("missing", "new") is None

    def test_reindex_requests_for_same_memory_are_coalesced(self, mock_services):
        add_record(mock_services)
        service = make_service(mock_services, with_queue=True)

        assert service.schedule_memory_reindex("memory-1")
        assert service.schedule_memory_reindex("memory-1")

        mock_services["task_queue"].submit.assert_called_once()

    def test_pending_event_precedes_terminal_reindex_event(self, mock_services):
        class InlineTaskQueue:
            @staticmethod
            def submit(_task_id, func, *args):
                func(*args)
                return object()

        add_record(mock_services, ai_summary="old", sync_status="SYNCED")
        values = dict(mock_services)
        values["task_queue"] = InlineTaskQueue()
        service = MemoryService(**values)
        statuses = []

        with patch.object(
            service,
            "_emit_memory_updated",
            side_effect=lambda memory: statuses.append(memory.sync_status),
        ):
            updated = service.update_memory_summary("memory-1", "new")

        assert updated.sync_status == "PENDING"
        assert statuses == ["PENDING", "SYNCED"]

    def test_reindex_and_summary_update_are_serial_for_one_memory(
        self,
        mock_services,
    ):
        add_record(
            mock_services,
            ai_summary="old summary",
            text_content="",
            sync_status="PENDING",
        )
        old_embedding_started = Event()
        release_old_embedding = Event()

        def get_embedding(text):
            if text == "old summary":
                old_embedding_started.set()
                assert release_old_embedding.wait(timeout=2)
            return [0.1] * 384

        mock_services["embedding_client"].get_embedding.side_effect = get_embedding
        service = make_service(mock_services)

        with (
            patch.object(service, "_emit_memory_updated"),
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            old_reindex = executor.submit(service._reindex_memory, "memory-1")
            assert old_embedding_started.wait(timeout=2)
            summary_update = executor.submit(
                service.update_memory_summary,
                "memory-1",
                "new summary",
            )
            time.sleep(0.05)
            assert not summary_update.done()
            release_old_embedding.set()

            assert old_reindex.result(timeout=2) is True
            updated = summary_update.result(timeout=2)

        assert updated.ai_summary == "new summary"
        indexed_texts = [
            call.kwargs["text"]
            for call in mock_services["chroma_manager"].upsert_memory.call_args_list
        ]
        assert indexed_texts == ["old summary", "new summary"]


class TestMemoryServiceVectorRepair:
    def test_repair_skips_synced_existing_and_rebuilds_failed_existing(
        self,
        mock_services,
    ):
        add_record(
            mock_services,
            id="synced",
            ai_summary="current",
            sync_status="SYNCED",
        )
        add_record(
            mock_services,
            id="failed",
            ai_summary="needs repair",
            sync_status="FAILED",
        )
        mock_services["chroma_manager"].get_all_memory_ids.return_value = [
            "synced",
            "failed",
        ]
        service = make_service(mock_services)

        result = service.repair_vector_index()

        assert result["indexed"] == 1
        assert result["skipped"] == 1
        assert result["failed"] == 0
        assert (
            mock_services["sqlite_manager"]._records["failed"].sync_status
            == "SYNCED"
        )

    def test_force_repair_rebuilds_all(self, mock_services):
        add_record(mock_services, sync_status="SYNCED")
        service = make_service(mock_services)

        result = service.repair_vector_index(force_rebuild=True)

        assert result["rebuilt"] is True
        assert result["indexed"] == 1
        mock_services["chroma_manager"].reset_collection.assert_called_once()

    def test_conditional_repair_skips_when_counts_and_status_match(self, mock_services):
        add_record(mock_services, sync_status="SYNCED")
        mock_services["chroma_manager"].get_memory_count.return_value = 1
        service = make_service(mock_services, with_queue=True)

        assert service.maybe_schedule_vector_index_repair() is False
        mock_services["task_queue"].submit.assert_not_called()

    def test_conditional_repair_queues_failed_row_without_running_inline(
        self,
        mock_services,
    ):
        add_record(mock_services, sync_status="FAILED")
        mock_services["chroma_manager"].get_memory_count.return_value = 1
        service = make_service(mock_services, with_queue=True)

        assert service.maybe_schedule_vector_index_repair() is True
        mock_services["task_queue"].submit.assert_called_once_with(
            "vector_index_repair",
            service.repair_vector_index,
        )

    def test_legacy_async_repair_name_delegates_to_conditional_scheduler(
        self,
        mock_services,
    ):
        service = make_service(mock_services, with_queue=True)
        with patch.object(
            service,
            "maybe_schedule_vector_index_repair",
            return_value=True,
        ) as scheduler:
            assert service.repair_vector_index_async() is True
        scheduler.assert_called_once_with()

    def test_conditional_repair_scheduler_failure_is_non_fatal(
        self,
        mock_services,
    ):
        add_record(mock_services, sync_status="PENDING")
        mock_services["task_queue"].submit.side_effect = RuntimeError("closed")
        service = make_service(mock_services, with_queue=True)

        assert service.maybe_schedule_vector_index_repair() is False


class TestOCRBackfill:
    def test_backfill_updates_empty_text_and_reindexes(self, mock_services):
        add_record(
            mock_services,
            extra_images=json.dumps(["second.png"]),
            sync_status="SYNCED",
        )
        mock_services["ocr_engine"].extract_text.side_effect = ["first", "second"]
        service = make_service(mock_services)

        result = service.backfill_ocr()

        assert result == {
            "status": "completed",
            "total": 1,
            "processed": 1,
            "succeeded": 1,
            "updated": 1,
            "skipped": 0,
            "failed": 0,
            "index_failed": 0,
        }
        record = mock_services["sqlite_manager"]._records["memory-1"]
        assert record.text_content == "first\n\nsecond"
        assert record.sync_status == "SYNCED"

    def test_backfill_empty_result_is_skipped(self, mock_services):
        add_record(mock_services)
        mock_services["ocr_engine"].extract_text.return_value = None
        service = make_service(mock_services)

        result = service.backfill_ocr()

        assert result["processed"] == 1
        assert result["skipped"] == 1
        assert result["updated"] == 0

    def test_backfill_exception_counts_failure_and_continues(self, mock_services):
        add_record(mock_services, id="bad", image_path="bad.png")
        add_record(mock_services, id="good", image_path="good.png")
        mock_services["ocr_engine"].extract_text.side_effect = [
            RuntimeError("bad image"),
            "recognized",
        ]
        service = make_service(mock_services)

        result = service.backfill_ocr()

        assert result["processed"] == 2
        assert result["failed"] == 1
        assert result["updated"] == 1

    def test_backfill_skips_text_memories_without_calling_ocr(self, mock_services):
        add_record(
            mock_services,
            image_path="",
            ai_summary="手动记录",
            text_content=None,
            memory_type="text",
        )
        service = make_service(mock_services)

        result = service.backfill_ocr()

        assert result["processed"] == 1
        assert result["skipped"] == 1
        assert result["updated"] == 0
        mock_services["ocr_engine"].extract_text.assert_not_called()


class TestMemoryServiceQueryAndDelete:
    def test_delete_memory_success(self, mock_services):
        add_record(mock_services)
        service = make_service(mock_services)
        assert service.delete_memory("memory-1") is True
        assert "memory-1" not in mock_services["sqlite_manager"]._records

    def test_delete_succeeds_when_chroma_cleanup_fails(self, mock_services):
        add_record(mock_services)
        mock_services["chroma_manager"].delete_memory.return_value = False
        service = make_service(mock_services)
        assert service.delete_memory("memory-1") is True
        assert "memory-1" not in mock_services["sqlite_manager"]._records

    def test_delete_waits_for_inflight_reindex_before_vector_cleanup(
        self,
        mock_services,
    ):
        add_record(mock_services, sync_status="PENDING")
        embedding_started = Event()
        release_embedding = Event()

        def get_embedding(_text):
            embedding_started.set()
            assert release_embedding.wait(timeout=2)
            return [0.1] * 384

        mock_services["embedding_client"].get_embedding.side_effect = get_embedding
        service = make_service(mock_services)

        with ThreadPoolExecutor(max_workers=2) as executor:
            reindex = executor.submit(service._reindex_memory, "memory-1")
            assert embedding_started.wait(timeout=2)
            deletion = executor.submit(service.delete_memory, "memory-1")
            time.sleep(0.05)
            assert not deletion.done()

            release_embedding.set()
            assert reindex.result(timeout=2) is True
            assert deletion.result(timeout=2) is True

        method_names = [call[0] for call in mock_services["chroma_manager"].method_calls]
        assert method_names.index("upsert_memory") < method_names.index("delete_memory")
        assert "memory-1" not in mock_services["sqlite_manager"]._records

    def test_get_memory_and_recent(self, mock_services):
        add_record(mock_services)
        service = make_service(mock_services)
        assert service.get_memory("memory-1").id == "memory-1"
        assert service.get_recent_memories(limit=50)[0].id == "memory-1"
        assert service.get_active_count() == 0
