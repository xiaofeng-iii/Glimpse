"""
Chroma Manager - 封装向量数据库的读写与检索
支持多实例隔离并行处理，注入PathManager
"""
from typing import List, Dict, Optional, Any, TYPE_CHECKING
import threading

import chromadb
from chromadb.config import Settings

if TYPE_CHECKING:
    from config.path_manager import PathManager


class ChromaManager:
    """Chroma 向量数据库管理器 - 支持多实例隔离，注入PathManager"""

    def __init__(self, path_manager: "PathManager"):
        self._client: Optional[chromadb.PersistentClient] = None
        self._collection: Optional[Any] = None
        self._lock = threading.Lock()
        self._path_manager = path_manager

        chroma_path = path_manager.chroma_path
        chroma_path.parent.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=str(chroma_path),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name="memories",
            metadata={"description": "Glimpse memory embeddings"},
        )

    def add_memory(
        self,
        memory_id: str,
        text: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        with self._lock:
            try:
                meta = metadata or {}
                meta["memory_id"] = memory_id

                self._collection.add(
                    ids=[memory_id],
                    documents=[text],
                    embeddings=[embedding],
                    metadatas=[meta],
                )
                return True
            except Exception as e:
                print(f"Add memory error: {e}")
                return False

    def search_similar(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            try:
                results = self._collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    where=where,
                )

                if not results or not results.get("ids"):
                    return []

                formatted_results = []
                for i in range(len(results["ids"][0])):
                    formatted_results.append({
                        "id": results["ids"][0][i],
                        "document": results["documents"][0][i],
                        "distance": results["distances"][0][i] if "distances" in results else None,
                        "metadata": results["metadatas"][0][i] if "metadatas" in results else None,
                    })

                return formatted_results
            except Exception as e:
                print(f"Search error: {e}")
                return []

    def delete_memory(self, memory_id: str) -> bool:
        with self._lock:
            try:
                self._collection.delete(ids=[memory_id])
                return True
            except Exception as e:
                print(f"Delete memory error: {e}")
                return False

    def update_memory(
        self,
        memory_id: str,
        text: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        with self._lock:
            try:
                update_kwargs = {"ids": [memory_id]}
                if text is not None:
                    update_kwargs["documents"] = [text]
                if embedding is not None:
                    update_kwargs["embeddings"] = [embedding]
                if metadata is not None:
                    update_kwargs["metadatas"] = [metadata]

                self._collection.update(**update_kwargs)
                return True
            except Exception as e:
                print(f"Update memory error: {e}")
                return False

    def get_memory_count(self) -> int:
        with self._lock:
            return self._collection.count()

    def get_all_memory_ids(self, limit: int = 1000, offset: int = 0) -> List[str]:
        with self._lock:
            try:
                results = self._collection.get(limit=limit, offset=offset)
                return results.get("ids", [])
            except Exception as e:
                print(f"Get all memory ids error: {e}")
                return []

    def close(self) -> None:
        self._client = None
        self._collection = None
