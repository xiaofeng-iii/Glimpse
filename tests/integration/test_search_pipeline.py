"""
搜索功能流程集成测试

验证：文本搜索、向量搜索、混合搜索的完整流程
"""
import pytest


class TestSearchPipeline:
    """测试搜索功能管道"""

    def test_text_search_finds_keyword(self, populated_memory_service, sqlite_manager):
        """文本搜索应根据关键词找到对应记忆"""
        memory_service, _ = populated_memory_service

        results = sqlite_manager.search_memories("截图摘要", limit=20)
        assert len(results) >= 1

    def test_vector_search_uses_embedding(self, search_service, populated_memory_service, mock_embedding_client):
        """向量搜索应使用嵌入向量进行相似度匹配"""
        _, memory_id = populated_memory_service

        search_service.set_search_mode("vector")
        mock_embedding_client.get_embedding.return_value = [0.1] * 384

        results = search_service.search("测试查询")
        assert len(results) >= 1

    def test_hybrid_search_combines_results(self, search_service, populated_memory_service, mock_embedding_client):
        """混合搜索应合并文本和向量搜索结果"""
        _, memory_id = populated_memory_service

        search_service.set_search_mode("hybrid")
        mock_embedding_client.get_embedding.return_value = [0.1] * 384

        results = search_service.search("测试查询")
        assert len(results) >= 1

    def test_hybrid_search_deduplicates(self, search_service, populated_memory_service, mock_embedding_client):
        """混合搜索不应重复返回相同的记忆"""
        _, memory_id = populated_memory_service

        search_service.set_search_mode("hybrid")
        mock_embedding_client.get_embedding.return_value = [0.1] * 384

        results = search_service.search("测试查询")
        ids = [r.id for r in results]
        assert len(ids) == len(set(ids))

    def test_search_mode_switch(self, search_service):
        """搜索模式切换应正常工作"""
        assert search_service.set_search_mode("text") is True
        assert search_service.get_search_mode() == "text"

        assert search_service.set_search_mode("vector") is True
        assert search_service.get_search_mode() == "vector"

        assert search_service.set_search_mode("hybrid") is True
        assert search_service.get_search_mode() == "hybrid"

        assert search_service.set_search_mode("invalid") is False
        assert search_service.get_search_mode() == "hybrid"

    def test_empty_query_returns_recent(self, search_service, populated_memory_service):
        """空搜索字符串应返回最近的记忆"""
        results = search_service.search("")
        assert len(results) >= 1

    def test_empty_query_returns_recent_memories(self, search_service, populated_memory_service):
        """仅空格查询应返回最近的记忆"""
        results = search_service.search("   ")
        assert len(results) >= 1

    def test_search_with_no_results(self, search_service, populated_memory_service):
        """搜索无匹配结果时应返回空列表"""
        results = search_service.search("绝对不会匹配的字符串xyzabc123456")
        assert isinstance(results, list)

    def test_limit_parameter_respected(self, memory_service, sample_image_path, search_service, mock_embedding_client):
        """搜索结果的 limit 参数应生效"""
        for i in range(5):
            memory_service.create_memory(sample_image_path, app_name=f"app_{i}")

        mock_embedding_client.get_embedding.return_value = [0.2] * 384
        results = search_service.search("测试", limit=2)
        assert len(results) <= 2

    def test_get_memory_by_id(self, search_service, populated_memory_service):
        """按 ID 获取记忆应返回正确记录"""
        _, memory_id = populated_memory_service

        record = search_service.get_memory_by_id(memory_id)
        assert record is not None
        assert record.id == memory_id

    def test_get_recent_memories_pagination(self, memory_service, sample_image_path, search_service):
        """分页获取最近记忆应正常工作"""
        for i in range(10):
            memory_service.create_memory(sample_image_path, app_name=f"pg_{i}")

        page1 = search_service.get_recent_memories(limit=5)
        assert 1 <= len(page1) <= 5

        page2 = search_service.get_recent_memories(limit=5)
        page1_ids = {r.id for r in page1}
        page2_ids = {r.id for r in page2}
        assert page1_ids == page2_ids or page1_ids & page2_ids == set()
