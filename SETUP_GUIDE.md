# Glimpse 快速启动指南

本文档面向第一次拉取仓库的开发成员。

## 1. 安装前确认

必须具备：

- Python `3.10+`
- Node.js `18+`

如果要运行桌面弹窗，还需要：

- Rust / Cargo
- Windows 下可用的 MSVC C++ 工具链

## 2. 安装依赖

在仓库根目录执行：

```powershell
pip install -r requirements.txt
```

安装前端依赖：

```powershell
cd glimpse-frontend
npm install
cd ..
```

如果需要打包发布版，再执行：

```powershell
pip install -r requirements-packaging.txt
```

## 3. 配置环境变量

复制 `.env.example` 为 `.env`，至少填写：

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
```

如果使用 OpenAI 兼容平台，请同时确认：

- `OPENAI_BASE_URL` 正确
- `MODEL` 填的是实际可调用的模型 / endpoint id

## 4. 启动方式

### A. 只跑后端

```powershell
python main_api.py
```

### B. 跑网页开发页

先启动后端：

```powershell
python main_api.py
```

再启动前端：

```powershell
cd glimpse-frontend
npm run dev
```

访问：

- `http://localhost:1420`

### C. 跑 Tauri 弹窗

推荐可见模式：

```powershell
.\start_tauri_visible.bat
```

如果只是想静默弹出桌面窗口：

```powershell
.\start_tauri.bat
```

## 5. PowerShell 注意事项

在 PowerShell 中运行仓库内脚本时，要加 `.\`：

```powershell
.\start.bat
.\start_tauri.bat
.\start_tauri_visible.bat
.\build_release.bat
```

不要直接写：

```powershell
start_tauri.bat
```

否则 PowerShell 可能提示“命令不存在”。

## 6. 常见问题

### 1. `cargo` 找不到

优先确认：

```powershell
cargo --version
rustup --version
```

如果机器已经装过 Rust，但当前终端识别不到，先关闭终端再重新打开。

### 2. Tauri 启动没反应

优先使用：

```powershell
.\start_tauri_visible.bat
```

因为 `start_tauri.bat` 是静默模式，失败时不直接显示终端报错。

### 3. `Port 1420 is already in use`

说明已有前端开发服务器在运行。请先关掉旧的 `npm run dev` 进程，再重新启动 Tauri。

### 4. 后端已启动但前端显示未连接

先检查：

```powershell
http://127.0.0.1:8000/api/health
```

浏览器或接口工具中应返回：

```json
{"status":"healthy", ...}
```

## 7. 推荐启动顺序

团队开发时建议优先按下面顺序：

1. 配置 `.env`
2. `pip install -r requirements.txt`
3. `cd glimpse-frontend && npm install`
4. 先跑 `python main_api.py`
5. 再根据需要选择：
   - 网页开发页：`cd glimpse-frontend && npm run dev`
   - 桌面弹窗：`.\start_tauri_visible.bat`
