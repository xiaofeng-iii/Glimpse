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

    def test_filters_browse_count_ids_and_search_by_memory_type(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager, MemoryRecord

        mgr = SQLiteManager(mock_path_manager)
        mgr.insert_memory(
            MemoryRecord(
                id="screenshot",
                created_at="2026-08-24 10:00:00",
                image_path="/img.png",
                ai_summary="shared filter phrase",
                app_name="test",
            )
        )
        mgr.insert_memory(
            MemoryRecord(
                id="text",
                created_at="2026-08-24 11:00:00",
                image_path="",
                ai_summary="shared filter phrase",
                app_name="Glimpse",
                memory_type="text",
            )
        )

        assert [memory.id for memory in mgr.get_all_memories(memory_type="text")] == ["text"]
        assert mgr.get_memories_count(memory_type="text") == 1
        assert mgr.get_memory_ids(memory_type="text") == ["text"]
        assert [
            memory.id for memory in mgr.search_memories("shared", memory_type="text")
        ] == ["text"]
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

    def test_search_covers_user_text(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager, MemoryRecord
        mgr = SQLiteManager(mock_path_manager)
        record = MemoryRecord(
            id="s-note-1",
            created_at="2026-01-01 12:00:00",
            image_path="/img.png",
            ai_summary="AI summary of the photo",
            app_name="test",
            user_text="typed quarantine keyword",
        )
        mgr.insert_memory(record)

        # FTS 索引包含 user_text（英文分词可靠）。
        assert [item.id for item in mgr.search_memories("quarantine")] == ["s-note-1"]

        # 中文无法被 FTS 默认分词，走 LIKE 回退时同样命中 user_text。
        assert mgr.search_memories("typed quarantine")[0].id == "s-note-1"

        updated = mgr.get_memory_by_id("s-note-1")
        assert updated.user_text == "typed quarantine keyword"
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

    def test_update_memory_user_text_refreshes_fts_and_status(
        self,
        mock_path_manager,
    ):
        from db.sqlite_manager import MemoryRecord, SQLiteManager

        mgr = SQLiteManager(mock_path_manager)
        mgr.insert_memory(
            MemoryRecord(
                id="note-u-1",
                created_at="2026-01-01",
                image_path="/img.png",
                ai_summary="summary",
                app_name="test",
                user_text="original note words",
            )
        )
        assert mgr.update_memory_user_text("note-u-1", "revised note words") is True

        found = mgr.get_memory_by_id("note-u-1")
        assert found.user_text == "revised note words"
        assert found.sync_status == "PENDING"
        assert mgr.search_memories("original") == []
        assert [item.id for item in mgr.search_memories("revised")] == ["note-u-1"]
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


def _insert(mgr, memory_id, **overrides):
    from db.sqlite_manager import MemoryRecord

    values = {
        "id": memory_id,
        "created_at": "2026-01-01 12:00:00",
        "image_path": "/img.png",
        "ai_summary": f"summary of {memory_id}",
        "app_name": "test",
    }
    values.update(overrides)
    assert mgr.insert_memory(MemoryRecord(**values)) is True


class TestSQLiteManagerTags:
    def test_init_is_idempotent_and_migrates_legacy_database(self, mock_path_manager):
        import sqlite3 as sqlite

        connection = sqlite.connect(str(mock_path_manager.sqlite_path))
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

        first = SQLiteManager(mock_path_manager)
        first.close()
        mgr = SQLiteManager(mock_path_manager)

        tables = {
            row[0]
            for row in mgr._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {"tags", "memory_tags"}.issubset(tables)
        assert mgr.get_memory_by_id("legacy").tags == []
        mgr.close()

    def test_set_tags_reuses_entities_case_insensitively(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager

        mgr = SQLiteManager(mock_path_manager)
        _insert(mgr, "m-1")
        _insert(mgr, "m-2")

        first = mgr.set_memory_tags("m-1", ["Work", "灵感"])
        second = mgr.set_memory_tags("m-2", ["work"])

        assert [tag.name for tag in first.tags] == ["Work", "灵感"]
        # 第二条记忆复用已存在的 "Work" 实体（ASCII 大小写不敏感）。
        assert [tag.id for tag in second.tags] == [first.tags[0].id]
        assert {tag["name"] for tag in mgr.get_all_tags()} == {"Work", "灵感"}
        mgr.close()

    def test_set_tags_replaces_all_and_empty_list_clears(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager

        mgr = SQLiteManager(mock_path_manager)
        _insert(mgr, "m-1")

        mgr.set_memory_tags("m-1", ["a", "b"])
        replaced = mgr.set_memory_tags("m-1", ["c"])
        assert [tag.name for tag in replaced.tags] == ["c"]
        # 整体替换后被顶掉的 a/b 失去全部关联，随关联一并删除
        assert [tag["name"] for tag in mgr.get_all_tags()] == ["c"]

        cleared = mgr.set_memory_tags("m-1", [])
        assert cleared.tags == []
        assert mgr.get_all_tags() == []
        mgr.close()

    def test_tag_is_deleted_with_its_last_association(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager

        mgr = SQLiteManager(mock_path_manager)
        _insert(mgr, "m-1")
        _insert(mgr, "m-2")

        # 共享标签：两条记忆都在用时，取消其中一条不影响另一条
        mgr.set_memory_tags("m-1", ["shared"])
        mgr.set_memory_tags("m-2", ["shared", "solo"])
        mgr.set_memory_tags("m-2", ["solo"])

        tags = {tag["name"]: tag for tag in mgr.get_all_tags()}
        assert set(tags) == {"shared", "solo"}
        assert tags["shared"]["memory_count"] == 1

        # 最后一条关联被取消后，标签实体随之删除
        mgr.set_memory_tags("m-1", [])
        mgr.set_memory_tags("m-2", [])
        assert mgr.get_all_tags() == []
        mgr.close()

    def test_delete_memory_removes_links_and_orphaned_tags(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager

        mgr = SQLiteManager(mock_path_manager)
        _insert(mgr, "m-1")
        _insert(mgr, "m-2")
        mgr.set_memory_tags("m-1", ["shared"])
        mgr.set_memory_tags("m-2", ["shared", "solo"])

        assert mgr.delete_memory("m-1") is True

        # shared 仍被 m-2 关联而保留；solo 不受影响
        links = list(
            mgr._conn.execute(
                "SELECT memory_id FROM memory_tags WHERE memory_id = 'm-1'"
            )
        )
        assert links == []
        tags = {tag["name"]: tag for tag in mgr.get_all_tags()}
        assert tags["shared"]["memory_count"] == 1
        assert tags["solo"]["memory_count"] == 1

        # 删除最后的关联记忆，标签一并消失
        assert mgr.delete_memory("m-2") is True
        assert mgr.get_all_tags() == []
        mgr.close()

    def test_set_tags_on_missing_memory_returns_none(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager

        mgr = SQLiteManager(mock_path_manager)
        assert mgr.set_memory_tags("missing", ["a"]) is None
        assert mgr.get_all_tags() == []
        mgr.close()

    def test_set_tags_rejects_invalid_names(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager

        mgr = SQLiteManager(mock_path_manager)
        _insert(mgr, "m-1")
        with pytest.raises(ValueError):
            mgr.set_memory_tags("m-1", ["  "])
        with pytest.raises(ValueError):
            mgr.set_memory_tags("m-1", [f"t{i}" for i in range(11)])
        mgr.close()

    def test_tag_update_does_not_touch_content_fts_or_sync_status(
        self, mock_path_manager
    ):
        from db.sqlite_manager import SQLiteManager

        mgr = SQLiteManager(mock_path_manager)
        _insert(
            mgr,
            "m-1",
            ai_summary="stable unique phrase",
            sync_status="SYNCED",
        )

        mgr.set_memory_tags("m-1", ["工作"])
        updated = mgr.get_memory_by_id("m-1")

        assert updated.sync_status == "SYNCED"
        assert updated.ai_summary == "stable unique phrase"
        # FTS 内容未因标签变更而重写，搜索依旧命中同一行。
        assert [m.id for m in mgr.search_memories("stable unique")] == ["m-1"]
        mgr.close()

    def test_read_paths_return_hydrated_tags(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager

        mgr = SQLiteManager(mock_path_manager)
        _insert(mgr, "m-1", ai_summary="hydration probe keyword")
        mgr.set_memory_tags("m-1", ["beta", "Alpha"])

        expected = ["Alpha", "beta"]  # 按 name COLLATE NOCASE 排序
        assert [t.name for t in mgr.get_memory_by_id("m-1").tags] == expected
        assert [t.name for t in mgr.get_all_memories()[0].tags] == expected
        assert [t.name for t in mgr.search_memories("hydration probe")[0].tags] == expected
        # LIKE 回退路径同样返回标签。
        assert [t.name for t in mgr.search_memories("hydration probe keyword")[0].tags] == expected

        d = mgr.get_memory_by_id("m-1").to_dict()
        assert d["tags"] == [
            {"id": d["tags"][0]["id"], "name": "Alpha"},
            {"id": d["tags"][1]["id"], "name": "beta"},
        ]
        mgr.close()

    def test_tag_filter_or_semantics_and_and_combination(self, mock_path_manager):
        from db.sqlite_manager import SQLiteManager

        mgr = SQLiteManager(mock_path_manager)
        _insert(mgr, "m-work", created_at="2026-08-01 10:00:00")
        _insert(mgr, "m-idea", created_at="2026-08-02 10:00:00")
        _insert(mgr, "m-both", created_at="2026-08-03 10:00:00")
        _insert(mgr, "m-none", created_at="2026-08-04 10:00:00")

        work = mgr.set_memory_tags("m-work", ["工作"]).tags[0]
        idea = mgr.set_memory_tags("m-idea", ["灵感"]).tags[0]
        mgr.set_memory_tags("m-both", ["工作", "灵感"])

        # 多标签 OR：关联任意一个选中标签即命中。
        or_ids = {
            m.id
            for m in mgr.get_all_memories(tag_ids=[work.id, idea.id])
        }
        assert or_ids == {"m-work", "m-idea", "m-both"}
        assert mgr.get_memories_count(tag_ids=[work.id, idea.id]) == 3
        assert set(mgr.get_memory_ids(tag_ids=[work.id, idea.id])) == or_ids

        # 标签条件与日期条件之间为 AND。
        narrowed = {
            m.id
            for m in mgr.get_all_memories(
                created_after="2026-08-02 00:00:00",
                created_before="2026-08-04 00:00:00",
                tag_ids=[work.id, idea.id],
            )
        }
        assert narrowed == {"m-idea", "m-both"}
        assert mgr.get_memories_count(
            created_after="2026-08-02 00:00:00",
            created_before="2026-08-04 00:00:00",
            tag_ids=[work.id, idea.id],
        ) == 2

        # 搜索路径同样应用标签过滤。
        searched = {
            m.id
            for m in mgr.search_memories("summary", tag_ids=[idea.id])
        }
        assert searched == {"m-idea", "m-both"}

        # 中文查询走 LIKE 回退，标签过滤依然生效。
        _insert(mgr, "m-zh", ai_summary="周会纪要")
        mgr.set_memory_tags("m-zh", ["灵感"])
        assert [m.id for m in mgr.search_memories("周会", tag_ids=[idea.id])] == [
            "m-zh"
        ]
        assert mgr.search_memories("周会", tag_ids=[work.id]) == []

        # 空列表等同于无标签筛选。
        assert mgr.get_memories_count(tag_ids=[]) == 5
        mgr.close()
