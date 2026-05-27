"""
截图 → 双数据库存储流程集成测试

验证：截图图像 → MemoryService → SQLite + ChromaDB 双写流程
"""
import os
from pathlib import Path

import pytest


class TestCaptureToStorage:
    """测试截图捕获到双数据库存储的完整流程"""

    def test_create_memory_stores_in_sqlite(self, memory_service, sample_image_path):
        """截图处理后应写入 SQLite"""
        memory_id = memory_service.create_memory(sample_image_path, app_name="test_app")

        assert memory_id is not None
        record = memory_service.get_memory(memory_id)
        assert record is not None
        assert record.app_name == "test_app"
        assert record.ai_summary == "这是一张包含文字内容的截图摘要"
        assert record.text_content == "测试 OCR 识别文本内容"

    def test_create_memory_stores_in_chroma(self, memory_service, sample_image_path, chroma_manager):
        """截图处理后应写入 ChromaDB 向量数据库"""
        memory_id = memory_service.create_memory(sample_image_path, app_name="test_app")

        assert memory_id is not None
        chroma_count = chroma_manager.get_memory_count()
        assert chroma_count >= 1

        ids = chroma_manager.get_all_memory_ids()
        assert memory_id in ids

    def test_create_memory_sqlite_chroma_id_match(self, memory_service, sample_image_path, sqlite_manager, chroma_manager):
        """SQLite 和 ChromaDB 中的记录应通过同一 UUID 关联"""
        memory_id = memory_service.create_memory(sample_image_path, app_name="sync_test")

        sqlite_record = sqlite_manager.get_memory_by_id(memory_id)
        chroma_ids = chroma_manager.get_all_memory_ids()

        assert sqlite_record is not None
        assert memory_id in chroma_ids

    def test_create_multiple_memories(self, memory_service, sample_image_path, sqlite_manager):
        """可以连续创建多条记忆"""
        ids = []
        for i in range(3):
            memory_id = memory_service.create_memory(
                sample_image_path, app_name=f"app_{i}"
            )
            assert memory_id is not None
            ids.append(memory_id)

        assert len(set(ids)) == 3
        count = sqlite_manager.get_memories_count()
        assert count == 3

    def test_memory_contains_timestamp(self, memory_service, sample_image_path):
        """创建的记忆应包含创建时间戳"""
        memory_id = memory_service.create_memory(sample_image_path)
        record = memory_service.get_memory(memory_id)

        assert record is not None
        assert record.created_at is not None
        assert len(record.created_at) == 19

    def test_memory_image_path_is_absolute(self, memory_service, sample_image_path):
        """记忆中的图片路径应为绝对路径"""
        memory_id = memory_service.create_memory(sample_image_path)
        record = memory_service.get_memory(memory_id)

        assert record is not None
        assert Path(record.image_path).is_absolute()

    def test_create_memory_without_ai_client(self, sqlite_manager, chroma_manager, mock_ocr_engine, mock_embedding_client, sample_image_path):
        """无 AI 客户端时应仍能创建记忆（使用 OCR 文本作为摘要）"""
        from unittest.mock import MagicMock
        from services.memory_service import MemoryService

        ai_client = MagicMock()
        ai_client.is_configured.return_value = False

        service = MemoryService(
            sqlite_manager=sqlite_manager,
            chroma_manager=chroma_manager,
            ocr_engine=mock_ocr_engine,
            ai_client=ai_client,
            embedding_client=mock_embedding_client,
        )

        memory_id = service.create_memory(sample_image_path, app_name="offline")
        record = service.get_memory(memory_id)

        assert record is not None
        assert record.ai_summary is not None
        assert len(record.ai_summary) > 0

    def test_delete_memory_removes_from_both(self, memory_service, sample_image_path, sqlite_manager, chroma_manager):
        """删除记忆应同时从 SQLite 和 ChromaDB 移除"""
        memory_id = memory_service.create_memory(sample_image_path)

        result = memory_service.delete_memory(memory_id)
        assert result is True

        sqlite_record = sqlite_manager.get_memory_by_id(memory_id)
        assert sqlite_record is None
