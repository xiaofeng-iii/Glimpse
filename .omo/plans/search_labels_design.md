# 搜索来源标记与过滤设计文档 (Search Labels & Filtering Design)

## 1. 目标 (Objective)
优化现有的混合搜索结果展示，让用户清楚地知道搜索结果是来自于"文本精确匹配"还是"向量语义相关"。提升搜索结果的可解释性，并允许用户通过来源进行过滤。

## 2. 核心架构修改 (Architecture Changes)

### 2.1 数据模型 (Data Model)
- 修改 `db/sqlite_manager.py` 中的 `MemoryRecord` dataclass，新增字段：
  `match_sources: List[str] = field(default_factory=list)`
  - 这个字段**不会**存入数据库，仅作为内存中的传输标记。

### 2.2 搜索服务 (Search Service)
- 修改 `services/search_service.py` 的 `_search_hybrid` 方法：
  - 在分别拿到 `text_results` 和 `vector_results` 后，合并过程中为每个 `MemoryRecord` 注入 `match_sources`。
  - 如果 ID 存在于 `text_results` 中，附加 `"OCR"`。
  - 如果 ID 存在于 `vector_results` 中，附加 `"语义"`。
- 新增过滤支持：`search(self, query: str, limit: int = 20, source_filter: str = "all")`
  - 如果 `source_filter == "ocr"`，只执行 `_search_text` 并强行打上 `"OCR"` 标签。
  - 如果 `source_filter == "semantic"`，只执行 `_search_vector` 并强行打上 `"语义"` 标签。
  - 如果 `source_filter == "all"`，执行原本的 `_search_hybrid`。

## 3. UI 交互修改 (UI Changes)

### 3.1 搜索工具栏 (MainWindow Toolbar)
- 修改 `ui/main_window.py` 中的工具栏布局：
  - 在 `search_input` 旁边新增一个 `QComboBox` (下拉框)，命名为 `search_filter_combo`。
  - 下拉框选项：`["综合结果", "仅看 OCR", "仅看语义"]`。
  - 连接下拉框的 `currentIndexChanged` 信号到 `_do_search`，以支持即时刷新。

### 3.2 列表渲染 (MainWindow ListWidget)
- 修改 `_update_memory_list` 渲染逻辑：
  - 在拼装显示的字符串前，读取 `memory.match_sources` (需使用 getattr 安全读取，因为旧记录可能没有)。
  - 生成前缀徽章，例如：`[OCR]`、`[语义]` 或 `[OCR][语义]`。
  - 列表项最终显示格式：`[OCR][语义] 2026-05-26 12:00:00 - 摘要内容...`。

## 4. 边界情况与错误处理 (Edge Cases)
- **空搜索框**：如果搜索框为空（获取最近记忆），则 `match_sources` 为空，UI 不显示任何前缀徽章。
- **降级处理**：如果 AI / Embedding 服务未配置导致无法向量搜索，混合搜索退化为文本搜索，此时结果均只携带 `[OCR]` 徽章。

## 5. 验收标准 (Acceptance Criteria)
1. 在搜索框输入查询词，结果列表正确带有 `[OCR]` 和/或 `[语义]` 前缀。
2. 更改下拉框过滤条件，列表能即时刷新，且仅显示对应来源的结果。
3. 单元测试更新：`TestSearchService` 断言合并结果的 `match_sources` 赋值正确。
