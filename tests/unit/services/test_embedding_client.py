"""
EmbeddingClient 单元测试

测试服务模块 services/embedding_client.py（ONNX 推理版）
覆盖: 懒加载与单次尝试、get_embedding/get_embeddings、strip+lower 语义、
calculate_similarity、错误路径优雅降级。

真模型用例依赖 assets/embedding 下的模型文件（scripts/fetch_embedding_model.py
获取）；缺失时 skip。
"""

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from services.embedding_client import EmbeddingClient, embedding_client

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODEL_DIR = PROJECT_ROOT / "assets" / "embedding"


def model_files_available() -> bool:
    return (MODEL_DIR / "bge-small-zh-v1.5.onnx").is_file() and (
        MODEL_DIR / "bge-small-zh-v1.5.tokenizer.json"
    ).is_file()


@pytest.fixture
def restore_global_encoder():
    """错误路径用例会替换全局单例的编码器，用例后恢复原状。"""
    saved_model = embedding_client._model
    saved_attempted = embedding_client._load_attempted
    yield
    embedding_client._model = saved_model
    embedding_client._load_attempted = saved_attempted


class TestEmbeddingClientInit:
    """EmbeddingClient 初始化测试"""

    def test_global_instance_exists(self):
        """验证: 全局 embedding_client 已创建"""
        assert isinstance(embedding_client, EmbeddingClient)

    def test_model_load_failure_is_one_shot(self, tmp_path):
        """验证: 模型目录无效时加载只尝试一次，之后直接返回 None（不反复重试）"""
        client = EmbeddingClient(model_dir=tmp_path)
        assert client.model is None
        assert client._load_attempted is True
        # 第二次访问不再尝试（没有可观测重试计数，以状态位为准）
        assert client.model is None


class TestEmbeddingClientGetEmbedding:
    """get_embedding 测试"""

    @pytest.mark.skipif(not model_files_available(), reason="embedding model files not fetched")
    def test_get_embedding_shape_and_norm(self):
        """验证: 返回 512 维 L2 归一化向量"""
        result = embedding_client.get_embedding("测试文本")
        assert isinstance(result, list)
        assert len(result) == 512
        assert all(isinstance(v, float) for v in result)
        assert abs(np.linalg.norm(result) - 1.0) < 1e-4

    @pytest.mark.skipif(not model_files_available(), reason="embedding model files not fetched")
    def test_get_embedding_lowercases_latin_text(self):
        """验证: strip+lower 语义（sentence-transformers 2.2.2 等价行为），
        'Windows' 与 'windows' 产生完全相同的向量"""
        upper = embedding_client.get_embedding("Windows 系统桌面")
        lower = embedding_client.get_embedding("windows 系统桌面")
        assert upper == lower

    def test_get_embedding_error_returns_empty(self, restore_global_encoder):
        """验证: 编码器抛错时返回空列表"""
        mock = MagicMock()
        mock.encode.side_effect = RuntimeError("Model error")
        embedding_client._model = mock
        assert embedding_client.get_embedding("test") == []

    def test_get_embedding_unavailable_returns_empty(self, restore_global_encoder):
        """验证: 模型不可用（None）时返回空列表"""
        embedding_client._model = None
        embedding_client._load_attempted = True
        assert embedding_client.get_embedding("test") == []


class TestEmbeddingClientGetEmbeddings:
    """get_embeddings 批量测试"""

    @pytest.mark.skipif(not model_files_available(), reason="embedding model files not fetched")
    def test_get_embeddings_returns_list_of_lists(self):
        """验证: 批量返回嵌入列表"""
        texts = ["文本1", "文本2", "文本3"]
        results = embedding_client.get_embeddings(texts)
        assert isinstance(results, list)
        assert len(results) == 3
        assert all(isinstance(v, list) and len(v) == 512 for v in results)

    def test_get_embeddings_empty_input(self):
        """验证: 空输入返回空列表"""
        assert embedding_client.get_embeddings([]) == []

    def test_get_embeddings_error_returns_empty(self, restore_global_encoder):
        """验证: 批量编码出错时返回空列表"""
        mock = MagicMock()
        mock.encode.side_effect = RuntimeError("Batch error")
        embedding_client._model = mock
        assert embedding_client.get_embeddings(["t1", "t2"]) == []


class TestEmbeddingClientCalculateSimilarity:
    """calculate_similarity 余弦相似度测试 (纯数学，不依赖模型)"""

    def test_calculate_similarity_identical(self):
        """验证: 相同向量的相似度为 1.0"""
        vec = [0.5, 0.5, 0.5, 0.5]
        similarity = embedding_client.calculate_similarity(vec, vec)
        assert abs(similarity - 1.0) < 1e-6

    def test_calculate_similarity_orthogonal(self):
        """验证: 正交向量的相似度为 0.0"""
        similarity = embedding_client.calculate_similarity([1.0, 0.0], [0.0, 1.0])
        assert abs(similarity - 0.0) < 1e-6

    def test_calculate_similarity_opposite(self):
        """验证: 相反向量的相似度为 -1.0"""
        similarity = embedding_client.calculate_similarity([1.0, 2.0, 3.0], [-1.0, -2.0, -3.0])
        assert abs(similarity + 1.0) < 1e-6

    def test_calculate_similarity_empty_input(self):
        """验证: 空向量返回 0.0"""
        assert embedding_client.calculate_similarity([], [1.0]) == 0.0
        assert embedding_client.calculate_similarity([1.0], []) == 0.0

    def test_calculate_similarity_zero_norm(self):
        """验证: 零向量返回 0.0"""
        assert embedding_client.calculate_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0
