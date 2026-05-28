"""
Unit tests for db/chroma_manager.py
"""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_path_manager(tmp_path):
    pm = MagicMock()
    pm.chroma_path = tmp_path / "test_chroma"
    pm.database_dir = tmp_path
    pm.chroma_path.parent.mkdir(parents=True, exist_ok=True)
    return pm


class TestChromaManagerInit:
    def test_init_creates_client(self, mock_path_manager):
        from db.chroma_manager import ChromaManager
        mgr = ChromaManager(mock_path_manager)
        assert mgr._client is not None
        assert mgr._collection is not None
        mgr.close()

    def test_initial_count_zero(self, mock_path_manager):
        from db.chroma_manager import ChromaManager
        mgr = ChromaManager(mock_path_manager)
        assert mgr.get_memory_count() == 0
        mgr.close()


class TestChromaManagerAdd:
    def test_add_memory_success(self, mock_path_manager):
        from db.chroma_manager import ChromaManager
        mgr = ChromaManager(mock_path_manager)
        embedding = [0.1] * 384
        result = mgr.add_memory("test-1", "test document", embedding)
        assert result is True
        assert mgr.get_memory_count() == 1
        mgr.close()

    def test_add_memory_with_metadata(self, mock_path_manager):
        from db.chroma_manager import ChromaManager
        mgr = ChromaManager(mock_path_manager)
        embedding = [0.2] * 384
        result = mgr.add_memory(
            "test-2",
            "doc with meta",
            embedding,
            metadata={"app": "chrome"},
        )
        assert result is True
        mgr.close()

    def test_add_memory_multiple(self, mock_path_manager):
        from db.chroma_manager import ChromaManager
        mgr = ChromaManager(mock_path_manager)
        embedding = [0.3] * 384
        for i in range(3):
            mgr.add_memory(f"multi-{i}", f"doc {i}", embedding)
        assert mgr.get_memory_count() == 3
        mgr.close()


class TestChromaManagerSearch:
    def test_search_similar_returns_results(self, mock_path_manager):
        from db.chroma_manager import ChromaManager
        mgr = ChromaManager(mock_path_manager)
        embedding = [0.5] * 384
        mgr.add_memory("srch-1", "python programming", embedding)
        results = mgr.search_similar(embedding, n_results=5)
        assert len(results) >= 1
        assert results[0]["id"] == "srch-1"
        mgr.close()

    def test_search_empty_collection(self, mock_path_manager):
        from db.chroma_manager import ChromaManager
        mgr = ChromaManager(mock_path_manager)
        embedding = [0.0] * 384
        results = mgr.search_similar(embedding)
        assert results == []
        mgr.close()


class TestChromaManagerDelete:
    def test_delete_memory_success(self, mock_path_manager):
        from db.chroma_manager import ChromaManager
        mgr = ChromaManager(mock_path_manager)
        embedding = [0.4] * 384
        mgr.add_memory("del-1", "to delete", embedding)
        assert mgr.get_memory_count() == 1
        result = mgr.delete_memory("del-1")
        assert result is True
        assert mgr.get_memory_count() == 0
        mgr.close()

    def test_delete_nonexistent(self, mock_path_manager):
        from db.chroma_manager import ChromaManager
        mgr = ChromaManager(mock_path_manager)
        result = mgr.delete_memory("nonexistent")
        assert result is True  # ChromaDB delete is idempotent
        mgr.close()


class TestChromaManagerUpdate:
    def test_update_memory_text(self, mock_path_manager):
        from db.chroma_manager import ChromaManager
        mgr = ChromaManager(mock_path_manager)
        embedding = [0.6] * 384
        mgr.add_memory("upd-1", "original text", embedding)
        result = mgr.update_memory("upd-1", text="updated text")
        assert result is True
        mgr.close()

    def test_update_memory_embedding(self, mock_path_manager):
        from db.chroma_manager import ChromaManager
        mgr = ChromaManager(mock_path_manager)
        embedding = [0.7] * 384
        mgr.add_memory("upd-2", "text", embedding)
        new_embedding = [0.99] * 384
        result = mgr.update_memory("upd-2", embedding=new_embedding)
        assert result is True
        mgr.close()


class TestChromaManagerGetAll:
    def test_get_all_memory_ids(self, mock_path_manager):
        from db.chroma_manager import ChromaManager
        mgr = ChromaManager(mock_path_manager)
        embedding = [0.8] * 384
        for i in range(3):
            mgr.add_memory(f"ids-{i}", f"doc {i}", embedding)
        ids = mgr.get_all_memory_ids()
        assert len(ids) == 3
        mgr.close()

    def test_get_all_memory_ids_limit_offset(self, mock_path_manager):
        from db.chroma_manager import ChromaManager
        mgr = ChromaManager(mock_path_manager)
        embedding = [0.9] * 384
        for i in range(5):
            mgr.add_memory(f"lim-{i}", f"doc {i}", embedding)
        ids = mgr.get_all_memory_ids(limit=2, offset=0)
        assert len(ids) <= 2
        mgr.close()


class TestChromaManagerGlobal:
    def test_global_is_none_initially(self):
        from db.chroma_manager import chroma_manager
        assert chroma_manager is None
