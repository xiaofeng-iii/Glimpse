"""
SQLite Manager - 封装 SQLite CRUD，包含 FTS5 配置与写入互斥锁
支持多实例隔离并行处理，注入PathManager
"""
import sqlite3
import threading
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from pathlib import Path

from utils.logger import get_logger

if TYPE_CHECKING:
    from config.path_manager import PathManager

logger = get_logger(__name__)


@dataclass
class MemoryRecord:
    id: str
    created_at: str
    image_path: str
    ai_summary: str
    app_name: str
    text_content: Optional[str] = None
    extra_images: Optional[str] = None
    sync_status: str = "PENDING"
    match_sources: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row) -> "MemoryRecord":
        # sqlite3.Row supports dict-like access; plain tuples used in tests do not
        if hasattr(row, "keys"):
            return cls(
                id=row["id"],
                created_at=row["created_at"],
                image_path=row["image_path"],
                ai_summary=row["ai_summary"],
                app_name=row["app_name"],
                text_content=row["text_content"] if "text_content" in row.keys() else None,
                extra_images=row["extra_images"] if "extra_images" in row.keys() else None,
                sync_status=row["sync_status"] if "sync_status" in row.keys() else "PENDING",
            )
        # Fallback for plain tuples (tests)
        if len(row) >= 8:
            return cls(
                id=row[0],
                created_at=row[1],
                image_path=row[2],
                ai_summary=row[3],
                app_name=row[4],
                text_content=row[5] if len(row) > 5 else None,
                extra_images=row[6],
                sync_status=row[7],
            )
        return cls(
            id=row[0],
            created_at=row[1],
            image_path=row[2],
            ai_summary=row[3],
            app_name=row[4],
            text_content=row[5] if len(row) > 5 else None,
            extra_images=None,
            sync_status=row[6] if len(row) > 6 else "PENDING",
        )


class SQLiteManager:
    """SQLite 管理器 - 支持多实例隔离，注入PathManager"""

    def __init__(self, path_manager: "PathManager"):
        self._conn: Optional[sqlite3.Connection] = None
        self._write_lock = threading.Lock()
        self._path_manager = path_manager
        self._db_path = path_manager.sqlite_path
        self._init_db()

    def _init_db(self):
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        cursor = self._conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                image_path TEXT NOT NULL,
                ai_summary TEXT,
                app_name TEXT,
                text_content TEXT,
                extra_images TEXT,
                sync_status TEXT DEFAULT 'PENDING'
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_created_at
            ON memories(created_at DESC)
        """)

        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
            USING fts5(ai_summary, text_content, content='memories', content_rowid='rowid')
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, ai_summary, text_content)
                VALUES (new.rowid, new.ai_summary, new.text_content);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, ai_summary, text_content)
                VALUES ('delete', old.rowid, old.ai_summary, old.text_content);
                INSERT INTO memories_fts(rowid, ai_summary, text_content)
                VALUES (new.rowid, new.ai_summary, new.text_content);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, ai_summary, text_content)
                VALUES ('delete', old.rowid, old.ai_summary, old.text_content);
            END
        """)

        # Lightweight additive migrations for databases created by older builds.
        cursor.execute("PRAGMA table_info(memories)")
        columns = [col[1] for col in cursor.fetchall()]
        if "extra_images" not in columns:
            cursor.execute("ALTER TABLE memories ADD COLUMN extra_images TEXT")
        if "sync_status" not in columns:
            cursor.execute(
                "ALTER TABLE memories ADD COLUMN sync_status TEXT DEFAULT 'PENDING'"
            )
        cursor.execute(
            """
            UPDATE memories
            SET sync_status = 'PENDING'
            WHERE sync_status IS NULL OR TRIM(sync_status) = ''
            """
        )

        self._conn.commit()

    def insert_memory(self, record: MemoryRecord) -> bool:
        with self._write_lock:
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO memories (id, created_at, image_path, ai_summary, app_name, text_content, extra_images, sync_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.id,
                        record.created_at,
                        record.image_path,
                        record.ai_summary,
                        record.app_name,
                        record.text_content,
                        record.extra_images,
                        record.sync_status,
                    ),
                )
                self._conn.commit()
                return True
            except Exception as e:
                logger.error("Insert memory error: %s", e)
                return False

    def get_memory_by_id(self, memory_id: str) -> Optional[MemoryRecord]:
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        if row:
            return MemoryRecord.from_row(row)
        return None

    @staticmethod
    def _memory_filter_clause(
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
    ) -> tuple[str, List[str]]:
        clauses = []
        params = []
        if created_after:
            clauses.append("m.created_at >= ?")
            params.append(created_after)
        if created_before:
            clauses.append("m.created_at < ?")
            params.append(created_before)
        return (" AND ".join(clauses), params)

    def get_all_memories(
        self,
        limit: int = 100,
        offset: int = 0,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
    ) -> List[MemoryRecord]:
        cursor = self._conn.cursor()
        filter_clause, filter_params = self._memory_filter_clause(
            created_after,
            created_before,
        )
        where_sql = f"WHERE {filter_clause}" if filter_clause else ""
        cursor.execute(
            f"SELECT m.* FROM memories m {where_sql} "
            "ORDER BY m.created_at DESC LIMIT ? OFFSET ?",
            (*filter_params, limit, offset),
        )
        rows = cursor.fetchall()
        return [MemoryRecord.from_row(row) for row in rows]

    def get_memory_ids(
        self,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
    ) -> List[str]:
        cursor = self._conn.cursor()
        filter_clause, filter_params = self._memory_filter_clause(
            created_after,
            created_before,
        )
        where_sql = f"WHERE {filter_clause}" if filter_clause else ""
        cursor.execute(
            f"SELECT m.id FROM memories m {where_sql} ORDER BY m.created_at DESC",
            filter_params,
        )
        return [row[0] for row in cursor.fetchall()]

    def search_memories(
        self,
        query: str,
        limit: int = 20,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
    ) -> List[MemoryRecord]:
        cursor = self._conn.cursor()
        filter_clause, filter_params = self._memory_filter_clause(
            created_after,
            created_before,
        )
        filter_sql = f" AND {filter_clause}" if filter_clause else ""
        try:
            cursor.execute(
                f"""
                SELECT m.* FROM memories m
                JOIN memories_fts fts ON m.rowid = fts.rowid
                WHERE memories_fts MATCH ?{filter_sql}
                ORDER BY rank
                LIMIT ?
                """,
                (query, *filter_params, limit),
            )
            rows = cursor.fetchall()
            if rows:
                return [MemoryRecord.from_row(row) for row in rows]
        except Exception:
            pass

        cursor.execute(
            f"""
            SELECT m.* FROM memories m
            WHERE (m.ai_summary LIKE ? OR m.text_content LIKE ?){filter_sql}
            ORDER BY m.created_at DESC
            LIMIT ?
            """,
            (f"%{query}%", f"%{query}%", *filter_params, limit),
        )
        rows = cursor.fetchall()
        return [MemoryRecord.from_row(row) for row in rows]

    def update_memory_summary(
        self,
        memory_id: str,
        summary: str,
        sync_status: str = "PENDING",
    ) -> bool:
        with self._write_lock:
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    """
                    UPDATE memories
                    SET ai_summary = ?, sync_status = ?
                    WHERE id = ?
                    """,
                    (summary, sync_status, memory_id),
                )
                self._conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                logger.error("Update memory error: %s", e)
                return False

    def update_memory_text_content(
        self,
        memory_id: str,
        text_content: str,
        sync_status: str = "PENDING",
    ) -> bool:
        with self._write_lock:
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    """
                    UPDATE memories
                    SET text_content = ?, sync_status = ?
                    WHERE id = ?
                    """,
                    (text_content, sync_status, memory_id),
                )
                self._conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                logger.error("Update memory OCR text error: %s", e)
                return False

    def update_memory_sync_status(self, memory_id: str, sync_status: str) -> bool:
        with self._write_lock:
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    "UPDATE memories SET sync_status = ? WHERE id = ?",
                    (sync_status, memory_id),
                )
                self._conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                logger.error("Update memory sync status error: %s", e)
                return False

    def compare_and_set_memory_sync_status(
        self,
        memory_id: str,
        *,
        expected_ai_summary: Optional[str],
        expected_text_content: Optional[str],
        sync_status: str,
    ) -> bool:
        """Update index status only while the indexed content snapshot is current."""
        with self._write_lock:
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    """
                    UPDATE memories
                    SET sync_status = ?
                    WHERE id = ?
                      AND ai_summary IS ?
                      AND text_content IS ?
                    """,
                    (
                        sync_status,
                        memory_id,
                        expected_ai_summary,
                        expected_text_content,
                    ),
                )
                self._conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                logger.error("Compare-and-set memory sync status error: %s", e)
                return False

    def get_memories_without_text(self) -> List[MemoryRecord]:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT * FROM memories
            WHERE text_content IS NULL OR TRIM(text_content) = ''
            ORDER BY created_at ASC, id ASC
            """
        )
        return [MemoryRecord.from_row(row) for row in cursor.fetchall()]

    def delete_memory(self, memory_id: str) -> bool:
        with self._write_lock:
            try:
                cursor = self._conn.cursor()
                cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
                self._conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                logger.error("Delete memory error: %s", e)
                return False

    def get_memories_count(
        self,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
    ) -> int:
        cursor = self._conn.cursor()
        filter_clause, filter_params = self._memory_filter_clause(
            created_after,
            created_before,
        )
        where_sql = f"WHERE {filter_clause}" if filter_clause else ""
        cursor.execute(
            f"SELECT COUNT(*) FROM memories m {where_sql}",
            filter_params,
        )
        return cursor.fetchone()[0]

    def get_unsynced_memories_count(self) -> int:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) FROM memories
            WHERE sync_status IS NULL OR sync_status != 'SYNCED'
            """
        )
        return cursor.fetchone()[0]

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


sqlite_manager: Optional["SQLiteManager"] = None  # populated by container
