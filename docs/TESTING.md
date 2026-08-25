# Glimpse 测试与验证

本文档只记录当前可执行的验证方式。测试配置位于根目录 `pyproject.toml`，
Python 命令使用 Conda `glimpse` 环境。

## 0. 执行策略

默认只做与当前改动直接相关的最小验证，不自动执行全量测试。验证深度按改动类型
区分：

| 改动类型 | 默认策略 |
|---|---|
| 前端细小样式、间距、颜色或文案调整 | 不运行测试；必要时只确认页面能够渲染、显示无明显错误 |
| 前端组件、页面或交互行为 | 只做受影响组件或流程的最小检查，并确认页面能够渲染；不自动运行全量 Vitest、完整构建或全量 E2E |
| 后端模块或 API | 只运行受影响模块的最小单元或 API 测试；仅在跨模块边界受影响时补充直接相关集成检查 |
| Tauri、sidecar 或发布配置 | 只运行能够证明受影响链路的最小构建或冒烟检查 |
| 全量验证 | 仅在用户明确要求时运行完整后端、前端、安装包或跨层测试 |

每次交付都应说明实际运行和未运行的验证。此策略是默认执行边界；安全、CI 或正式
发布流程中明确要求的检查仍按其要求执行。

## 1. 常用命令

后端快速检查：

```powershell
conda run -n glimpse python -m pytest tests/unit -q
conda run -n glimpse python -m pytest tests/integration -q
conda run -n glimpse python -m pytest tests/test_api.py -q
```

完整后端测试：

```powershell
conda run -n glimpse python -m pytest -q
```

前端单元/组件测试、类型检查与生产构建：

```powershell
cd glimpse-frontend
npm ci
npm run test:run
npm run build
```

日常开发已安装依赖时可直接运行测试和构建；全新检出、CI 或需要严格按锁文件
复现依赖时使用 `npm ci`。

开发时持续监听受影响的前端测试：

```powershell
cd glimpse-frontend
npm test
```

完整 Windows 安装包验证：

```powershell
.\build_release.bat
```

安装包构建较慢，只有改动 Tauri、sidecar、依赖收集或发布配置时才需要运行。

## 2. 测试分层

| 目录 | 验证内容 |
|---|---|
| `tests/unit/config/` | 路径与设置 |
| `tests/unit/core/` | 截图、集群缓冲、任务队列 |
| `tests/unit/db/` | SQLite 与 ChromaDB |
| `tests/unit/services/` | AI、Embedding、快捷键、记忆与搜索 |
| `tests/unit/api/` | API 辅助逻辑 |
| `tests/unit/ui/` | 旧 Qt 回退界面的关键行为 |
| `tests/integration/` | AI 管道、双库、搜索和完整记忆生命周期 |
| `tests/test_api.py` | FastAPI 与 WebSocket 边界 |
| `glimpse-frontend/tests/` | Vue 组件、Pinia store、交互与渲染契约（Vitest + Vue Test Utils + jsdom） |

单元测试应隔离网络、屏幕和持久数据库。集成测试可以组合真实业务组件，但仍
应使用临时数据目录和可控的 AI/Embedding 替身。

## 3. 按改动选择验证

| 改动区域 | 最小验证 |
|---|---|
| `services/memory_service.py` | memory service 单测；仅在 AI 或数据库边界受影响时补直接相关检查 |
| `services/search_service.py` | search service 单测；仅在搜索管道边界受影响时补直接相关检查 |
| `core/capture.py` | capture 单测；仅在存储边界受影响时补 capture-to-storage 检查 |
| `db/` | 对应 DB 单测；仅在同步路径受影响时补 database sync 检查 |
| `api/` | 受影响的 `tests/test_api.py` 或对应 API 单测 |
| Vue 组件或 stores | 受影响组件测试（如有）+ 最小渲染/显示检查；仅在逻辑或构建链路受影响时补 `npm run build` |
| Tauri/Rust 或 sidecar | 受影响链路的最小前端构建或冒烟检查；仅在发布配置受影响时运行 `build_release.bat` |
| 设置或快捷键 | settings、hotkey、keyboard 单测 |

## 4. 外部服务

默认测试不得要求真实 API Key。真实 OpenAI 兼容服务只用于显式的人工或专项
集成验证，且不得把密钥、响应正文或用户截图提交到仓库。

Embedding 模型首次加载可能较慢；测试应优先使用 fixture 或 mock，专项搜索
验证再加载真实模型。

## 5. 完成标准

- 运行与改动范围相匹配的最小验证，并记录实际运行和跳过的命令。
- 新行为优先补充对应的单元或集成验证；是否执行完整测试按“执行策略”和用户要求决定。
- 前端行为或构建链路变更时，完成最小渲染检查，必要时补 `npm run build`。
- 全量后端、前端、安装包或跨层测试仅在用户明确要求时执行。
- 不依赖测试执行顺序。
- 不在测试中写入真实 `GlimpseData/`。
- 失败时报告实际命令、通过数和失败原因，不以“环境问题”笼统代替。
