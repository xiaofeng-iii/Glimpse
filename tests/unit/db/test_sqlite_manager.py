"""
Unit tests for db/sqlite_manager.py
"""
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
import sqlite3


@pytest.fixture
def temp_db_path(tmp_path):
    return tmp_path / "test_glimpse.db"


@pytest.fixture
def mock_path_manager(tmp_path):
    pm = MagicMock()
    pm.sqlite_path = tmp_path / "test_glimpse.db"
    pm.database_dir = tmp_path
    return pm


class TestMemoryRecord:
    def test_default_values(self):
        from db.sqlite_manager import MemoryRecord
        record = MemoryRecord(
            id="test-1",
            created_at="2026-01-01 12:00:00",
            image_path="/path/to/img.png",
            ai_summary="A summary",
            app_name="chrome",
        )
        assert record.id == "test-1"
        assert record.sync_status == "PENDING"
        assert record.text_content is None

    def test_to_dict(self):
        from db.sqlite_manager import MemoryRecord
        record = MemoryRecord(
            id="test-1",
            created_at="2026-01-01 12:00:00",
            image_path="/path.png",
            ai_summary="summary",
            app_name="chrome",
        )
        d = record.to_dict()
        assert d["id"] == "test-1"
        assert "sync_status" in d

    def test_from_row(self):
        from db.sqlite_manager import MemoryRecord
        row = ("id-123", "2026-05-25", "img.png", "sum", "app", "text", "DONE")
        record = MemoryRecord.from_row(row)
        assert record.id == "id-123"
        assert record.sync_status == "DONE"

    def test_from_row_with_extra_images(self):
        from db.sqlite_manager import MemoryRecord
        row = ("id-123", "2026-05-25", "img.png", "sum", "app", "text", '["extra1.png"]', "DONE")
        record = MemoryRecord.from_row(row)
        assert record.id == "id-123"
        assert record.extra_images == '["extra1.png"]'
        assert record.sync_status == "DONE"

    def test_from_row_partial(self):
        from db.sqlite_manager import MemoryRecord
        row = ("id-123", "2026-05-25", "img.png", "sum", "app")
        record = MemoryRecord.from_row(row)
        assert record.text_content is None
        assert record.sync_status == "PENDING"


class TestSQLiteManagerInit:
    def test_init_creates_connection(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager
        mgr = SQLiteManager(mock_path_manager)
        assert mgr._conn is not None
        mgr.close()

    def test_creates_tables(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager
        mgr = SQLiteManager(mock_path_manager)
        cursor = mgr._conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memories'")
        assert cursor.fetchone() is not None
        mgr.close()

    def test_initial_count_zero(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager
        mgr = SQLiteManager(mock_path_manager)
        assert mgr.get_memories_count() == 0
        mgr.close()

    def test_migrates_legacy_database_without_sync_status(self, mock_path_manager):
        connection = sqlite3.connect(str(mock_path_manager.sqlite_path))
        connection.execute(
            """
            CREATE TABLE memories (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                image_path TEXT NOT NULL,
                ai_summary TEXT,
                app_name TEXT,
                text_content TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO memories
            (id, created_at, image_path, ai_summary, app_name, text_content)
            VALUES ('legacy', '2026-01-01', 'legacy.png', 'summary', 'app', '')
            """
        )
        connection.commit()
        connection.close()

        from db.sqlite_manager import SQLiteManager

        mgr = SQLiteManager(mock_path_manager)
        columns = {
            row[1] for row in mgr._conn.execute("PRAGMA table_info(memories)")
        }
        assert {"extra_images", "sync_status"}.issubset(columns)
        assert mgr.get_memory_by_id("legacy").sync_status == "PENDING"
        mgr.close()


class TestSQLiteManagerInsert:
    def test_insert_memory_success(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager, MemoryRecord
        mgr = SQLiteManager(mock_path_manager)
        record = MemoryRecord(
            id="test-insert-1",
            created_at="2026-01-01 12:00:00",
            image_path="/img.png",
            ai_summary="Test summary",
            app_name="test",
        )
        result = mgr.insert_memory(record)
        assert result is True
        assert mgr.get_memories_count() == 1
        mgr.close()

    def test_insert_memory_duplicate_id_fails(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager, MemoryRecord
        mgr = SQLiteManager(mock_path_manager)
        record = MemoryRecord(
            id="dup-1",
            created_at="2026-01-01 12:00:00",
            image_path="/img.png",
            ai_summary="sum",
            app_name="test",
        )
        mgr.insert_memory(record)
        result = mgr.insert_memory(record)
        assert result is False
        mgr.close()


class TestSQLiteManagerQuery:
    def test_get_memory_by_id_found(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager, MemoryRecord
        mgr = SQLiteManager(mock_path_manager)
        record = MemoryRecord(
            id="q-1",
            created_at="2026-01-01 12:00:00",
            image_path="/img.png",
            ai_summary="Found me",
            app_name="test",
        )
        mgr.insert_memory(record)
        found = mgr.get_memory_by_id("q-1")
        assert found is not None
        assert found.ai_summary == "Found me"
        mgr.close()

    def test_get_memory_by_id_not_found(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager
        mgr = SQLiteManager(mock_path_manager)
        found = mgr.get_memory_by_id("nonexistent")
        assert found is None
        mgr.close()

    def test_get_all_memories(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager, MemoryRecord
        mgr = SQLiteManager(mock_path_manager)
        for i in range(5):
            record = MemoryRecord(
                id=f"all-{i}",
                created_at=f"2026-01-0{i+1} 12:00:00",
                image_path=f"/img{i}.png",
                ai_summary=f"Summary {i}",
                app_name="test",
            )
            mgr.insert_memory(record)
        results = mgr.get_all_memories(limit=10)
        assert len(results) == 5
        mgr.close()

    def test_get_all_memories_limit_offset(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager, MemoryRecord
        mgr = SQLiteManager(mock_path_manager)
        for i in range(5):
            record = MemoryRecord(
                id=f"lo-{i}",
                created_at=f"2026-01-0{i+1} 12:00:00",
                image_path=f"/img{i}.png",
                ai_summary=f"S{i}",
                app_name="test",
            )
            mgr.insert_memory(record)
        results = mgr.get_all_memories(limit=2, offset=0)
        assert len(results) == 2
        mgr.close()

    def test_filters_memories_by_inclusive_local_date_range(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager, MemoryRecord

        mgr = SQLiteManager(mock_path_manager)
        for memory_id, created_at in [
            ("before", "2026-07-31 23:59:59"),
            ("start", "2026-08-01 00:00:00"),
            ("end", "2026-08-24 23:59:59"),
            ("after", "2026-08-25 00:00:00"),
        ]:
            mgr.insert_memory(
                MemoryRecord(
                    id=memory_id,
                    created_at=created_at,
                    image_path="/img.png",
                    ai_summary="filter me",
                    app_name="test",
                )
            )

        results = mgr.get_all_memories(
            limit=10,
            created_after="2026-08-01 00:00:00",
            created_before="2026-08-25 00:00:00",
        )
        assert [memory.id for memory in results] == ["end", "start"]
        assert mgr.get_memories_count(
            created_after="2026-08-01 00:00:00",
            created_before="2026-08-25 00:00:00",
        ) == 2
        assert mgr.get_memory_ids(
            created_after="2026-08-01 00:00:00",
            created_before="2026-08-25 00:00:00",
        ) == ["end", "start"]
        assert [memory.id for memory in mgr.search_memories(
            "filter",
            created_after="2026-08-01 00:00:00",
            created_before="2026-08-25 00:00:00",
        )] == ["start", "end"]
        mgr.close()


class TestSQLiteManagerSearch:
    def test_search_memories_text(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager, MemoryRecord
        mgr = SQLiteManager(mock_path_manager)
        record = MemoryRecord(
            id="s-1",
            created_at="2026-01-01 12:00:00",
            image_path="/img.png",
            ai_summary="machine learning",
            app_name="test",
        )
        mgr.insert_memory(record)
        results = mgr.search_memories("machine")
        assert len(results) >= 1
        mgr.close()

    def test_search_memories_no_match(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager
        mgr = SQLiteManager(mock_path_manager)
        results = mgr.search_memories("zzzzz_nonexistent")
        assert len(results) == 0
        mgr.close()


class TestSQLiteManagerUpdateDelete:
    def test_update_memory_summary(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager, MemoryRecord
        mgr = SQLiteManager(mock_path_manager)
        record = MemoryRecord(
            id="u-1",
            created_at="2026-01-01",
            image_path="/img.png",
            ai_summary="original",
            app_name="test",
        )
        mgr.insert_memory(record)
        mgr.update_memory_summary("u-1", "updated")
        found = mgr.get_memory_by_id("u-1")
        assert found.ai_summary == "updated"
        assert found.sync_status == "PENDING"
        assert mgr.search_memories("original") == []
        assert [item.id for item in mgr.search_memories("updated")] == ["u-1"]
        mgr.close()

    def test_update_memory_text_content_refreshes_fts_and_status(
        self,
        mock_path_manager,
    ):
        from db.sqlite_manager import MemoryRecord, SQLiteManager

        mgr = SQLiteManager(mock_path_manager)
        mgr.insert_memory(
            MemoryRecord(
                id="ocr-1",
                created_at="2026-01-01",
                image_path="/img.png",
                ai_summary="summary",
                app_name="test",
                text_content="oldword",
                sync_status="SYNCED",
            )
        )

        assert mgr.update_memory_text_content("ocr-1", "newword") is True
        found = mgr.get_memory_by_id("ocr-1")
        assert found.text_content == "newword"
        assert found.sync_status == "PENDING"
        assert mgr.search_memories("oldword") == []
        assert [item.id for item in mgr.search_memories("newword")] == ["ocr-1"]

        assert mgr.update_memory_sync_status("ocr-1", "SYNCED") is True
        assert mgr.get_unsynced_memories_count() == 0
        mgr.close()

    def test_sync_status_compare_and_set_requires_same_summary_and_ocr(
        self,
        mock_path_manager,
    ):
        from db.sqlite_manager import MemoryRecord, SQLiteManager

        mgr = SQLiteManager(mock_path_manager)
        mgr.insert_memory(
            MemoryRecord(
                id="cas-1",
                created_at="2026-01-01",
                image_path="/img.png",
                ai_summary="summary-v1",
                app_name="test",
                text_content="ocr-v1",
                sync_status="PENDING",
            )
        )

        assert mgr.compare_and_set_memory_sync_status(
            "cas-1",
            expected_ai_summary="summary-v1",
            expected_text_content="ocr-v1",
            sync_status="SYNCED",
        )
        assert mgr.get_memory_by_id("cas-1").sync_status == "SYNCED"

        assert mgr.update_memory_summary("cas-1", "summary-v2")
        assert not mgr.compare_and_set_memory_sync_status(
            "cas-1",
            expected_ai_summary="summary-v1",
            expected_text_content="ocr-v1",
            sync_status="SYNCED",
        )
        assert mgr.get_memory_by_id("cas-1").sync_status == "PENDING"

        assert mgr.update_memory_text_content("cas-1", "ocr-v2")
        assert not mgr.compare_and_set_memory_sync_status(
            "cas-1",
            expected_ai_summary="summary-v2",
            expected_text_content="ocr-v1",
            sync_status="FAILED",
        )
        assert mgr.get_memory_by_id("cas-1").sync_status == "PENDING"
        mgr.close()

    def test_update_nonexistent_returns_false(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager
        mgr = SQLiteManager(mock_path_manager)
        result = mgr.update_memory_summary("nonexistent", "x")
        assert result is False
        mgr.close()

    def test_delete_memory(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager, MemoryRecord
        mgr = SQLiteManager(mock_path_manager)
        record = MemoryRecord(
            id="d-1",
            created_at="2026-01-01",
            image_path="/img.png",
            ai_summary="to delete",
            app_name="test",
        )
        mgr.insert_memory(record)
        assert mgr.delete_memory("d-1") is True
        assert mgr.get_memory_by_id("d-1") is None
        mgr.close()

    def test_delete_nonexistent_returns_false(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager
        mgr = SQLiteManager(mock_path_manager)
        assert mgr.delete_memory("nonexistent") is False
        mgr.close()


class TestSQLiteManagerGlobal:
    def test_global_is_none_initially(self):
        from db.sqlite_manager import sqlite_manager
        assert sqlite_manager is None
