# Glimpse UI 组件清单

## 1. MainWindow (主窗口)

**文件**: `ui/main_window.py`
**继承**: `QMainWindow`

### 1.1 布局结构

```
QMainWindow
├── 菜单栏 (QMenuBar)
│   └── 文件菜单
│       ├── 设置 (QAction)
│       └── 退出 (QAction)
│
├── 中央控件 (QWidget) [QVBoxLayout]
│   ├── 工具栏 (QWidget) [QVBoxLayout]
│   │   ├── 截图按钮 (QPushButton)
│   │   └── 搜索栏 (QHBoxLayout)
│   │       ├── 来源过滤器 (QComboBox)
│   │       └── 搜索输入框 (QLineEdit)
│   │
│   ├── 记忆列表 (QListWidget)
│   └── 详情面板 (QTextEdit, read-only)
│
└── 状态栏 (QStatusBar)
    ├── 状态标签 (QLabel)
    ├── 集群提交按钮 (QPushButton, 初始隐藏)
    └── 集群取消按钮 (QPushButton, 初始隐藏)
```

### 1.2 控件详情

| 控件名 | 类型 | 用途 | 信号连接 |
|--------|------|------|----------|
| `screenshot_btn` | QPushButton | 触发截图 | `clicked → _on_screenshot` |
| `source_filter_combo` | QComboBox | 搜索来源过滤 | `currentIndexChanged → _on_source_filter_changed` |
| `search_input` | QLineEdit | 搜索关键词输入 | `textChanged → _on_search_text_changed` |
| `memory_list` | QListWidget | 显示记忆列表 | `itemClicked → _on_memory_selected` |
| `detail_panel` | QTextEdit | 显示记忆详情 | read-only |
| `_cluster_submit_btn` | QPushButton | 手动提交集群截图 | `clicked → _on_cluster_submit` |
| `_cluster_cancel_btn` | QPushButton | 取消集群截图 | `clicked → _on_cluster_cancel` |
| `status_bar` | QLabel | 显示状态信息 | 无 |

### 1.3 来源过滤器选项

| 显示文本 | 数据值 | 说明 |
|----------|--------|------|
| `综合结果` | `all` | 混合搜索（精确 + 语义） |
| `仅看精确` | `exact` | 仅文本搜索 |
| `仅看语义` | `semantic` | 仅向量搜索 |

### 1.4 快捷键

| 功能 | 默认快捷键 | 配置键 |
|------|-----------|--------|
| 截图 | `Ctrl+Shift+G` | `hotkeys.screenshot` |
| 搜索聚焦 | `Ctrl+F` | `hotkeys.search` |
| 清空搜索 | `Escape` | `hotkeys.clear` |

---

## 2. SettingsDialog (设置对话框)

**文件**: `ui/settings_dialog.py`
**继承**: `QDialog`
**尺寸**: 最小 600×500

### 2.1 选项卡结构

| 选项卡 | 配置项 | 对应控件 |
|--------|--------|----------|
| **快捷键** | 截图/搜索/清除快捷键 | `QKeySequenceEdit` ×3 |
| **截图** | 防抖间隔、最大截图数 | `QDoubleSpinBox`, `QSpinBox` |
| **AI 服务** | API Key、Base URL、模型、超时 | `QLineEdit`, `QSpinBox` |
| **OCR** | 引擎、语言 | `QComboBox` ×2 |
| **界面** | 主题、自动隐藏、启动最小化 | `QComboBox`, `QCheckBox` ×2 |
| **集群截图** | 启用模式、自动提交、最大截图数、超时 | `QCheckBox`, `QSpinBox` ×2 |

AI 服务控件详情:
- **Model**: QLineEdit (free-text), placeholder `gpt-4o-mini`
- **Base URL**: QLineEdit, placeholder `https://api.openai.com/v1`

### 2.2 按钮区域

| 按钮 | 行为 |
|------|------|
| 恢复默认 | 重置所有设置到默认值 |
| 确定 | 保存并关闭对话框 |
| 应用 | 保存但不关闭 |
| 取消 | 放弃更改并关闭 |

---

## 3. 系统托盘

**实现**: `MainWindow._setup_tray_icon()`

| 菜单项 | 行为 |
|--------|------|
| 显示 | `showNormal()` |
| 退出 | `_on_quit()` |

**特性**:
- 点击托盘图标显示窗口
- 关闭窗口时最小化到托盘（非退出）
- 显示气泡提示

---

## 4. 信号连接矩阵

### MainWindow 接收的信号

| 信号 | 发射方 | 槽函数 | 行为 |
|------|--------|--------|------|
| `screenshot_requested` | 全局快捷键 | `_on_screenshot` | 执行截图 |
| `screenshot_completed` | CaptureManager | `_on_screenshot_complete` | 更新状态栏 |
| `memory_saved` | MemoryService | `_on_memory_saved` | 刷新列表 |
| `search_completed` | SearchService | `_on_search_completed` | 显示结果 |
| `error_occurred` | 各服务 | `_on_error` | 显示错误 |
| `status_updated` | 各服务 | `_on_status_updated` | 更新状态 |

### ClusterBuffer 信号

| 信号 | 槽函数 | 行为 |
|------|--------|------|
| `state_changed` | `_on_cluster_state_changed` | 显示/隐藏集群按钮 |
| `countdown_changed` | `_on_cluster_countdown` | 更新倒计时 |
| `flushed` | `_on_cluster_flushed` | 处理集群截图 |
| `discarded` | `_on_cluster_discarded` | 取消集群截图 |

---

## 5. 样式表

**文件**: `ui/styles/light.qss`, `ui/styles/dark.qss`
**加载**: 通过 `ThemeManager` (`ui/theme_manager.py`) 动态加载和切换

- `ui.theme`: `light` / `dark` / `system`
- 存储在 `settings.json` 中，SettingsDialog 可读取和修改
- `ThemeManager` 支持系统主题检测（Windows 注册表 / macOS / Linux GTK）
- QSS 内容以缓存方式加载，避免重复读取

---

## 6. 图标与资源

当前使用**程序化生成的图标**:
- 托盘图标: 24×24 蓝色方块 (`QPixmap` 填充)
- 无外部图片资源

**建议**: 添加 `resources/icons/` 目录存放实际图标文件。

---

## 7. 其他 UI 组件

| 组件 | 文件 | 说明 |
|------|------|------|
| **MemoryDetailDialog** | `ui/memory_detail_dialog.py` | 对话框，展示单条记忆的完整详情 |
| **LoadingSpinner** | `ui/widgets/loading_spinner.py` | 覆盖层，带动画旋转指示器 |
| **SegmentedFilter** | `ui/widgets/segmented_filter.py` | 搜索来源过滤器按钮组 |
| **LocaleManager** | `ui/locale_manager.py` | 国际化管理，提供 `t()` 翻译函数 |
| **ThemeManager** | `ui/theme_manager.py` | 主题切换，加载 QSS 并检测系统主题 |
| **locales/** | `ui/locales/zh-CN.json`, `en-US.json` | 中/英文翻译文件 |
