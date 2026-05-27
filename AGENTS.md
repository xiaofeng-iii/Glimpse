# Glimpse 项目运行概况

## 项目简介

**Glimpse** — AI 驱动的桌面记忆检索系统。通过全局快捷键截图 → OCR 识别 → AI 摘要 → 双数据库存储(SQLite + ChromaDB) → 语义搜索。

## 环境

- **Conda 环境名**: `glimpse` (Python 3.10.13)
- **Python 路径**: `C:\Users\RXiaoen\.conda\envs\glimpse\python.exe`
- **运行命令前缀**: `& "C:\Users\RXiaoen\.conda\envs\glimpse\python.exe"`
- **依赖**: 已全部安装 (`pip install -r requirements.txt`，在 glimpse 环境下)
- **缺少 API Key**: 截图分析功能不可用，但搜索/浏览仍可运行

## 架构

```
main.py                 # 单一入口：加载 .env → 初始化 DI 容器 → 启动 UI
container.py            # 依赖注入容器 (DIContainer, 单例/作用域/瞬态)
config/
  path_manager.py       # 路径管理 (所有数据写入 ./GlimpseData/)
  settings_manager.py   # 配置读写 (GlipmseData/config/settings.json)
core/
  capture.py            # 截图管理 (mss, 防抖/集群检测)
  task_queue.py         # 异步任务队列 (ThreadPoolExecutor)
db/
  sqlite_manager.py     # SQLite (MemoryRecord, CRUD, FTS5 全文搜索)
  chroma_manager.py     # ChromaDB 向量数据库
services/
  memory_service.py     # 记忆编排 (OCR → AI摘要 → 双写)
  search_service.py     # 搜索 (text/vector/hybrid, RRF 合并)
  ai_client.py          # OpenAI API 客户端 (vision + text)
  ocr_engine.py         # OCR (RapidOCR, NativeOCR 回退)
  embedding_client.py   # 文本嵌入 (sentence-transformers, 余弦相似度)
  keyboard_manager.py   # 全局快捷键 (pynput)
  hotkey_utils.py       # 快捷键格式转换 (pynput ↔ QKeySequence)
ui/
  main_window.py        # 主窗口 (PySide6, 托盘图标, 搜索)
  settings_dialog.py    # 设置对话框 (AI/OCR/快捷键/截图 配置)
  signals.py            # 跨线程信号总线
```

## 运行

```powershell
& "C:\Users\RXiaoen\.conda\envs\glimpse\python.exe" main.py
```

快捷键: `Ctrl+Shift+G` 截图, `Ctrl+F` 搜索, `Escape` 清空搜索

## 测试

```powershell
# 全部测试 (302 个)
& "C:\Users\RXiaoen\.conda\envs\glimpse\python.exe" -m pytest tests/ -v

# 仅单元测试 (255 个)
& "C:\Users\RXiaoen\.conda\envs\glimpse\python.exe" -m pytest tests/unit/ -v

# 仅集成测试 (47 个)
& "C:\Users\RXiaoen\.conda\envs\glimpse\python.exe" -m pytest tests/integration/ -v
```

工作目录: `5.25Glimpse/`

## 关键约定

- **DI 容器**: 所有服务通过 `container.get("name")` 获取，不直接 import 模块级实例
- **路径**: 所有数据强制写入 `./GlimpseData/`，由 `PathManager` 路由
- **数据库**: SQLite (元数据+FTS5) + ChromaDB (向量嵌入)，通过 UUID 关联
- **约束并发**: `MemoryService` 用 `Semaphore(5)` 限制同时创建的记忆数
- **中文搜索**: FTS5 不支持中文分词，`search_memories()` 有 LIKE 回退逻辑
- **Mock 测试**: 单元测试大量使用 `unittest.mock`；集成测试用真实 DB + Mock AI/OCR
