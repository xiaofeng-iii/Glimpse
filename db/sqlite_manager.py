"""
SQLite Manager - 封装 SQLite CRUD，包含 FTS5 配置与写入互斥锁
支持多实例隔离并行处理，注入PathManager
"""
import sqlite3
import threading
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict, Any, TypedDict, TYPE_CHECKING
from pathlib import Path

from utils.logger import get_logger
from utils.tag_names import normalize_tag_names

if TYPE_CHECKING:
    from config.path_manager import PathManager

logger = get_logger(__name__)


@dataclass
class TagRecord:
    id: int
    name: str


class TagSummaryDict(TypedDict):
    """One row of get_all_tags(): the tag entity plus its distinct memory count."""

    id: int
    name: str
    memory_count: int


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
    analysis_status: str = "COMPLETED"
    memory_type: str = "screenshot"
    match_sources: List[str] = field(default_factory=list)
    # 运行时字段：由关联表单独加载，不来自 memories 行。
    tags: List[TagRecord] = field(default_factory=list)
    # 用户手动键入的文本（与 AI 摘要分离；仅部分图片记忆携带）。
    # 必须保持在最后一个字段：旧库的按列位读取分支依赖既有顺序。
    user_text: Optional[str] = None

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
                analysis_status=(
                    row["analysis_status"]
                    if "analysis_status" in row.keys() and row["analysis_status"]
                    else "COMPLETED"
                ),
                memory_type=(
                    row["memory_type"]
                    if "memory_type" in row.keys() and row["memory_type"]
                    else "screenshot"
                ),
                user_text=row["user_text"] if "user_text" in row.keys() else None,
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
                memory_type=row[8] if len(row) > 8 and row[8] else "screenshot",
                analysis_status=row[9] if len(row) > 9 and row[9] else "COMPLETED",
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
            memory_type="screenshot",
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
                sync_status TEXT DEFAULT 'PENDING',
                memory_type TEXT NOT NULL DEFAULT 'screenshot',
                analysis_status TEXT NOT NULL DEFAULT 'COMPLETED',
                user_text TEXT
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_created_at
            ON memories(created_at DESC)
        """)

        # user_text 需要先于 FTS 重建就位，重建时才能把该列一并写入索引。
        cursor.execute("PRAGMA table_info(memories)")
        columns = [col[1] for col in cursor.fetchall()]
        if "user_text" not in columns:
            cursor.execute("ALTER TABLE memories ADD COLUMN user_text TEXT")

        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
            USING fts5(ai_summary, text_content, user_text, content='memories', content_rowid='rowid')
        """)

        # 旧库的 FTS 表只有 ai_summary/text_content 两列；FTS5 不支持加列，
        # 只能整表重建并从 memories 重新灌入。
        cursor.execute("PRAGMA table_info(memories_fts)")
        fts_columns = [col[1] for col in cursor.fetchall()]
        if fts_columns and "user_text" not in fts_columns:
            cursor.execute("DROP TABLE memories_fts")
            cursor.execute("""
                CREATE VIRTUAL TABLE memories_fts
                USING fts5(ai_summary, text_content, user_text, content='memories', content_rowid='rowid')
            """)
            cursor.execute("""
                INSERT INTO memories_fts(rowid, ai_summary, text_content, user_text)
                SELECT rowid, ai_summary, text_content, user_text FROM memories
            """)

        # 触发器用 DROP+CREATE 而非 IF NOT EXISTS：旧库里的两列版本必须被三列版本替换。
        cursor.execute("DROP TRIGGER IF EXISTS memories_ai")
        cursor.execute("""
            CREATE TRIGGER memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, ai_summary, text_content, user_text)
                VALUES (new.rowid, new.ai_summary, new.text_content, new.user_text);
            END
        """)

        cursor.execute("DROP TRIGGER IF EXISTS memories_au")
        cursor.execute("""
            CREATE TRIGGER memories_au AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, ai_summary, text_content, user_text)
                VALUES ('delete', old.rowid, old.ai_summary, old.text_content, old.user_text);
                INSERT INTO memories_fts(rowid, ai_summary, text_content, user_text)
                VALUES (new.rowid, new.ai_summary, new.text_content, new.user_text);
            END
        """)

        cursor.execute("DROP TRIGGER IF EXISTS memories_ad")
        cursor.execute("""
            CREATE TRIGGER memories_ad AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, ai_summary, text_content, user_text)
                VALUES ('delete', old.rowid, old.ai_summary, old.text_content, old.user_text);
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
        if "memory_type" not in columns:
            cursor.execute(
                "ALTER TABLE memories ADD COLUMN memory_type TEXT NOT NULL "
                "DEFAULT 'screenshot'"
            )
        if "analysis_status" not in columns:
            cursor.execute(
                "ALTER TABLE memories ADD COLUMN analysis_status TEXT NOT NULL "
                "DEFAULT 'COMPLETED'"
            )
        cursor.execute(
            """
            UPDATE memories
            SET sync_status = 'PENDING'
            WHERE sync_status IS NULL OR TRIM(sync_status) = ''
            """
        )
        cursor.execute(
            """
            UPDATE memories
            SET memory_type = 'screenshot'
            WHERE memory_type IS NULL OR TRIM(memory_type) = ''
            """
        )
        cursor.execute(
            """
            UPDATE memories
            SET analysis_status = 'COMPLETED'
            WHERE analysis_status IS NULL OR TRIM(analysis_status) = ''
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memories_type_created_at
            ON memories(memory_type, created_at DESC)
            """
        )

        # 标签实体与记忆-标签关联：独立于 memories 主表，标签更新不触发主表
        # AFTER UPDATE 触发器，也就不会引发 FTS 重写。
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_tags (
                memory_id TEXT NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (memory_id, tag_id)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_tags_tag_id
            ON memory_tags(tag_id, memory_id)
        """)

        self._conn.commit()

    def insert_memory(self, record: MemoryRecord) -> bool:
        with self._write_lock:
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO memories (id, created_at, image_path, ai_summary, app_name, text_content, extra_images, sync_status, memory_type, analysis_status, user_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        record.memory_type,
                        record.analysis_status,
                        record.user_text,
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
            return self._hydrate_tags([MemoryRecord.from_row(row)])[0]
        return None

    def _hydrate_tags(self, records: List[MemoryRecord]) -> List[MemoryRecord]:
        """Fill each record's tags from the association table in batched queries."""
        if not records:
            return records
        tags_by_memory: Dict[str, List[TagRecord]] = {
            record.id: [] for record in records
        }
        memory_ids = list(tags_by_memory.keys())
        cursor = self._conn.cursor()
        # SQLite caps bound parameters per statement; chunk well below 999.
        chunk_size = 500
        for start in range(0, len(memory_ids), chunk_size):
            chunk = memory_ids[start : start + chunk_size]
            placeholders = ", ".join("?" for _ in chunk)
            cursor.execute(
                f"""
                SELECT mt.memory_id, t.id, t.name
                FROM memory_tags mt
                JOIN tags t ON t.id = mt.tag_id
                WHERE mt.memory_id IN ({placeholders})
                ORDER BY t.name COLLATE NOCASE, t.name
                """,
                chunk,
            )
            for memory_id, tag_id, name in cursor.fetchall():
                tags_by_memory[memory_id].append(TagRecord(id=tag_id, name=name))
        for record in records:
            record.tags = tags_by_memory[record.id]
        return records

    def set_memory_tags(
        self,
        memory_id: str,
        tag_names: List[str],
    ) -> Optional[MemoryRecord]:
        """Replace a memory's tag associations atomically; None if missing."""
        names = normalize_tag_names(tag_names)
        with self._write_lock:
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM memories WHERE id = ?", (memory_id,)
                )
                if cursor.fetchone() is None:
                    return None
                tag_ids = [self._get_or_create_tag_id(cursor, name) for name in names]
                cursor.execute(
                    "DELETE FROM memory_tags WHERE memory_id = ?", (memory_id,)
                )
                cursor.executemany(
                    "INSERT INTO memory_tags (memory_id, tag_id) VALUES (?, ?)",
                    [(memory_id, tag_id) for tag_id in tag_ids],
                )
                self._delete_orphaned_tags(cursor)
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return self.get_memory_by_id(memory_id)

    @staticmethod
    def _delete_orphaned_tags(cursor) -> None:
        # 标签没有独立生命周期：失去全部关联（含记忆被删除）即随之删除。
        cursor.execute(
            "DELETE FROM tags WHERE id NOT IN (SELECT tag_id FROM memory_tags)"
        )

    @staticmethod
    def _get_or_create_tag_id(cursor, name: str) -> int:
        # NOCASE 只覆盖 ASCII 大小写；请求级的完整去重由 normalize_tag_names 完成。
        cursor.execute("SELECT id FROM tags WHERE name = ? COLLATE NOCASE", (name,))
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute("INSERT INTO tags (name) VALUES (?)", (name,))
        return cursor.lastrowid

    def get_all_tags(self) -> List[TagSummaryDict]:
        """All tags with their distinct memory counts; orphans are auto-deleted,
        so every listed tag has at least one association."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT t.id, t.name, COUNT(DISTINCT mt.memory_id) AS memory_count
            FROM tags t
            LEFT JOIN memory_tags mt ON mt.tag_id = t.id
            GROUP BY t.id, t.name
            ORDER BY memory_count DESC, t.name COLLATE NOCASE, t.name
            """
        )
        return [
            {"id": row["id"], "name": row["name"], "memory_count": row["memory_count"]}
            for row in cursor.fetchall()
        ]

    @staticmethod
    def _memory_filter_clause(
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
        memory_type: Optional[str] = None,
        tag_ids: Optional[List[int]] = None,
    ) -> tuple[str, List[Any]]:
        clauses = []
        params: List[Any] = []
        if created_after:
            clauses.append("m.created_at >= ?")
            params.append(created_after)
        if created_before:
            clauses.append("m.created_at < ?")
            params.append(created_before)
        if memory_type:
            clauses.append("m.memory_type = ?")
            params.append(memory_type)
        if tag_ids:
            # EXISTS 而不是 JOIN：多标签记忆不会因关联多行而在结果中重复。
            placeholders = ", ".join("?" for _ in tag_ids)
            clauses.append(
                "EXISTS (SELECT 1 FROM memory_tags mt "
                f"WHERE mt.memory_id = m.id AND mt.tag_id IN ({placeholders}))"
            )
            params.extend(tag_ids)
        return (" AND ".join(clauses), params)

    def get_all_memories(
        self,
        limit: int = 100,
        offset: int = 0,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
        memory_type: Optional[str] = None,
        tag_ids: Optional[List[int]] = None,
    ) -> List[MemoryRecord]:
        cursor = self._conn.cursor()
        filter_clause, filter_params = self._memory_filter_clause(
            created_after,
            created_before,
            memory_type,
            tag_ids,
        )
        where_sql = f"WHERE {filter_clause}" if filter_clause else ""
        cursor.execute(
            f"SELECT m.* FROM memories m {where_sql} "
            "ORDER BY m.created_at DESC LIMIT ? OFFSET ?",
            (*filter_params, limit, offset),
        )
        rows = cursor.fetchall()
        return self._hydrate_tags([MemoryRecord.from_row(row) for row in rows])

    def get_memory_ids(
        self,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
        memory_type: Optional[str] = None,
        tag_ids: Optional[List[int]] = None,
    ) -> List[str]:
        cursor = self._conn.cursor()
        filter_clause, filter_params = self._memory_filter_clause(
            created_after,
            created_before,
            memory_type,
            tag_ids,
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
        memory_type: Optional[str] = None,
        tag_ids: Optional[List[int]] = None,
    ) -> List[MemoryRecord]:
        cursor = self._conn.cursor()
        filter_clause, filter_params = self._memory_filter_clause(
            created_after,
            created_before,
            memory_type,
            tag_ids,
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
                return self._hydrate_tags([MemoryRecord.from_row(row) for row in rows])
        except Exception:
            pass

        cursor.execute(
            f"""
            SELECT m.* FROM memories m
            WHERE (m.ai_summary LIKE ? OR m.text_content LIKE ? OR m.user_text LIKE ?){filter_sql}
            ORDER BY m.created_at DESC
            LIMIT ?
            """,
            (f"%{query}%", f"%{query}%", f"%{query}%", *filter_params, limit),
        )
        rows = cursor.fetchall()
        return self._hydrate_tags([MemoryRecord.from_row(row) for row in rows])

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

    def update_memory_user_text(
        self,
        memory_id: str,
        user_text: str,
        sync_status: str = "PENDING",
    ) -> bool:
        with self._write_lock:
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    """
                    UPDATE memories
                    SET user_text = ?, sync_status = ?
                    WHERE id = ?
                    """,
                    (user_text, sync_status, memory_id),
                )
                self._conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                logger.error("Update memory user text error: %s", e)
                return False

    def update_memory_analysis(
        self,
        memory_id: str,
        ai_summary: str,
        text_content: str,
        *,
        analysis_status: str = "COMPLETED",
        sync_status: str = "PENDING",
    ) -> bool:
        """Commit OCR and summary output together so observers see one stable state."""
        with self._write_lock:
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    """
                    UPDATE memories
                    SET ai_summary = ?, text_content = ?,
                        analysis_status = ?, sync_status = ?
                    WHERE id = ?
                    """,
                    (
                        ai_summary,
                        text_content,
                        analysis_status,
                        sync_status,
                        memory_id,
                    ),
                )
                self._conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                logger.error("Update memory analysis error: %s", e)
                return False

    def update_memory_analysis_status(
        self,
        memory_id: str,
        analysis_status: str,
    ) -> bool:
        with self._write_lock:
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    "UPDATE memories SET analysis_status = ? WHERE id = ?",
                    (analysis_status, memory_id),
                )
                self._conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                logger.error("Update memory analysis status error: %s", e)
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
            WHERE (text_content IS NULL OR TRIM(text_content) = '')
              AND memory_type != 'text'
            ORDER BY created_at ASC, id ASC
            """
        )
        return [MemoryRecord.from_row(row) for row in cursor.fetchall()]

    def get_all_image_memories(self) -> List[MemoryRecord]:
        """Return every settled image-backed memory for a full OCR repair."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT * FROM memories
            WHERE memory_type != 'text'
              AND analysis_status != 'PROCESSING'
              AND image_path IS NOT NULL
              AND TRIM(image_path) != ''
            ORDER BY created_at ASC, id ASC
            """
        )
        return [MemoryRecord.from_row(row) for row in cursor.fetchall()]

    def delete_memory(self, memory_id: str) -> bool:
        with self._write_lock:
            try:
                cursor = self._conn.cursor()
                cursor.execute(
                    "DELETE FROM memory_tags WHERE memory_id = ?", (memory_id,)
                )
                cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
                deleted = cursor.rowcount > 0
                self._delete_orphaned_tags(cursor)
                self._conn.commit()
                return deleted
            except Exception as e:
                self._conn.rollback()
                logger.error("Delete memory error: %s", e)
                return False

    def get_memories_count(
        self,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
        memory_type: Optional[str] = None,
        tag_ids: Optional[List[int]] = None,
    ) -> int:
        cursor = self._conn.cursor()
        filter_clause, filter_params = self._memory_filter_clause(
            created_after,
            created_before,
            memory_type,
            tag_ids,
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
