"""
Chroma Manager - encapsulates vector database operations with graceful fallback.
"""
import os
import subprocess
import sys
import threading
from typing import List, Dict, Optional, Any, TYPE_CHECKING

from utils.logger import get_logger

if TYPE_CHECKING:
    from config.path_manager import PathManager

logger = get_logger(__name__)


class ChromaManager:
    """Vector database manager with no-op fallback when Chroma is unavailable."""

    def __init__(self, path_manager: "PathManager"):
        self._client: Optional[Any] = None
        self._collection: Optional[Any] = None
        self._lock = threading.Lock()
        self._init_lock = threading.Lock()
        self._path_manager = path_manager
        self._chroma_path = path_manager.chroma_path
        self._available = False
        self._initialization_attempted = False
        self._startup_error: Optional[str] = None

        self._chroma_path.parent.mkdir(parents=True, exist_ok=True)

    def _probe_chromadb_import(self) -> bool:
        if os.getenv("GLIMPSE_DISABLE_CHROMA") == "1":
            self._startup_error = "ChromaDB disabled by GLIMPSE_DISABLE_CHROMA=1"
            return False

        command = [sys.executable, "-c", "import chromadb"]
        kwargs = {
            "capture_output": True,
            "text": True,
            "timeout": 20,
        }
        if os.name == "nt":
            kwargs["creationflags"] = 0x08000000

        try:
            result = subprocess.run(command, **kwargs)
        except Exception as exc:
            self._startup_error = f"ChromaDB probe failed: {exc}"
            return False

        if result.returncode == 0:
            return True

        probe_error = (result.stderr or result.stdout or "").strip()
        self._startup_error = probe_error or f"ChromaDB probe exited with code {result.returncode}"
        return False

    def _ensure_initialized(self) -> bool:
        if self._available and self._collection is not None:
            return True

        if self._initialization_attempted:
            return False

        with self._init_lock:
            if self._available and self._collection is not None:
                return True
            if self._initialization_attempted:
                return False

            self._initialization_attempted = True

            if not self._probe_chromadb_import():
                logger.warning("ChromaDB unavailable, semantic search disabled: %s", self._startup_error)
                return False

            try:
                import chromadb
                from chromadb.config import Settings

                self._client = chromadb.PersistentClient(
                    path=str(self._chroma_path),
                    settings=Settings(anonymized_telemetry=False),
                )
                self._collection = self._client.get_or_create_collection(
                    name="memories",
                    metadata={"description": "Glimpse memory embeddings"},
                )
                self._available = True
            except Exception as exc:
                self._startup_error = str(exc)
                logger.warning("ChromaDB unavailable, semantic search disabled: %s", exc)
                self._client = None
                self._collection = None
                self._available = False

        return self._available and self._collection is not None

    @property
    def available(self) -> bool:
        return self._ensure_initialized()

    @property
    def startup_error(self) -> Optional[str]:
        return self._startup_error

    def add_memory(
        self,
        memory_id: str,
        text: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if not self.available:
            return True

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
            except Exception as exc:
                logger.error("Add memory error: %s", exc)
                return False

    def search_similar(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not self.available:
            return []

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
            except Exception as exc:
                logger.error("Search error: %s", exc)
                return []

    def delete_memory(self, memory_id: str) -> bool:
        if not self.available:
            return False

        with self._lock:
            try:
                self._collection.delete(ids=[memory_id])
                return True
            except Exception as exc:
                logger.error("Delete memory error: %s", exc)
                return False

    def update_memory(
        self,
        memory_id: str,
        text: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if not self.available:
            return True

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
            except Exception as exc:
                logger.error("Update memory error: %s", exc)
                return False

    def get_memory_count(self) -> int:
        if not self.available:
            return 0

        with self._lock:
            try:
                return self._collection.count()
            except Exception:
                return 0

    def get_all_memory_ids(self, limit: int = 1000, offset: int = 0) -> List[str]:
        if not self.available:
            return []

        with self._lock:
            try:
                results = self._collection.get(limit=limit, offset=offset)
                return results.get("ids", [])
            except Exception as exc:
                logger.error("Get all memory ids error: %s", exc)
                return []

    def close(self) -> None:
        self._client = None
        self._collection = None
        self._available = False


chroma_manager: Optional["ChromaManager"] = None  # populated by container
