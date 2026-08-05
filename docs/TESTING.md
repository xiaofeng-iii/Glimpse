# Glimpse 测试与验证

本文档只记录当前可执行的验证方式。测试配置位于根目录 `pyproject.toml`，
Python 命令使用 Conda `glimpse` 环境。

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
npm install
npm run test:run
npm run build
```

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
| `services/memory_service.py` | memory service 单测 + AI 管道 + database sync |
| `services/search_service.py` | search service 单测 + search pipeline |
| `core/capture.py` | capture 单测 + capture-to-storage |
| `db/` | 对应 DB 单测 + database sync |
| `api/` | `tests/test_api.py` + 对应 API 单测 |
| Vue 组件或 stores | `npm run test:run` + `npm run build` + 手动检查受影响流程 |
| Tauri/Rust 或 sidecar | 前端构建 + `build_release.bat` |
| 设置或快捷键 | settings、hotkey、keyboard 单测 |

## 4. 外部服务

默认测试不得要求真实 API Key。真实 OpenAI 兼容服务只用于显式的人工或专项
集成验证，且不得把密钥、响应正文或用户截图提交到仓库。

Embedding 模型首次加载可能较慢；测试应优先使用 fixture 或 mock，专项搜索
验证再加载真实模型。

## 5. 当前已知测试问题

完整测试套件存在一个测试隔离问题：

- `tests/unit/api/test_hotkeys.py` 在模块级注册 `api.desktop_actions` stub。
- 该 stub 只有 `capture_and_analyze`，没有 `capture_only`。
- 当它先于 `tests/test_api.py` 导入时，11 个 API 测试在收集后的 setup 阶段
  报错。
- 单独运行 `tests/test_api.py` 时 11 项全部通过。

修复标准是让测试替身在用例结束后恢复 `sys.modules`，或补齐路由导入所需
接口；在修复前，不应把这组顺序错误解释为生产代码缺少 `capture_only`。

## 6. 完成标准

- 运行与改动范围相匹配的测试。
- 新行为有对应的单元或集成验证。
- 前端改动至少通过 `npm run build`。
- 前端新行为需要对应 Vitest 组件或 store 测试，并通过 `npm run test:run`。
- 不依赖测试执行顺序。
- 不在测试中写入真实 `GlimpseData/`。
- 失败时报告实际命令、通过数和失败原因，不以“环境问题”笼统代替。
