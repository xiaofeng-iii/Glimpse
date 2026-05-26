"""
Search Service - 统一搜索逻辑
支持SQLite全文搜索和向量相似度搜索
支持构造函数注入依赖
"""
from typing import List, Optional, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from db.sqlite_manager import SQLiteManager
    from db.chroma_manager import ChromaManager
    from services.embedding_client import EmbeddingClient


class SearchService:
    """搜索服务 - 统一管理文本搜索和向量搜索"""

    def __init__(
        self,
        sqlite_manager: "SQLiteManager",
        chroma_manager: "ChromaManager",
        embedding_client: "EmbeddingClient",
    ):
        self._sqlite_manager = sqlite_manager
        self._chroma_manager = chroma_manager
        self._embedding_client = embedding_client

        self._search_mode = "hybrid"
        self._rrf_k = 60

    def set_search_mode(self, mode: str) -> bool:
        if mode in ("text", "vector", "hybrid"):
            self._search_mode = mode
            return True
        return False

    def get_search_mode(self) -> str:
        return self._search_mode

    def search(self, query: str, limit: int = 20, source_filter: Optional[str] = None) -> List:
        if not query.strip():
            return self.get_recent_memories(limit=limit)

        # source_filter overrides internal _search_mode if provided
        mode = self._search_mode
        if source_filter == "ocr":
            mode = "text"
        elif source_filter == "semantic":
            mode = "vector"
        elif source_filter == "all":
            mode = "hybrid"

        if mode == "text":
            return self._search_text(query, limit)
        elif mode == "vector":
            return self._search_vector(query, limit)
        else:
            return self._search_hybrid(query, limit)

    def _search_text(self, query: str, limit: int) -> List:
        results = self._sqlite_manager.search_memories(query, limit=limit)
        for memory in results:
            if not hasattr(memory, "match_sources"):
                memory.match_sources = []
            if "精确" not in memory.match_sources:
                memory.match_sources.append("精确")
        return results

    def _search_vector(self, query: str, limit: int) -> List:
        embedding = self._embedding_client.get_embedding(query)
        if not embedding:
            return []

        results = self._chroma_manager.search_similar(embedding, n_results=limit)
        if not results:
            return []

        memory_ids = [r["id"] for r in results]
        memories = []
        for mem_id in memory_ids:
            memory = self._sqlite_manager.get_memory_by_id(mem_id)
            if memory:
                if not hasattr(memory, "match_sources"):
                    memory.match_sources = []
                if "语义" not in memory.match_sources:
                    memory.match_sources.append("语义")
                memories.append(memory)

        return memories

    def _search_hybrid(self, query: str, limit: int) -> List:
        text_results = self._sqlite_manager.search_memories(query, limit=limit * 2)

        embedding = self._embedding_client.get_embedding(query)
        if not embedding:
            for memory in text_results[:limit]:
                if not hasattr(memory, "match_sources"):
                    memory.match_sources = []
                if "精确" not in memory.match_sources:
                    memory.match_sources.append("精确")
            return text_results[:limit]

        vector_results = self._chroma_manager.search_similar(embedding, n_results=limit * 2)

        text_rank: Dict[str, float] = {}
        for rank, memory in enumerate(text_results):
            text_rank[memory.id] = 1.0 / (self._rrf_k + rank + 1)

        vector_rank: Dict[str, float] = {}
        for rank, result in enumerate(vector_results):
            vector_rank[result["id"]] = 1.0 / (self._rrf_k + rank + 1)

        all_ids = set(text_rank.keys()) | set(vector_rank.keys())
        rrf_scores: Dict[str, float] = {}
        for mem_id in all_ids:
            rrf_scores[mem_id] = text_rank.get(mem_id, 0.0) + vector_rank.get(mem_id, 0.0)

        sorted_ids = sorted(rrf_scores.keys(), key=lambda mid: rrf_scores[mid], reverse=True)

        merged = []
        for mem_id in sorted_ids[:limit]:
            memory = self._sqlite_manager.get_memory_by_id(mem_id)
            if memory:
                if not hasattr(memory, "match_sources"):
                    memory.match_sources = []
                if mem_id in text_rank and "精确" not in memory.match_sources:
                    memory.match_sources.append("精确")
                if mem_id in vector_rank and "语义" not in memory.match_sources:
                    memory.match_sources.append("语义")
                merged.append(memory)

        return merged

    def get_recent_memories(self, limit: int = 100) -> List:
        return self._sqlite_manager.get_all_memories(limit=limit)

    def get_memory_by_id(self, memory_id: str):
        return self._sqlite_manager.get_memory_by_id(memory_id)
