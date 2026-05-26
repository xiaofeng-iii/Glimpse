"""
SQLite Manager - 封装 SQLite CRUD，包含 FTS5 配置与写入互斥锁
支持多实例隔离并行处理，注入PathManager
"""
import sqlite3
import threading
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from config.path_manager import PathManager


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

        # Migration: add extra_images column if not exists
        cursor.execute("PRAGMA table_info(memories)")
        columns = [col[1] for col in cursor.fetchall()]
        if "extra_images" not in columns:
            cursor.execute("ALTER TABLE memories ADD COLUMN extra_images TEXT")
            self._conn.commit()

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
                print(f"Insert memory error: {e}")
                return False

    def get_memory_by_id(self, memory_id: str) -> Optional[MemoryRecord]:
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        if row:
            return MemoryRecord.from_row(row)
        return None

    def get_all_memories(self, limit: int = 100, offset: int = 0) -> List[MemoryRecord]:
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM memories ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = cursor.fetchall()
        return [MemoryRecord.from_row(row) for row in rows]

    def search_memories(self, query: str, limit: int = 20) -> List[MemoryRecord]:
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                """
                SELECT m.* FROM memories m
                JOIN memories_fts fts ON m.rowid = fts.rowid
                WHERE memories_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            )
            rows = cursor.fetchall()
            if rows:
                return [MemoryRecord.from_row(row) for row in rows]
        except Exception:
            pass

        cursor.execute(
            """
            SELECT m.* FROM memories m
            WHERE m.ai_summary LIKE ? OR m.text_content LIKE ?
            ORDER BY m.created_at DESC
            LIMIT ?
            """,
            (f"%{query}%", f"%{query}%", limit),
        )
        rows = cursor.fetchall()
        return [MemoryRecord.from_row(row) for row in rows]

    def update_memory_summary(self, memory_id: str, summary: str) -> bool:
        with self._write_lock:
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    "UPDATE memories SET ai_summary = ? WHERE id = ?",
                    (summary, memory_id),
                )
                self._conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                print(f"Update memory error: {e}")
                return False

    def delete_memory(self, memory_id: str) -> bool:
        with self._write_lock:
            try:
                cursor = self._conn.cursor()
                cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
                self._conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                print(f"Delete memory error: {e}")
                return False

    def get_memories_count(self) -> int:
        cursor = self._conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM memories")
        return cursor.fetchone()[0]

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


sqlite_manager: Optional["SQLiteManager"] = None  # populated by container
