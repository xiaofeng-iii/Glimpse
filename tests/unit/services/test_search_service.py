"""
Unit tests for services/search_service.py
"""
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_services():
    sqlite_mgr = MagicMock()
    sqlite_mgr.search_memories.return_value = []
    sqlite_mgr.get_all_memories.return_value = []
    sqlite_mgr.get_memory_by_id.return_value = None

    chroma_mgr = MagicMock()
    chroma_mgr.search_similar.return_value = []

    embedding_client = MagicMock()
    embedding_client.get_embedding.return_value = [0.1] * 384

    return {
        "sqlite_manager": sqlite_mgr,
        "chroma_manager": chroma_mgr,
        "embedding_client": embedding_client,
    }


class TestSearchServiceInit:
    def test_init_stores_dependencies(self, mock_services):
        from services.search_service import SearchService
        ss = SearchService(
            sqlite_manager=mock_services["sqlite_manager"],
            chroma_manager=mock_services["chroma_manager"],
            embedding_client=mock_services["embedding_client"],
        )
        assert ss._sqlite_manager is mock_services["sqlite_manager"]
        assert ss._search_mode == "hybrid"

    def test_default_search_mode_is_hybrid(self, mock_services):
        from services.search_service import SearchService
        ss = SearchService(**mock_services)
        assert ss.get_search_mode() == "hybrid"


class TestSearchServiceSearchMode:
    def test_set_search_mode_text(self, mock_services):
        from services.search_service import SearchService
        ss = SearchService(**mock_services)
        assert ss.set_search_mode("text") is True
        assert ss.get_search_mode() == "text"

    def test_set_search_mode_vector(self, mock_services):
        from services.search_service import SearchService
        ss = SearchService(**mock_services)
        assert ss.set_search_mode("vector") is True
        assert ss.get_search_mode() == "vector"

    def test_set_search_mode_hybrid(self, mock_services):
        from services.search_service import SearchService
        ss = SearchService(**mock_services)
        ss.set_search_mode("text")
        assert ss.set_search_mode("hybrid") is True
        assert ss.get_search_mode() == "hybrid"

    def test_set_search_mode_invalid(self, mock_services):
        from services.search_service import SearchService
        ss = SearchService(**mock_services)
        assert ss.set_search_mode("invalid") is False
        assert ss.get_search_mode() == "hybrid"


class TestSearchServiceSearch:
    def test_search_empty_query_returns_recent(self, mock_services):
        from services.search_service import SearchService
        from db.sqlite_manager import MemoryRecord
        ss = SearchService(**mock_services)
        
        mock_memory = MemoryRecord(id="1", created_at="now", image_path="path", ai_summary="sum", app_name="app")
        mock_services["sqlite_manager"].get_all_memories.return_value = [mock_memory]
        
        results = ss.search("")
        mock_services["sqlite_manager"].get_all_memories.assert_called_once()
        assert len(results) == 1
        assert not hasattr(results[0], "match_sources") or len(results[0].match_sources) == 0

    def test_search_text_mode(self, mock_services):
        from services.search_service import SearchService
        ss = SearchService(**mock_services)
        ss.set_search_mode("text")
        ss.search("test query")
        mock_services["sqlite_manager"].search_memories.assert_called_with(
            "test query", limit=20
        )

    def test_search_vector_mode(self, mock_services):
        from services.search_service import SearchService
        ss = SearchService(**mock_services)
        ss.set_search_mode("vector")
        ss.search("test query")
        mock_services["embedding_client"].get_embedding.assert_called_with("test query")
        mock_services["chroma_manager"].search_similar.assert_called_once()

    def test_search_vector_no_embedding(self, mock_services):
        from services.search_service import SearchService
        mock_services["embedding_client"].get_embedding.return_value = []
        ss = SearchService(**mock_services)
        ss.set_search_mode("vector")
        results = ss.search("test")
        assert results == []

    def test_search_hybrid_mode(self, mock_services):
        from services.search_service import SearchService
        ss = SearchService(**mock_services)
        ss.search("hybrid query")
        mock_services["sqlite_manager"].search_memories.assert_called_once()
        mock_services["embedding_client"].get_embedding.assert_called_once()

    def test_search_source_filter_ocr(self, mock_services):
        from services.search_service import SearchService
        from db.sqlite_manager import MemoryRecord
        ss = SearchService(**mock_services)
        
        mock_memory = MemoryRecord(id="1", created_at="now", image_path="path", ai_summary="sum", app_name="app")
        mock_services["sqlite_manager"].search_memories.return_value = [mock_memory]
        
        results = ss.search("test", source_filter="ocr")
        assert len(results) == 1
        assert "OCR" in results[0].match_sources
        assert "语义" not in results[0].match_sources
        mock_services["sqlite_manager"].search_memories.assert_called_with("test", limit=20)

    def test_search_source_filter_semantic(self, mock_services):
        from services.search_service import SearchService
        from db.sqlite_manager import MemoryRecord
        ss = SearchService(**mock_services)
        
        mock_memory = MemoryRecord(id="1", created_at="now", image_path="path", ai_summary="sum", app_name="app")
        mock_services["embedding_client"].get_embedding.return_value = [0.1, 0.2]
        mock_services["chroma_manager"].search_similar.return_value = [{"id": "1"}]
        mock_services["sqlite_manager"].get_memory_by_id.return_value = mock_memory
        
        results = ss.search("test", source_filter="semantic")
        assert len(results) == 1
        assert "语义" in results[0].match_sources
        assert "OCR" not in results[0].match_sources

    def test_search_source_filter_all(self, mock_services):
        from services.search_service import SearchService
        from db.sqlite_manager import MemoryRecord
        ss = SearchService(**mock_services)
        
        mock_memory1 = MemoryRecord(id="1", created_at="now", image_path="path", ai_summary="sum", app_name="app")
        mock_memory2 = MemoryRecord(id="2", created_at="now", image_path="path", ai_summary="sum", app_name="app")
        
        mock_services["sqlite_manager"].search_memories.return_value = [mock_memory1]
        mock_services["embedding_client"].get_embedding.return_value = [0.1, 0.2]
        mock_services["chroma_manager"].search_similar.return_value = [{"id": "1"}, {"id": "2"}]
        
        def get_memory_side_effect(mem_id):
            if mem_id == "1": return mock_memory1
            if mem_id == "2": return mock_memory2
            return None
            
        mock_services["sqlite_manager"].get_memory_by_id.side_effect = get_memory_side_effect
        
        results = ss.search("test", source_filter="all")
        assert len(results) == 2
        
        # Memory 1 should have both
        mem1 = next(m for m in results if m.id == "1")
        assert "OCR" in mem1.match_sources
        assert "语义" in mem1.match_sources
        
        # Memory 2 should have only semantic
        mem2 = next(m for m in results if m.id == "2")
        assert "OCR" not in mem2.match_sources
        assert "语义" in mem2.match_sources


class TestSearchServiceQuery:
    def test_get_recent_memories(self, mock_services):
        from services.search_service import SearchService
        ss = SearchService(**mock_services)
        ss.get_recent_memories(limit=50)
        mock_services["sqlite_manager"].get_all_memories.assert_called_with(limit=50)

    def test_get_memory_by_id(self, mock_services):
        from services.search_service import SearchService
        ss = SearchService(**mock_services)
        mock_services["sqlite_manager"].get_memory_by_id.return_value = "fake_memory"
        result = ss.get_memory_by_id("test-id")
        assert result == "fake_memory"
