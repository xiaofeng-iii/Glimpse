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

应用版本只在 `glimpse-frontend/src-tauri/Cargo.toml` 的
`[package].version` 中维护。Tauri 安装包和内置 Python API 都从该版本派生；
`pyproject.toml` 中的版本仅作为 Python 包元数据镜像，`Cargo.lock` 中的根包版本
由同步工具维护；这些镜像和锁文件都不要手工修改。

同步版本号并检查重复版本字段：

```powershell
python scripts/set_version.py 0.2.0
python scripts/set_version.py --check
```

一键提交当前改动、创建版本标签并推送到 GitHub：

```powershell
.\scripts\release.ps1 -Version 0.2.0
```

脚本会显示待提交文件，并要求输入 `v0.2.0` 确认。推送成功后，
`.github/workflows/release.yml` 会在 GitHub 的 Windows 服务器上运行完整测试、
构建 NSIS 安装包、生成 SHA-256 校验文件并创建 GitHub Release。
可先使用 `-DryRun` 预览，或在无人值守环境中明确传入 `-Yes`。

### 正式版发布后的 Release 说明（必做）

正式版标签触发的 Workflow 使用 `--generate-notes` 创建 Release；自动正文只是
提交列表或 compare 链接，不能作为最终发布说明。Workflow 成功且安装包上传后，
必须补写面向用户的中文说明，完成正文验收后才能宣布发布完成。

1. 从上一正式版到本版的提交记录收集素材，只保留用户能感知的变化：

   ```powershell
   $PreviousTag = "v0.2.1"
   $CurrentTag = "v0.2.2"
   git log --oneline "$PreviousTag..$CurrentTag"
   ```

2. 在 `.tmp/` 中准备临时发布说明文件：

   ```powershell
   $NotesFile = ".tmp/release-notes-$CurrentTag.md"
   ```

   正文使用以下骨架：

   ```markdown
   ## Glimpse vX.Y.Z

   **新特性**
   - 用户可感知的新能力

   **优化**
   - 用户能感知的体验改善

   **修复**
   - 用户能感知的修复结果

   **Full Changelog**: https://github.com/xiaofeng-iii/Glimpse/compare/v上一版...v本版
   ```

   编写时遵循以下规则：

   - 每条只写一句话且不超过 30 个字，说明用户实际得到的结果。
   - 删除锁、死代码、SemVer、通道名等实现或发布术语。
   - 使用“默认”“不再”“支持”“移除”等准确的结果表述。
   - 没有用户可感知变化的改动不写；某分类无内容时保留标题，不编造条目。
   - `Full Changelog` 使用 `v上一版...v本版` 的 GitHub compare 链接。

3. 用填写后的文件覆盖 Release 正文：

   ```powershell
   gh release edit $CurrentTag --notes-file $NotesFile
   ```

4. 重新读取 GitHub Release，确认正文、正式发布状态和链接都正确：

   ```powershell
   gh release view $CurrentTag --json name,tagName,isDraft,isPrerelease,body,url
   ```

   同时确认安装包和 `SHA256SUMS.txt` 已上传。验收完成后删除临时说明文件；
   在此之前不得把发布报告为完成。`v0.2.1` 的发布说明是文案风格范本。

### 版本命名规范

项目统一采用 SemVer + 预发布后缀，三个发布通道，不再混用日历版本：

| 通道 | 版本号 | Git 标签 | GitHub Release 形态 | 可见性 |
|---|---|---|---|---|
| 正式版 | `0.2.0`、`0.3.0`、`1.0.0` | `v0.2.0` | Release | 所有人可见 |
| 公开预览 | `0.2.0-preview.20260806` | `v0.2.0-preview.20260806` | Pre-release | 所有人可见（带 prerelease 标记） |
| 私密开发版 | `0.2.0-dev.20260806` | `v0.2.0-dev.20260806` | Draft | 仅仓库协作者可见 |

- **正式版**：功能稳定后发布，触发 `.github/workflows/release.yml`
- **公开预览（preview）**：功能完成、准备收集外部反馈时发布，触发 `.github/workflows/preview-release.yml`
- **私密开发版（dev）**：开发中途自测用，不对外暴露半成品，触发 `.github/workflows/dev-release.yml`

三个通道都会校验 `scripts/set_version.py --check`（仓库版本必须与标签/输入完全一致）。
`scripts/set_version.py` 接受标准 SemVer 预发布后缀（`-preview.20260806`、`-dev.20260806`、`-rc.1`）和构建元数据（`+build.5`）。

安装包输出目录：

- `glimpse-frontend/src-tauri/target/release/bundle/nsis/`

发布版运行时：

- 数据默认写入 `%LOCALAPPDATA%\Glimpse\GlimpseData`
- 可将 `.env` 放在应用根目录，或放在 `%LOCALAPPDATA%\Glimpse\GlimpseData\.env`
- 内置 API 进程文件名为 `GlimpseRuntime.exe`，Windows 友好名称为 `Glimpse 核心服务`

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
