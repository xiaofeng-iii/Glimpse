# Glimpse

AI 驱动的桌面记忆检索系统。支持截图、AI 摘要、精确检索、语义检索，以及基于 `Vue 3 + Tauri` 的桌面弹窗界面。

当前仓库包含以下入口：

- `python main.py`：默认启动当前主用的 `Vue 3 + Tauri` 桌面界面，Tauri 按需启动 FastAPI 后端
- `python main_api.py`：单独启动 FastAPI 后端，用于 API 或网页开发
- `glimpse-frontend/`：Vue 网页开发与 Tauri 构建入口
- `python main_legacy_qt.py`：保留的旧版 `PySide6` 界面，仅用于回退和调试

## 1. 环境要求

基础要求：

- Python `3.10+`
- Node.js `18+`

如果要运行 Tauri 弹窗，还需要：

- Rust 工具链：`rustup` / `cargo`
- Windows 下的 MSVC C++ 工具链
  - 推荐安装 `Visual Studio 2022 Build Tools`
  - 需要包含 `Desktop development with C++` 或等价的 `MSVC x64/x86 build tools`

## 2. 安装依赖

### Python

安装 Python 依赖：

```bash
pip install -r requirements.txt
```

### 前端

```bash
cd glimpse-frontend
npm install
```

### 发布版打包依赖

仅在构建安装包时需要：

```bash
pip install -r requirements-packaging.txt
```

## 3. 配置 `.env`

复制 `.env.example` 为 `.env`。应用可以在没有 AI 凭据的情况下启动；若要创建
AI 记忆，需要填写：

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
```

如果使用 OpenAI 兼容平台（例如豆包 / Ark），请同时确认：

- `OPENAI_BASE_URL` 指向兼容接口地址
- `MODEL` 填写的是“实际可调用的模型 / endpoint id”
- 不要把控制台展示名称直接填进 `MODEL`

示例见 [`.env.example`](./.env.example)。

## 4. 启动方式

### 方式 A：只启动后端 API

```bash
python main_api.py
```

启动后可访问：

- API 健康检查：`http://127.0.0.1:8000/api/health`
- API 文档：`http://127.0.0.1:8000/docs`

### 方式 B：启动网页开发页

先启动后端：

```bash
python main_api.py
```

再启动前端：

```bash
cd glimpse-frontend
npm run dev
```

浏览器访问：

- `http://localhost:1420`

### 方式 C：启动 Tauri 桌面版

源码环境下推荐直接运行：

```powershell
python main.py
```

`main.py` 会启动 Tauri/Vue 前端，并让 Tauri shell 在需要时自动启动 Python API。

### 方式 D：启动 Tauri 弹窗开发版脚本

推荐优先使用“可见模式”，便于排错：

```powershell
cd D:\path\to\Glimpse
.\start_tauri_visible.bat
```

如果要静默启动，只保留弹窗窗口：

```powershell
cd D:\path\to\Glimpse
.\start_tauri.bat
```

说明：

- `start_tauri_visible.bat`
  - 会显示终端
  - 适合开发和排错
- `start_tauri.bat`
  - 会隐藏控制台
  - 适合日常调试
  - 如果启动失败，请查看 `.logs/tauri-dev.log`

注意：

- 在 PowerShell 中运行批处理脚本要写成 `.\start_tauri.bat`，不能直接写 `start_tauri.bat`
- Tauri 会占用前端开发端口 `1420`
- 如果 `1420` 已被已有的 `npm run dev` 占用，Tauri 会启动失败

## 5. 常用脚本

### Windows 一键启动桌面版

```powershell
.\start.bat
```

该脚本调用 `python main.py`，启动当前 Vue + Tauri 桌面界面。

### Windows 可见模式启动 Tauri

```powershell
.\start_tauri_visible.bat
```

### Windows 静默模式启动 Tauri

```powershell
.\start_tauri.bat
```

### 构建 Windows 安装包

```powershell
.\build_release.bat
```

## 6. 常见问题

### 1. `cargo` / `rustup` 找不到

如果你机器上已经装过 Rust，但 PowerShell 里仍然提示找不到：

- 先关闭当前终端，重新打开
- 再执行 `cargo --version`
- 如果仍然找不到，确认用户目录下存在：
  - `C:\Users\<用户名>\.cargo\bin\cargo.exe`

项目自带的 `start_tauri_visible.bat` 和 `scripts/setup_tauri_env.bat` 会优先尝试把该目录加入 `PATH`。

### 2. `Port 1420 is already in use`

说明已有前端开发服务器在运行。先关闭旧的 `npm run dev` 终端，或结束对应进程，再重新启动 Tauri。

### 3. Tauri 启动“没反应”

多数情况是：

- 用的是静默脚本 `start_tauri.bat`
- 实际已经报错，但控制台被隐藏

优先改用：

```powershell
.\start_tauri_visible.bat
```

如果仍有问题，查看：

- `.logs/tauri-dev.log`
- `.logs/backend-dev.log`

### 4. 快捷键、截图或图片预览没有反应

先确认：

- 后端状态是否为“已连接”
- `http://127.0.0.1:8000/api/health` 是否返回 `healthy`
- WebSocket 未被浏览器插件或代理拦截

## 7. 发布版说明

构建脚本 [build_release.bat](./build_release.bat) 会做两步：

1. 用 `PyInstaller` 构建 Python 后端 sidecar
2. 用 `Tauri` 构建 NSIS 安装包

安装包输出目录：

- `glimpse-frontend/src-tauri/target/release/bundle/nsis/`

发布版运行时：

- 数据默认写入 `%LOCALAPPDATA%\Glimpse\GlimpseData`
- 可将 `.env` 放在应用根目录，或放在 `%LOCALAPPDATA%\Glimpse\GlimpseData\.env`

## 8. 目录结构

```text
Glimpse/
├── api/                      # FastAPI API 层
├── config/                   # 配置管理
├── core/                     # 截图、任务、集群缓冲
├── db/                       # SQLite / ChromaDB
├── services/                 # 业务服务
├── ui/                       # 旧 PySide6 UI
├── glimpse-frontend/         # Vue 3 + Tauri 前端
├── docs/                     # 产品、架构与测试文档
├── scripts/                  # 构建、环境与维护脚本
├── main.py                   # Vue + Tauri 默认源码入口
├── main_api.py               # FastAPI 后端入口
├── main_legacy_qt.py         # 旧 PySide6 回退入口
├── build_release.bat         # Windows 安装包构建
├── start.bat                 # 一键启动当前桌面版
├── start_tauri.bat           # 静默启动 Tauri
└── start_tauri_visible.bat   # 可见模式启动 Tauri
```

## 9. 项目文档

- [产品、架构与业务流程](./docs/README.md)
- [测试与验证](./docs/TESTING.md)

FastAPI 的现行请求和响应模型以运行时 `/docs` 页面为准。旧课程或团队协作
材料位于 `docs/archive/`，不作为当前实现依据。
