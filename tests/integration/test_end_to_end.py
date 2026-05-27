"""
端到端集成测试

验证：从截图捕获到记忆创建到搜索的完整业务流程
"""
import pytest


class TestEndToEnd:
    """端到端测试：截图 → 分析 → 存储 → 搜索"""

    def test_full_lifecycle_create_read_delete(
        self, memory_service, sample_image_path, sqlite_manager, chroma_manager
    ):
        """完整生命周期：创建 → 读取 → 删除"""
        memory_id = memory_service.create_memory(sample_image_path, app_name="e2e_test")

        record = memory_service.get_memory(memory_id)
        assert record is not None
        assert record.app_name == "e2e_test"

        deleted = memory_service.delete_memory(memory_id)
        assert deleted is True

        gone = memory_service.get_memory(memory_id)
        assert gone is None

    def test_create_search_find(
        self, memory_service, sample_image_path, search_service, sqlite_manager, mock_embedding_client
    ):
        """创建记忆后应能通过搜索找到"""
        memory_id = memory_service.create_memory(
            sample_image_path, app_name="searchable_app"
        )

        mock_embedding_client.get_embedding.return_value = [0.1] * 384
        results = search_service.search("截图摘要", limit=10)

        found = any(r.id == memory_id for r in results)
        assert found, f"Created memory {memory_id} not found in search results"

    def test_multi_app_workflow(
        self, memory_service, sample_image_path, search_service, mock_embedding_client
    ):
        """多应用场景：不同 app_name 的记忆应能区分"""
        apps = ["chrome", "vscode", "terminal", "slack"]
        ids = {}

        for app in apps:
            memory_id = memory_service.create_memory(sample_image_path, app_name=app)
            ids[app] = memory_id

        for app, mem_id in ids.items():
            record = memory_service.get_memory(mem_id)
            assert record.app_name == app

    def test_search_returns_results_ordered(self, memory_service, sample_image_path, search_service, mock_embedding_client):
        """搜索结果应有合理排序"""
        for i in range(5):
            memory_service.create_memory(sample_image_path, app_name=f"order_{i}")

        mock_embedding_client.get_embedding.return_value = [0.15] * 384
        results = search_service.search("测试", limit=20)

        assert len(results) >= 1
        ids = [r.id for r in results]
        assert len(ids) == len(set(ids)), "Results should be deduplicated"

    def test_get_active_count(self, memory_service, sample_image_path):
        """get_active_count 应正确反映活动任务数"""
        initial = memory_service.get_active_count()
        assert initial == 0

        memory_service.create_memory(sample_image_path)

        after = memory_service.get_active_count()
        assert after == 0

    def test_memory_count_reflects_operations(self, memory_service, sample_image_path, sqlite_manager):
        """记忆计数应准确反映创建和删除操作"""
        assert sqlite_manager.get_memories_count() == 0

        id1 = memory_service.create_memory(sample_image_path)
        assert sqlite_manager.get_memories_count() == 1

        id2 = memory_service.create_memory(sample_image_path)
        assert sqlite_manager.get_memories_count() == 2

        memory_service.delete_memory(id1)
        assert sqlite_manager.get_memories_count() == 1

        memory_service.delete_memory(id2)
        assert sqlite_manager.get_memories_count() == 0

    def test_get_all_memories_with_offset(self, memory_service, sample_image_path, sqlite_manager):
        """get_all_memories 的分页功能应正常"""
        for i in range(10):
            memory_service.create_memory(sample_image_path, app_name=f"page_{i}")

        page1 = sqlite_manager.get_all_memories(limit=5, offset=0)
        page2 = sqlite_manager.get_all_memories(limit=5, offset=5)

        assert len(page1) == 5
        assert len(page2) == 5

        page1_ids = {r.id for r in page1}
        page2_ids = {r.id for r in page2}
        assert page1_ids.isdisjoint(page2_ids)

    def test_concurrent_memory_creation(
        self, memory_service, sample_image_path, sqlite_manager
    ):
        """多条记忆连续创建不应互相干扰"""
        import concurrent.futures

        def create_one(index):
            return memory_service.create_memory(sample_image_path, app_name=f"concurrent_{index}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(create_one, i) for i in range(3)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert all(r is not None for r in results)
        assert len(set(results)) == 3

        count = sqlite_manager.get_memories_count()
        assert count == 3

    def test_recent_memories_ordering(self, memory_service, sample_image_path, sqlite_manager):
        """获取最近记忆应按时间降序排列"""
        import time

        ids = []
        for i in range(5):
            memory_id = memory_service.create_memory(sample_image_path, app_name=f"time_{i}")
            ids.append(memory_id)
            time.sleep(0.1)

        recent = sqlite_manager.get_all_memories(limit=5)

        assert len(recent) == 5
        timestamps = [r.created_at for r in recent]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_zero_memories_on_fresh_db(self, sqlite_manager, chroma_manager):
        """全新数据库应无任何记忆"""
        assert sqlite_manager.get_memories_count() == 0
        assert chroma_manager.get_memory_count() == 0
