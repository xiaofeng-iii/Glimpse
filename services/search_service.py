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
        self._semantic_threshold = 1.15  # 语义匹配阈值，distance ≤ 此值才打 [语义] 标签

    def set_search_mode(self, mode: str) -> bool:
        if mode in ("text", "vector", "hybrid"):
            self._search_mode = mode
            return True
        return False

    def get_search_mode(self) -> str:
        return self._search_mode

    def warmup(self) -> Dict[str, bool]:
        result = {
            "chroma_ready": False,
            "embedding_ready": False,
        }

        try:
            result["chroma_ready"] = bool(self._chroma_manager.available)
        except Exception as exc:
            print(f"Semantic search warmup: ChromaDB unavailable: {exc}")

        try:
            result["embedding_ready"] = bool(self._embedding_client.get_embedding("语义搜索预热"))
        except Exception as exc:
            print(f"Semantic search warmup: embedding model unavailable: {exc}")

        print(
            "Semantic search warmup completed: "
            f"chroma_ready={result['chroma_ready']}, "
            f"embedding_ready={result['embedding_ready']}"
        )
        return result

    def search(
        self,
        query: str,
        limit: int = 20,
        source_filter: Optional[str] = None,
        semantic_threshold: Optional[float] = None,
        candidate_multiplier: int = 2,
        rrf_k: Optional[int] = None,
        include_debug: bool = False,
    ) -> List:
        if not query.strip():
            return self.get_recent_memories(limit=limit)

        threshold = (
            self._semantic_threshold
            if semantic_threshold is None
            else max(0.0, float(semantic_threshold))
        )
        candidate_multiplier = max(1, int(candidate_multiplier))
        fusion_rrf_k = self._rrf_k if rrf_k is None else max(1, int(rrf_k))

        # source_filter overrides internal _search_mode if provided
        mode = self._search_mode
        normalized_source = (source_filter or "").strip().lower()
        if normalized_source in {"exact", "ocr"}:
            mode = "text"
        elif normalized_source == "semantic":
            mode = "vector"
        elif normalized_source == "all":
            mode = "hybrid"

        if mode == "text":
            return self._search_text(query, limit, include_debug)
        elif mode == "vector":
            return self._search_vector(
                query,
                limit,
                threshold,
                candidate_multiplier,
                include_debug,
            )
        else:
            return self._search_hybrid(
                query,
                limit,
                threshold,
                candidate_multiplier,
                fusion_rrf_k,
                include_debug,
            )

    @staticmethod
    def _set_search_metadata(
        memory,
        match_sources: List[str],
        include_debug: bool,
        *,
        mode: str,
        text_rank: Optional[int] = None,
        semantic_rank: Optional[int] = None,
        semantic_distance: Optional[float] = None,
        rrf_score: Optional[float] = None,
    ) -> None:
        memory.match_sources = match_sources
        memory.search_debug = (
            {
                "mode": mode,
                "text_rank": text_rank,
                "semantic_rank": semantic_rank,
                "semantic_distance": semantic_distance,
                "rrf_score": rrf_score,
            }
            if include_debug
            else None
        )

    def _search_text(self, query: str, limit: int, include_debug: bool) -> List:
        results = self._sqlite_manager.search_memories(query, limit=limit)
        for rank, memory in enumerate(results, start=1):
            self._set_search_metadata(
                memory,
                ["精确"],
                include_debug,
                mode="text",
                text_rank=rank,
            )
        return results

    def _search_vector(
        self,
        query: str,
        limit: int,
        semantic_threshold: float,
        candidate_multiplier: int,
        include_debug: bool,
    ) -> List:
        embedding = self._embedding_client.get_embedding(query)
        if not embedding:
            return []

        results = self._chroma_manager.search_similar(
            embedding,
            n_results=limit * candidate_multiplier,
        )
        if not results:
            return []

        memories = []
        for rank, result in enumerate(results, start=1):
            mem_id = result["id"]
            distance = result.get("distance")

            # 只有相似度超过阈值才认为是语义匹配
            if distance is not None and distance > semantic_threshold:
                continue

            memory = self._sqlite_manager.get_memory_by_id(mem_id)
            if memory and memory.sync_status == "SYNCED":
                self._set_search_metadata(
                    memory,
                    ["语义"],
                    include_debug,
                    mode="vector",
                    semantic_rank=rank,
                    semantic_distance=distance,
                )
                memories.append(memory)
                if len(memories) >= limit:
                    break

        return memories

    def _search_hybrid(
        self,
        query: str,
        limit: int,
        semantic_threshold: float,
        candidate_multiplier: int,
        rrf_k: int,
        include_debug: bool,
    ) -> List:
        candidate_limit = limit * candidate_multiplier
        text_results = self._sqlite_manager.search_memories(query, limit=candidate_limit)

        embedding = self._embedding_client.get_embedding(query)
        if not embedding:
            for rank, memory in enumerate(text_results[:limit], start=1):
                self._set_search_metadata(
                    memory,
                    ["精确"],
                    include_debug,
                    mode="hybrid",
                    text_rank=rank,
                )
            return text_results[:limit]

        vector_results = self._chroma_manager.search_similar(
            embedding,
            n_results=candidate_limit,
        )

        text_rank: Dict[str, float] = {}
        text_position: Dict[str, int] = {}
        for rank, memory in enumerate(text_results):
            text_rank[memory.id] = 1.0 / (rrf_k + rank + 1)
            text_position[memory.id] = rank + 1

        # 保存 vector result 的 distance 用于阈值判断
        vector_rank: Dict[str, float] = {}
        vector_position: Dict[str, int] = {}
        vector_distance: Dict[str, float] = {}
        for rank, result in enumerate(vector_results):
            result_id = result["id"]
            memory = self._sqlite_manager.get_memory_by_id(result_id)
            if memory is None or memory.sync_status != "SYNCED":
                continue
            vector_rank[result_id] = 1.0 / (rrf_k + rank + 1)
            vector_position[result_id] = rank + 1
            if "distance" in result:
                vector_distance[result_id] = result["distance"]

        accepted_vector_ids = {
            memory_id
            for memory_id, distance in vector_distance.items()
            if distance is not None and distance <= semantic_threshold
        }
        # Above-threshold vector candidates may still contribute an RRF boost to
        # an exact match, but they must never create a result with no match source.
        all_ids = set(text_rank.keys()) | accepted_vector_ids
        rrf_scores: Dict[str, float] = {}
        for mem_id in all_ids:
            rrf_scores[mem_id] = text_rank.get(mem_id, 0.0) + vector_rank.get(mem_id, 0.0)

        sorted_ids = sorted(rrf_scores.keys(), key=lambda mid: rrf_scores[mid], reverse=True)

        merged = []
        for mem_id in sorted_ids[:limit]:
            memory = self._sqlite_manager.get_memory_by_id(mem_id)
            if memory:
                match_sources = []
                if mem_id in text_rank:
                    match_sources.append("精确")
                # 只有 distance 存在且不超过阈值才打语义标签
                distance = vector_distance.get(mem_id)
                if (
                    mem_id in vector_rank
                    and distance is not None
                    and distance <= semantic_threshold
                ):
                    match_sources.append("语义")
                self._set_search_metadata(
                    memory,
                    match_sources,
                    include_debug,
                    mode="hybrid",
                    text_rank=text_position.get(mem_id),
                    semantic_rank=vector_position.get(mem_id),
                    semantic_distance=distance,
                    rrf_score=rrf_scores[mem_id],
                )
                merged.append(memory)

        return merged

    def get_recent_memories(self, limit: int = 100) -> List:
        return self._sqlite_manager.get_all_memories(limit=limit)

    def get_memory_by_id(self, memory_id: str):
        return self._sqlite_manager.get_memory_by_id(memory_id)
