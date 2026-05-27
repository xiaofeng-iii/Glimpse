#!/usr/bin/env python3
"""
诊断搜索数据库内容
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.path_manager import PathManager
from db.sqlite_manager import SQLiteManager
import sqlite3

pm = PathManager()
conn = sqlite3.connect(str(pm.sqlite_path))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=" * 60)
print("诊断 1: 检查 memories 表内容")
print("=" * 60)
cursor.execute("SELECT COUNT(*) FROM memories")
count = cursor.fetchone()[0]
print(f"总记忆数: {count}")

print("\n所有记忆的 ai_summary 和 text_content 前50字:")
cursor.execute("SELECT id, ai_summary, text_content FROM memories")
for row in cursor.fetchall():
    ai = (row['ai_summary'] or '')[:50]
    text = (row['text_content'] or '')[:50]
    print(f"\nID: {row['id'][:8]}")
    print(f"  AI摘要: {ai}")
    print(f"  OCR文本: {text}")

print("\n" + "=" * 60)
print("诊断 2: 检查 FTS5 虚拟表")
print("=" * 60)
try:
    cursor.execute("SELECT COUNT(*) FROM memories_fts")
    fts_count = cursor.fetchone()[0]
    print(f"FTS5 索引行数: {fts_count}")
    
    print("\nFTS5 表内容样例:")
    cursor.execute("SELECT * FROM memories_fts LIMIT 3")
    for row in cursor.fetchall():
        print(f"  {dict(row)}")
except Exception as e:
    print(f"FTS5 表访问失败: {e}")

print("\n" + "=" * 60)
print("诊断 3: 测试关键词 '截图' 在 FTS5 中的匹配")
print("=" * 60)
try:
    cursor.execute("SELECT rowid, * FROM memories_fts WHERE memories_fts MATCH '截图'")
    rows = cursor.fetchall()
    print(f"MATCH '截图' 返回 {len(rows)} 条:")
    for row in rows:
        print(f"  rowid={row['rowid']}, ai_summary={row['ai_summary'][:40] if row['ai_summary'] else 'N/A'}")
except Exception as e:
    print(f"MATCH 失败: {e}")

print("\n" + "=" * 60)
print("诊断 4: 测试 LIKE 查询")
print("=" * 60)
cursor.execute("SELECT id, ai_summary, text_content FROM memories WHERE ai_summary LIKE '%截图%' OR text_content LIKE '%截图%'")
rows = cursor.fetchall()
print(f"LIKE '%截图%' 返回 {len(rows)} 条:")
for row in rows:
    print(f"  ID={row['id'][:8]}, ai={row['ai_summary'][:40] if row['ai_summary'] else 'N/A'}")

conn.close()
