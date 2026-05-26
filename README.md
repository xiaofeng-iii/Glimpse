# Glimpse

AI 驱动的桌面记忆检索系统。截图后自动进行 OCR 和 AI 摘要分析，支持语义搜索。

## 环境要求

- Python 3.10+
- Windows / macOS / Linux

## 依赖安装

```bash
pip install -r requirements.txt
```

## 配置

创建 `.env` 文件：

```
OPENAI_API_KEY=your_api_key_here
```

## 运行

```bash
python main.py
```

## 项目结构

```
Glimpse/
├── main.py                 # 程序入口
├── container.py            # 依赖注入容器
├── config/                 # 配置
├── core/                   # 核心功能（截图、任务队列）
├── db/                     # 数据库（SQLite、ChromaDB）
├── services/               # 业务服务（记忆、搜索）
├── ui/                     # 界面
├── docs/                   # 文档
└── GlimpseData/            # 数据存储
```

## 快捷键

- `Ctrl+Shift+G` - 全局截图
- `Ctrl+F` - 聚焦搜索框
- `Escape` - 清空搜索

## 前端开发

项目使用 **PySide6** 构建桌面 UI。

### 前端文档

- [前端架构](./docs/FRONTEND_ARCHITECTURE.md) — 技术栈、数据流、信号总线
- [UI 组件清单](./docs/UI_COMPONENTS.md) — 所有控件、布局、信号连接
- [用户交互流程](./docs/UI_FLOWS.md) — 搜索、截图、设置等完整流程
- [前端待办事项](./docs/FRONTEND_TODO.md) — 已知需求和改进建议

### 快速开始

```bash
# 进入前端开发环境
conda activate glimpse

# 运行应用
python main.py
```
