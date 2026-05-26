# Glimpse 前端架构文档

## 1. 技术栈

- **UI 框架**: PySide6 (Qt for Python)
- **架构模式**: 信号/槽 (Signals/Slots) + 依赖注入 (DI Container)
- **跨线程通信**: 全局信号总线 (`ui/signals.py`)
- **样式**: 内联代码设置（暂无 QSS 样式表，可扩展）

---

## 2. 目录结构

```
ui/
├── __init__.py          # UI 包初始化
├── main_window.py       # 主窗口（核心界面）
├── settings_dialog.py   # 设置对话框
└── signals.py           # 全局信号总线
```

---

## 3. 核心概念

### 3.1 全局信号总线 (UISignals)

**文件**: `ui/signals.py`

采用单例模式实现跨模块、跨线程的解耦通信。所有业务逻辑通过信号通知 UI，UI 不直接调用服务方法。

```python
signals.screenshot_completed.connect(self._on_screenshot_complete)
signals.memory_saved.connect(self._on_memory_saved)
signals.error_occurred.connect(self._on_error)
```

**可用信号清单**:

| 信号名 | 参数 | 触发场景 |
|--------|------|----------|
| `screenshot_requested` | 无 | 全局快捷键触发截图 |
| `screenshot_completed` | `str` (image_path) | 截图完成 |
| `memory_saved` | `str` (memory_id) | 记忆保存成功 |
| `memory_deleted` | `str` (memory_id) | 记忆删除 |
| `search_requested` | `str` (query) | 搜索请求 |
| `search_completed` | `list` (results) | 搜索完成 |
| `error_occurred` | `str` (error_msg) | 错误发生 |
| `status_updated` | `str` (status) | 状态更新 |
| `progress_updated` | `int`, `str` | 进度更新 |

### 3.2 依赖注入容器

**文件**: `container.py`

所有 UI 组件通过 `container.get("service_name")` 获取服务，不直接实例化。这保证了：
- 单元测试可 Mock
- 服务生命周期统一管理
- 解耦 UI 与业务逻辑

```python
# 正确做法
search_service = container.get("search_service")

# 错误做法
from services.search_service import SearchService  # 不要这样做
```

### 3.3 UI 渲染模式

当前采用**命令式编程**（直接操作控件），而非声明式。所有状态变更通过方法调用直接更新 QListWidget、QLabel 等控件。

---

## 4. 数据流

```
用户操作/快捷键 → UI 事件处理 → 调用服务（通过 container）
                                          ↓
服务完成 → 发射信号 → UI 槽函数接收 → 更新界面
```

**关键特征**:
- UI 层只负责**显示**和**用户输入捕获**
- 所有业务逻辑（搜索、截图、OCR、AI）在 services/ 层完成
- 状态变更通过信号通知，UI 被动刷新

---

## 5. 样式现状

- **当前**: 无统一样式表，使用 Qt 默认主题
- **主题设置**: `settings_dialog.py` 中有主题选择（light/dark/system），但实现为空
- **可改进**: 
  - 添加 `resources/styles.qss` 统一样式表
  - 实现 QPalette 动态切换
  - 支持高 DPI 适配

---

## 6. 扩展指南

### 6.1 添加新窗口

1. 在 `ui/` 创建新文件（如 `memory_detail_dialog.py`）
2. 继承 `QDialog` 或 `QWidget`
3. 通过 `container.get()` 获取需要的服务
4. 如需跨窗口通信，使用 `signals` 发射信号

### 6.2 添加新信号

1. 在 `ui/signals.py` 的 `UISignals` 类中添加：
   ```python
   my_new_signal = Signal(str)
   ```
2. 发射方: `signals.my_new_signal.emit("data")`
3. 接收方: `signals.my_new_signal.connect(self._handler)`

### 6.3 修改搜索 UI

搜索相关代码集中在 `main_window.py`:
- `_setup_ui()` 第 45-59 行：搜索栏布局（含 source_filter_combo）
- `_do_search()` 第 289-297 行：搜索执行
- `_update_memory_list()` 第 197-208 行：结果渲染

---

## 7. 已知限制

1. **无 UI 测试框架**：当前只有服务层测试，缺少 UI 自动化测试
2. **样式分散**：没有统一的 QSS 文件，样式难以维护
3. **硬编码尺寸**：窗口大小、布局间距均为硬编码
4. **缺少国际化**：中文标签硬编码在 Python 文件中

---

## 8. 相关文档

- [UI 组件清单](./UI_COMPONENTS.md)
- [用户交互流程](./UI_FLOWS.md)
- [前端待办事项](./FRONTEND_TODO.md)
- [API 接口规范](./API_INTERFACES.md)
