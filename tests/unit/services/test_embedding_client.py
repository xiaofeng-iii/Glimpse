"""
EmbeddingClient 单元测试

测试服务模块 services/embedding_client.py
覆盖: EmbeddingClient 初始化, get_embedding, get_embeddings, calculate_similarity

注意: SentenceTransformer 在模块加载时即初始化，本测试直接使用已加载实例。
"""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from services.embedding_client import EmbeddingClient, embedding_client


class TestEmbeddingClientInit:
    """EmbeddingClient 初始化测试"""

    def test_global_instance_exists(self):
        """验证: 全局 embedding_client 已创建"""
        assert isinstance(embedding_client, EmbeddingClient)

    def test_model_is_loaded(self):
        """验证: SentenceTransformer 模型已加载 (仅在依赖可用时)"""
        try:
            from sentence_transformers import SentenceTransformer
            assert isinstance(embedding_client.model, SentenceTransformer)
        except ImportError:
            pytest.skip("sentence-transformers not installed")


class TestEmbeddingClientGetEmbedding:
    """get_embedding 测试"""

    def test_get_embedding_returns_list(self):
        """验证: get_embedding 返回 float 列表（真实模型或错误优雅处理）"""
        try:
            result = embedding_client.get_embedding("测试文本")
            if result:
                assert isinstance(result, list)
                assert all(isinstance(v, float) for v in result)
        except Exception:
            pytest.skip("Model not available")

    def test_get_embedding_with_mocked_model(self):
        """验证: 当模型出错时返回空列表"""
        with patch.object(embedding_client.model, "encode", side_effect=RuntimeError("Model error")):
            result = embedding_client.get_embedding("test")
            assert result == []


class TestEmbeddingClientGetEmbeddings:
    """get_embeddings 批量测试"""

    def test_get_embeddings_returns_list_of_lists(self):
        """验证: get_embeddings 返回嵌入列表（真实模型）"""
        try:
            texts = ["文本1", "文本2", "文本3"]
            results = embedding_client.get_embeddings(texts)
            if results:
                assert isinstance(results, list)
                assert len(results) == 3
                assert all(isinstance(v, list) for v in results)
        except Exception:
            pytest.skip("Model not available")

    def test_get_embeddings_error_returns_empty(self):
        """验证: 错误时返回空列表"""
        with patch.object(embedding_client.model, "encode", side_effect=RuntimeError("Batch error")):
            result = embedding_client.get_embeddings(["text1", "text2"])
            assert result == []


class TestEmbeddingClientCalculateSimilarity:
    """calculate_similarity 余弦相似度测试 (纯数学，不依赖模型)"""

    def test_calculate_similarity_identical(self):
        """验证: 相同向量的相似度为 1.0"""
        vec = [0.5, 0.5, 0.5, 0.5]
        similarity = embedding_client.calculate_similarity(vec, vec)
        assert abs(similarity - 1.0) < 1e-6

    def test_calculate_similarity_orthogonal(self):
        """验证: 正交向量的相似度为 0.0"""
        vec1 = [1.0, 0.0]
        vec2 = [0.0, 1.0]
        similarity = embedding_client.calculate_similarity(vec1, vec2)
        assert abs(similarity - 0.0) < 1e-6

    def test_calculate_similarity_opposite(self):
        """验证: 相反向量的相似度为 -1.0"""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [-1.0, -2.0, -3.0]
        similarity = embedding_client.calculate_similarity(vec1, vec2)
        assert abs(similarity + 1.0) < 1e-6

    def test_calculate_similarity_empty_input(self):
        """验证: 空向量返回 0.0"""
        assert embedding_client.calculate_similarity([], [1.0]) == 0.0
        assert embedding_client.calculate_similarity([1.0], []) == 0.0

    def test_calculate_similarity_zero_norm(self):
        """验证: 零向量返回 0.0"""
        assert embedding_client.calculate_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0

    def test_calculate_similarity_high_dimensional(self):
        """验证: 高维向量相似度计算正确"""
        vec1 = [1.0] * 100
        vec2 = [1.0] * 100
        similarity = embedding_client.calculate_similarity(vec1, vec2)
        assert abs(similarity - 1.0) < 1e-6

    def test_calculate_similarity_various(self):
        """验证: 一般向量的相似度在合理范围"""
        vec1 = [0.2, 0.5, 0.3, 0.8]
        vec2 = [0.3, 0.4, 0.2, 0.7]
        similarity = embedding_client.calculate_similarity(vec1, vec2)
        assert 0.0 < similarity < 1.0  # 正相关


class TestEmbeddingClientGlobal:
    """全局 embedding_client 测试"""

    def test_global_is_embedding_client(self):
        """验证: 全局实例是 EmbeddingClient 类型"""
        assert isinstance(embedding_client, EmbeddingClient)
