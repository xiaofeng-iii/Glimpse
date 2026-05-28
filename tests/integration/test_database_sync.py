"""
双数据库同步集成测试

验证：SQLite 与 ChromaDB 之间的数据一致性
"""
import pytest


class TestDatabaseSync:
    """测试 SQLite 和 ChromaDB 双数据库同步"""

    def test_both_databases_contain_entry_after_create(
        self, memory_service, sample_image_path, sqlite_manager, chroma_manager
    ):
        """创建记忆后，两个数据库都应包含该条目"""
        memory_id = memory_service.create_memory(sample_image_path)

        sqlite_record = sqlite_manager.get_memory_by_id(memory_id)
        chroma_ids = chroma_manager.get_all_memory_ids()

        assert sqlite_record is not None
        assert memory_id in chroma_ids

    def test_both_databases_remove_entry_after_delete(
        self, memory_service, sample_image_path, sqlite_manager, chroma_manager
    ):
        """删除记忆后，两个数据库都应移除该条目"""
        memory_id = memory_service.create_memory(sample_image_path)

        memory_service.delete_memory(memory_id)

        sqlite_record = sqlite_manager.get_memory_by_id(memory_id)
        assert sqlite_record is None

        chroma_ids = chroma_manager.get_all_memory_ids()
        assert memory_id not in chroma_ids

    def test_count_consistency_after_create(
        self, memory_service, sample_image_path, sqlite_manager, chroma_manager
    ):
        """创建记忆后，两个数据库的计数应一致"""
        for i in range(3):
            memory_service.create_memory(sample_image_path, app_name=f"count_{i}")

        sqlite_count = sqlite_manager.get_memories_count()
        chroma_count = chroma_manager.get_memory_count()

        assert sqlite_count == 3
        assert chroma_count == 3

    def test_sync_status_persisted(self, memory_service, sample_image_path):
        """记忆的 sync_status 字段应被正确保存"""
        memory_id = memory_service.create_memory(sample_image_path)
        record = memory_service.get_memory(memory_id)

        assert record is not None
        assert record.sync_status is not None

    def test_insert_to_sqlite_independent(self, sqlite_manager, sample_image_path):
        """直接插入 SQLite 也应正常工作"""
        from db.sqlite_manager import MemoryRecord
        import uuid
        import time

        memory_id = str(uuid.uuid4())
        created_at = time.strftime("%Y-%m-%d %H:%M:%S")

        record = MemoryRecord(
            id=memory_id,
            created_at=created_at,
            image_path=sample_image_path,
            ai_summary="直接插入测试",
            app_name="test",
            text_content="直接插入的文本",
            sync_status="PENDING",
        )

        success = sqlite_manager.insert_memory(record)
        assert success is True

        fetched = sqlite_manager.get_memory_by_id(memory_id)
        assert fetched is not None
        assert fetched.ai_summary == "直接插入测试"

    def test_chroma_crud_independent(self, chroma_manager):
        """直接对 ChromaDB 进行 CRUD 操作也应正常"""
        import uuid

        memory_id = str(uuid.uuid4())
        embedding = [0.1] * 384

        chroma_manager.add_memory(
            memory_id=memory_id,
            text="Chroma 独立测试",
            embedding=embedding,
            metadata={"type": "test"},
        )

        ids = chroma_manager.get_all_memory_ids()
        assert memory_id in ids

        chroma_manager.delete_memory(memory_id)

        ids_after = chroma_manager.get_all_memory_ids()
        assert memory_id not in ids_after

    def test_sqlite_update_summary(self, memory_service, sample_image_path, sqlite_manager):
        """SQLite 更新摘要功能应正常"""
        memory_id = memory_service.create_memory(sample_image_path)

        success = sqlite_manager.update_memory_summary(memory_id, "更新后的摘要")
        assert success is True

        record = sqlite_manager.get_memory_by_id(memory_id)
        assert record.ai_summary == "更新后的摘要"

    def test_chroma_update_text(self, memory_service, sample_image_path, chroma_manager):
        """ChromaDB 更新文本功能应正常"""
        memory_id = memory_service.create_memory(sample_image_path)

        success = chroma_manager.update_memory(
            memory_id=memory_id,
            text="更新后的文本",
        )
        assert success is True

    def test_delete_nonexistent_memory_is_safe(self, memory_service):
        """删除不存在的记忆不应抛出异常（ChromaDB 对不存在 ID 返回 True）"""
        try:
            memory_service.delete_memory("non-existent-id-12345")
        except Exception:
            pytest.fail("Deleting non-existent memory should not raise")
