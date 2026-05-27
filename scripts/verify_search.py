#!/usr/bin/env python3
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.path_manager import PathManager
from db.sqlite_manager import SQLiteManager

pm = PathManager()
sqlite = SQLiteManager(pm)

print("=== 搜 '截图' ===")
results = sqlite.search_memories("截图", limit=10)
print(f"返回 {len(results)} 条")
for i, r in enumerate(results):
    has_keyword = "截图" in (r.ai_summary or "") or "截图" in (r.text_content or "")
    print(f"{i+1}. [含截图={has_keyword}] {r.ai_summary[:40]}...")

print()
print("=== 搜 '项目' ===")
results = sqlite.search_memories("项目", limit=10)
print(f"返回 {len(results)} 条")
for i, r in enumerate(results):
    has_keyword = "项目" in (r.ai_summary or "") or "项目" in (r.text_content or "")
    print(f"{i+1}. [含项目={has_keyword}] {r.ai_summary[:40]}...")

sqlite.close()
