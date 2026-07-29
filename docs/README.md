# Glimpse 项目文档

本文档是 Glimpse 当前产品、架构与业务流程的事实入口。运行方式以根目录
`README.md` 为准；可执行接口以 FastAPI 的 `/docs` 为准；测试命令见
[`TESTING.md`](./TESTING.md)。

供 AI 长期复用的扩展上下文位于 [`agents/`](./agents/README.md)；通用工作
规则仍以根目录 `AGENTS.md` 为准。

## 1. 产品目标

Glimpse 是一个桌面记忆助手。用户通过快捷键或界面按钮截取屏幕，系统调用
多模态 AI 理解画面、生成摘要并在本地建立索引，之后用户可以通过关键词或
自然语言找回记忆。

产品设计围绕四个原则：

- **低摩擦记录**：用户只负责表达“这值得记住”，不必先分类或整理。
- **召回优先**：同时提供精确搜索和语义搜索，降低对准确关键词的依赖。
- **后台处理**：截图后立即恢复交互，AI、向量化和存储异步完成。
- **本地事实源**：截图、摘要、元数据和向量索引默认保存在本地。

“本地事实源”不等于完全离线：截图会发送给用户配置的 OpenAI 兼容多模态
服务；文本向量由本地模型生成。

## 2. 当前运行形态

```text
Tauri 原生桌面壳
├── 管理窗口、托盘、关闭行为和 Python sidecar
└── 承载 Vue 3 前端
    ├── REST 调用 FastAPI
    └── 通过 WebSocket 接收后台事件

FastAPI / Python
├── api/       HTTP、WebSocket、桌面动作
├── services/  记忆、搜索、AI、向量、快捷键
├── core/      截图、集群缓冲、任务队列
├── db/        SQLite 与 ChromaDB
└── config/    路径和设置
```

主要入口：

| 入口 | 用途 |
|---|---|
| `main.py` | 默认源码入口，启动 Vue + Tauri |
| `main_api.py` | 单独启动 FastAPI 后端 |
| `main_legacy_qt.py` | 旧 PySide6 界面，仅用于回退和调试 |
| `build_release.bat` | 构建 Python sidecar 与 Tauri NSIS 安装包 |

`container.py` 统一注册并关闭 Python 服务。API 通过
`api/dependencies.py` 获取服务，不在路由中自行构造数据库或业务服务。

## 3. 核心流程

### 3.1 单张记忆

```text
快捷键或截图按钮
→ Vue 检查后端状态并最小化窗口
→ POST /api/screenshot/analyze
→ CaptureManager 保存截图
→ MemoryService 后台调用多模态 AI
→ EmbeddingClient 生成本地中文向量
→ SQLite 保存事实记录
→ ChromaDB 保存向量索引
→ WebSocket 广播 memory_saved
→ Vue 刷新记忆列表
```

任务队列不可用时，API 会回退到后台线程继续创建记忆。

### 3.2 集群记忆

集群模式将多张连续截图合并为一条记忆。图片达到数量上限、等待超时或用户
手动提交后，`MemoryService.create_cluster_memory*()` 调用多图 AI 分析，
第一张图作为主图，其余图片记录在 `extra_images`。

### 3.3 搜索

`SearchService.search()` 支持：

| `source` | 行为 |
|---|---|
| `exact` | SQLite FTS5 精确搜索 |
| `semantic` | ChromaDB 语义搜索 |
| `all` | 两路结果使用 RRF 融合 |

语义向量使用 `BAAI/bge-small-zh-v1.5`，首次使用时延迟加载。返回记录通过
`match_sources` 标记“精确”和“语义”来源。

### 3.4 记忆管理

当前界面支持记忆列表、图片缩略图、详情、原图预览、复制摘要和删除。删除及
索引修复必须保持 SQLite 事实记录与 ChromaDB 派生索引的一致性。

## 4. 前端地图

```text
glimpse-frontend/src/
├── views/
│   ├── Home.vue          首页、截图、搜索和集群交互
│   ├── Settings.vue      运行时设置
│   └── MemoryDetail.vue  独立详情页
├── components/           搜索栏、记忆列表、详情、通知、预览等
├── stores/               memories、settings、cluster、notification
├── api/                  REST 与 WebSocket 客户端
├── platform/             Tauri 桌面能力适配
└── router/               `/`、`/settings`、`/memory/:id`
```

Tauri Rust 层负责原生窗口、托盘和后端进程。Vue 不直接访问 Python 模块，
Python 也不直接操作 Vue 状态。

## 5. API 边界

开发环境默认监听 `127.0.0.1:8000`。完整请求和响应模型以
`http://127.0.0.1:8000/docs` 生成的 OpenAPI 页面为准。

| 分组 | 主要能力 |
|---|---|
| `/api/health`、`/api/stats` | 健康状态与双库统计 |
| `/api/screenshot` | 仅截图、截图并分析 |
| `/api/memories` | 列表、详情、删除 |
| `/api/search` | 搜索与语义模型预热 |
| `/api/settings` | 获取、更新、重置、AI 测试、索引修复 |
| `/api/cluster` | 集群状态、提交、取消 |
| `/api/images` | 本地记忆图片读取 |
| `/ws/events` | 后台事件推送 |

主要 WebSocket 事件包括：

- `screenshot_completed`
- `memory_saved`
- `error_occurred`
- 集群状态事件

截图分析接口返回 `accepted` 表示后台任务已接收，不表示 AI 与存储已经完成；
最终结果以 WebSocket 事件为准。

## 6. 数据与配置

SQLite 是事实来源，保存 UUID、时间、图片路径、AI 摘要、来源应用、可选文本、
附加图片和同步状态。ChromaDB 是可重建的语义索引。

开发环境的数据默认位于项目下的 `GlimpseData/`；安装版默认位于：

```text
%LOCALAPPDATA%\Glimpse\GlimpseData
```

设置由 `config/settings_manager.py` 管理，主要包括：

- 全局截图快捷键
- 截图限流窗口和数量
- AI Provider、Base URL、API Key、模型与超时
- 集群模式、数量与超时
- 主题、语言和窗口关闭行为

## 7. 当前边界

- `services/ocr_engine.py` 仍存在并已注册，但当前 `MemoryService` 主链没有调用
  OCR；不要把 OCR 描述为当前记忆创建的必经步骤。
- `ui/` 是旧 PySide6 回退界面；新产品功能优先在 Vue/Tauri 路径实现。
- `app_name` 在当前截图入口通常仍为 `unknown`。
- FastAPI 接口字段优先通过 OpenAPI 与 Pydantic 模型维护，避免在 Markdown
  中重复完整签名。

## 8. 文档维护

- 产品、架构、流程或稳定边界变化时更新本文档。
- 测试命令与测试分层只在 `TESTING.md` 维护。
- 启动、安装和打包命令只在根 `README.md` 维护。
- 旧实现文档进入 `docs/archive/`，不得继续作为当前事实来源。
- 临时分析、AI 草稿和工具输出不得放入 `docs/`。
