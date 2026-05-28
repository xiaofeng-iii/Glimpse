# Glimpse 环境配置指南

## 环境要求

- Python 3.10+
- Node.js 18+
- Windows / macOS / Linux
- 可选：Rust（Tauri 开发 / 打包）

## Python 依赖安装

```bash
pip install -r requirements.txt
```

## 前端依赖安装

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

## 运行方式

### 1. 旧版 PySide6 界面

```bash
python main.py
```

### 2. 新版 FastAPI + Vue 3 + Tauri 开发模式

启动 API：

```bash
python main_api.py
```

启动前端：

```bash
cd glimpse-frontend
npm run dev
```

一键启动：

```bat
start.bat
```

桌面弹窗模式调试：

```bat
start_tauri.bat
```

## 依赖说明

| 类别 | 依赖 | 说明 |
|------|------|------|
| Legacy UI | `PySide6==6.11.0` | 旧 Qt for Python 桌面界面 |
| API | `fastapi`, `uvicorn`, `websockets`, `pydantic` | 新前后端分离接口层 |
| 数据库 | `chromadb==0.4.18` | 向量数据库 |
| Embedding | `sentence-transformers==2.2.2` | 文本嵌入模型 |
| 截图 | `mss==9.0.1`, `Pillow==10.2.0` | 屏幕截图处理 |
| OCR | `rapidocr-onnxruntime==1.4.4` | 文字识别 |
| 输入 | `pynput==1.7.6` | 全局热键监听 |
| AI | `openai==1.13.3` | AI 接口调用 |
| 工具 | `psutil==5.9.8`, `python-dateutil==2.9.0` | 系统工具 |

## 故障排除

### Python 依赖安装失败

```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### 前端依赖安装失败

```bash
cd glimpse-frontend
npm cache clean --force
npm install
```

### Tauri 无法启动

- 先确认 `python main_api.py` 已经启动
- 确认本机已安装 Rust 工具链
- 确认前端目录下已执行 `npm install`
