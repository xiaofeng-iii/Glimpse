# Glimpse

AI 驱动的桌面记忆检索系统。截图后自动进行 OCR 和 AI 摘要分析，支持语义搜索。

当前仓库同时包含两套桌面入口：

- `python main.py`：原 `PySide6` 桌面界面
- `python main_api.py` + `glimpse-frontend/`：`FastAPI + Vue 3 + Tauri` 新架构

## 环境要求

- Python 3.10+
- Node.js 18+
- Windows / macOS / Linux
- 可选：Rust（仅 Tauri 打包或 `tauri dev` 需要）

## 安装

```bash
pip install -r requirements.txt
```

前端开发依赖：

```bash
cd glimpse-frontend
npm install
```

## 配置

创建 `.env` 文件：

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
```

## 启动

### 方案 1：启动原 PySide6 桌面版

```bash
python main.py
```

### 方案 2：启动新前后端分离架构

先启动 Python API：

```bash
python main_api.py
```

再启动前端：

```bash
cd glimpse-frontend
npm run dev
```

开发态地址：

- API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`
- Frontend: `http://localhost:1420`

Windows 下也可以直接运行：

```bat
start.bat
```

如果要直接以桌面弹窗壳调试：

```bat
start_tauri.bat
```

## 项目结构

```text
Glimpse/
├── api/                      # FastAPI API 层
├── config/                   # 配置管理
├── core/                     # 核心功能（截图、任务、集群缓冲）
├── db/                       # SQLite / ChromaDB
├── services/                 # 业务服务
├── ui/                       # 旧 PySide6 UI
├── glimpse-frontend/         # Vue 3 + Tauri 前端
├── main.py                   # 旧桌面入口
├── main_api.py               # 新 API 入口
└── start.bat                 # 一键启动 API + 前端
```

## 快捷键

- `Ctrl+Shift+G`：全局截图
- `Ctrl+F`：聚焦搜索框
- `Escape`：清空搜索

## 文档

- [前端重构说明](./FRONTEND_REFACTOR.md)
- [前端架构](./docs/FRONTEND_ARCHITECTURE.md)
- [UI 组件清单](./docs/UI_COMPONENTS.md)
- [用户交互流程](./docs/UI_FLOWS.md)
