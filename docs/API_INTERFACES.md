# Glimpse 对外接口规范

本文档列出 Glimpse 项目当前的对外接口，包括公共 API 和服务注册接口。

---

## 1. 依赖注入容器 (DI Container)

**文件**: `container.py`

### DIContainer 类

依赖注入容器，支持单例、作用域、瞬态三种生命周期。

#### 注册接口

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `register_singleton(name, instance)` | `name: str`, `instance: Any` | `None` | 注册单例实例 |
| `register_singleton_factory(name, factory)` | `name: str`, `factory: Callable[[], Any]` | `None` | 注册单例工厂 |
| `register_scoped(name, factory)` | `name: str`, `factory: Callable[[], Any]` | `None` | 注册作用域服务 |
| `register_transient(name, factory)` | `name: str`, `factory: Callable[[], Any]` | `None` | 注册瞬态服务 |
| `register_shutdown_handler(handler)` | `handler: Callable[[], None]` | `None` | 注册关闭处理器 |

#### 解析接口

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `get(name, scope_id=None)` | `name: str`, `scope_id: Optional[str]` | `Any` | 获取服务实例 |
| `has(name)` | `name: str` | `bool` | 检查服务是否已注册 |
| `create_scope(scope_id=None)` | `scope_id: Optional[str]` | `Scope` | 创建作用域 |
| `release_scope(scope_id)` | `scope_id: str` | `None` | 释放作用域 |

#### 生命周期管理

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `initialize_defaults()` | 无 | `None` | 初始化默认服务注册 |
| `shutdown()` | 无 | `None` | 关闭容器并释放所有资源 |

### Scope 类

作用域管理器，提供独立的作用域实例。

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `get(name)` | `name: str` | `Any` | 在作用域内获取服务 |
| `release()` | 无 | `None` | 释放作用域 |

### 全局实例

```python
container: DIContainer  # 全局单例容器
```

---

## 2. 记忆服务 (Memory Service)

**文件**: `services/memory_service.py`

### MemoryService 类

协调截图、OCR、AI摘要生成、存储的完整记忆流程。

#### 构造函数

```python
def __init__(
    self,
    sqlite_manager: "SQLiteManager",
    chroma_manager: "ChromaManager",
    ocr_engine: "OCREngine",
    ai_client: "AIClient",
    embedding_client: "EmbeddingClient",
    task_queue: Optional["TaskQueue"] = None,
)
```

#### 主要接口

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `create_memory(image_path, app_name="unknown", stream_callback=None)` | `image_path: str`, `app_name: str`, `stream_callback: Optional[Callable[[str], None]]` | `Optional[str]` | 创建记忆（同步） |
| `create_memory_async(image_path, app_name="unknown", on_complete=None, on_error=None)` | `image_path: str`, `app_name: str`, `on_complete: Optional[Callable[[Optional[str]], None]]`, `on_error: Optional[Callable[[str], None]]` | `None` | 创建记忆（异步） |
| `create_cluster_memory(image_paths, app_name="unknown", stream_callback=None)` | `image_paths: List[str]`, `app_name: str`, `stream_callback: Optional[Callable[[str], None]]` | `Optional[str]` | 创建集群记忆 |
| `create_cluster_memory_async(image_paths, app_name="unknown", on_complete=None, on_error=None)` | `image_paths: List[str]`, `app_name: str`, `on_complete: Optional[Callable[[Optional[str]], None]]`, `on_error: Optional[Callable[[str], None]]` | `None` | 创建集群记忆（异步） |
| `delete_memory(memory_id)` | `memory_id: str` | `bool` | 删除记忆 |
| `get_memory(memory_id)` | `memory_id: str` | `Optional[MemoryRecord]` | 获取单条记忆 |
| `get_recent_memories(limit=100, offset=0)` | `limit: int`, `offset: int` | `List[MemoryRecord]` | 获取最近记忆 |
| `get_active_count()` | 无 | `int` | 获取活动任务数 |
| `set_progress_callback(callback)` | `callback: Callable[[str], None]` | `None` | 设置进度回调 |

---

## 3. 搜索服务 (Search Service)

**文件**: `services/search_service.py`

### SearchService 类

统一管理文本搜索和向量搜索。

#### 构造函数

```python
def __init__(
    self,
    sqlite_manager: "SQLiteManager",
    chroma_manager: "ChromaManager",
    embedding_client: "EmbeddingClient",
)
```

#### 主要接口

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `search(query, limit=20)` | `query: str`, `limit: int` | `List[MemoryRecord]` | 执行搜索 |
| `set_search_mode(mode)` | `mode: str` ("text" \| "vector" \| "hybrid") | `bool` | 设置搜索模式 |
| `get_search_mode()` | 无 | `str` | 获取当前搜索模式 |
| `get_recent_memories(limit=100)` | `limit: int` | `List[MemoryRecord]` | 获取最近记忆 |
| `get_memory_by_id(memory_id)` | `memory_id: str` | `Optional[MemoryRecord]` | 按ID获取记忆 |

---

## 4. SQLite 数据库管理

**文件**: `db/sqlite_manager.py`

### MemoryRecord 数据类

```python
@dataclass
class MemoryRecord:
    id: str
    created_at: str
    image_path: str
    ai_summary: str
    app_name: str
    text_content: Optional[str] = None
    extra_images: Optional[str] = None
    sync_status: str = "PENDING"
    match_sources: List[str] = field(default_factory=list)
```

#### 方法

| 方法 | 返回值 | 说明 |
|-----|-------|------|
| `to_dict()` | `Dict[str, Any]` | 转换为字典 |
| `from_row(row: tuple)` | `MemoryRecord` | 从数据库行创建实例（类方法） |

### SQLiteManager 类

SQLite 管理器，支持多实例隔离，注入 PathManager。

#### 构造函数

```python
def __init__(self, path_manager: "PathManager")
```

#### CRUD 接口

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `insert_memory(record)` | `record: MemoryRecord` | `bool` | 插入记忆 |
| `get_memory_by_id(memory_id)` | `memory_id: str` | `Optional[MemoryRecord]` | 按ID查询 |
| `get_all_memories(limit=100, offset=0)` | `limit: int`, `offset: int` | `List[MemoryRecord]` | 获取所有记忆 |
| `search_memories(query, limit=20)` | `query: str`, `limit: int` | `List[MemoryRecord]` | FTS5全文搜索 |
| `update_memory_summary(memory_id, summary)` | `memory_id: str`, `summary: str` | `bool` | 更新摘要 |
| `delete_memory(memory_id)` | `memory_id: str` | `bool` | 删除记忆 |
| `get_memories_count()` | 无 | `int` | 获取记忆总数 |
| `close()` | 无 | `None` | 关闭连接 |

---

## 5. ChromaDB 向量数据库管理

**文件**: `db/chroma_manager.py`

### ChromaManager 类

Chroma 向量数据库管理器，支持多实例隔离，注入 PathManager。

#### 构造函数

```python
def __init__(self, path_manager: "PathManager")
```

#### 向量操作接口

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `add_memory(memory_id, text, embedding, metadata=None)` | `memory_id: str`, `text: str`, `embedding: List[float]`, `metadata: Optional[Dict[str, Any]]` | `bool` | 添加向量记忆 |
| `search_similar(query_embedding, n_results=5, where=None)` | `query_embedding: List[float]`, `n_results: int`, `where: Optional[Dict[str, Any]]` | `List[Dict[str, Any]]` | 相似度搜索 |
| `delete_memory(memory_id)` | `memory_id: str` | `bool` | 删除记忆 |
| `update_memory(memory_id, text=None, embedding=None, metadata=None)` | `memory_id: str`, `text: Optional[str]`, `embedding: Optional[List[float]]`, `metadata: Optional[Dict[str, Any]]` | `bool` | 更新记忆 |
| `get_memory_count()` | 无 | `int` | 获取记忆数量 |
| `get_all_memory_ids(limit=1000, offset=0)` | `limit: int`, `offset: int` | `List[str]` | 获取所有记忆ID |
| `close()` | 无 | `None` | 关闭连接 |

---

## 6. AI 客户端

**文件**: `services/ai_client.py`

### AIClient 类

AI 客户端，支持构造函数注入 SettingsManager 依赖。

#### 构造函数

```python
def __init__(self, settings_manager: Optional["SettingsManager"] = None)
```

#### 配置接口

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `configure(api_key, base_url=DEFAULT_BASE_URL, model=None, timeout=DEFAULT_TIMEOUT, provider=DEFAULT_PROVIDER, provider_type=DEFAULT_PROVIDER_TYPE)` | `api_key: str`, `base_url: str`, `model: Optional[str]`, `timeout: int`, `provider: str`, `provider_type: str` | `bool` | 配置API |
| `configure_from_settings()` | 无 | `bool` | 从设置加载配置 |
| `is_configured()` | 无 | `bool` | 检查是否已配置 |
| `test_connection()` | 无 | `bool` | 测试连接 |

#### AI 接口

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `analyze_image(image_path, prompt="描述这张截图的内容", stream_callback=None)` | `image_path: str`, `prompt: str`, `stream_callback: Optional[Callable[[str], None]]` | `str` | 分析图像 |
| `generate_summary(text, prompt="为以下内容生成简短摘要：")` | `text: str`, `prompt: str` | `str` | 生成文本摘要 |

---

## 7. OCR 引擎

**文件**: `services/ocr_engine.py`

### OCREngine 抽象基类

| 抽象方法 | 参数 | 返回值 | 说明 |
|---------|------|-------|------|
| `extract_text(image_path)` | `image_path: str` | `Optional[str]` | 提取文本 |
| `extract_text_boxes(image_path)` | `image_path: str` | `List[Tuple[str, Tuple[int, int, int, int]]]` | 提取文本框 |

### RapidOCREngine 类

RapidOCR 引擎实现。

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `extract_text(image_path)` | `image_path: str` | `Optional[str]` | 提取文本 |
| `extract_text_boxes(image_path)` | `image_path: str` | `List[Tuple[str, Tuple[int, int, int, int]]]` | 提取带坐标的文本 |

### 工厂函数

```python
def create_ocr_engine(engine_type: str = "rapidocr") -> OCREngine
```

### 全局实例

```python
ocr_engine: RapidOCREngine  # 全局默认OCR引擎
```

---

## 8. 嵌入服务客户端

**文件**: `services/embedding_client.py`

### EmbeddingClient 类

嵌入服务客户端，负责文本嵌入和向量处理。

#### 构造函数

```python
def __init__(self)
```

#### 嵌入接口

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `get_embedding(text)` | `text: str` | `list` | 获取文本嵌入向量 |
| `get_embeddings(texts)` | `texts: list` | `list` | 批量获取嵌入向量 |
| `calculate_similarity(embedding1, embedding2)` | `embedding1: list`, `embedding2: list` | `float` | 计算余弦相似度 |

---

## 9. 截图管理器

**文件**: `core/capture.py`

### CaptureResult 数据类

```python
@dataclass
class CaptureResult:
    image_path: str
    width: int
    height: int
    timestamp: float
    app_name: Optional[str] = None
```

### CaptureManager 类

截图管理器，注入 PathManager，包含集群防抖。

#### 构造函数

```python
def __init__(self, path_manager: "PathManager")
```

#### 截图接口

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `capture_fullscreen(delay=0)` | `delay: float` | `Optional[CaptureResult]` | 全屏截图 |
| `capture_region(region)` | `region: Tuple[int, int, int, int]` (x, y, w, h) | `Optional[CaptureResult]` | 区域截图 |

#### 设置接口

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `set_debounce_interval(interval)` | `interval: float` | `bool` | 设置防抖间隔(秒) |
| `set_cluster_threshold(threshold)` | `threshold: float` | `bool` | 设置集群阈值(秒) |
| `set_max_captures_per_window(max_captures)` | `max_captures: int` | `bool` | 设置窗口最大截图数 |
| `update_settings(settings)` | `settings: dict` | `bool` | 批量更新设置 |
| `get_settings()` | 无 | `dict` | 获取当前设置 |
| `close()` | 无 | `None` | 释放资源 |

---

## 10. 键盘管理器

**文件**: `services/keyboard_manager.py`

### KeyboardManager 类

键盘管理器，负责全局快捷键监听和配置。

#### 快捷键接口

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `register_hotkey(hotkey, callback)` | `hotkey: str`, `callback: Callable` | `None` | 注册全局快捷键 |
| `unregister_hotkey(hotkey)` | `hotkey: str` | `None` | 注销快捷键 |
| `clear_hotkeys()` | 无 | `None` | 清空所有快捷键 |
| `get_hotkeys()` | 无 | `Dict[str, Callable]` | 获取所有快捷键 |

#### 生命周期接口

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `start_listening()` | 无 | `None` | 开始监听 |
| `stop_listening()` | 无 | `None` | 停止监听 |
| `restart_listening()` | 无 | `None` | 重启监听 |
| `is_running()` | 无 | `bool` | 检查是否运行中 |
| `reload_hotkeys(hotkeys)` | `hotkeys: Dict[str, Callable]` | `bool` | 重新加载快捷键配置 |

### 全局实例

```python
keyboard_manager: KeyboardManager  # 全局单例
```

---

## 11. 任务队列

**文件**: `core/task_queue.py`

### TaskStatus 枚举

```python
class TaskStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()
```

### Task 数据类

```python
@dataclass
class Task:
    id: str
    func: Callable
    args: tuple
    kwargs: dict
    status: TaskStatus
    result: Any
    error: Optional[str]
    callback: Optional[Callable]
    created_at: float
    started_at: Optional[float]
    completed_at: Optional[float]

    @property
    def duration(self) -> Optional[float]: ...
```

### TaskQueue 类

任务队列管理器，单例模式。

#### 任务管理接口

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `submit(task_id, func, *args, callback=None, **kwargs)` | `task_id: str`, `func: Callable`, `*args`, `callback: Optional[Callable]`, `**kwargs` | `Optional[Task]` | 提交任务 |
| `get_task(task_id)` | `task_id: str` | `Optional[Task]` | 获取任务 |
| `cancel_task(task_id)` | `task_id: str` | `bool` | 取消任务 |
| `get_all_tasks()` | 无 | `Dict[str, Task]` | 获取所有任务 |
| `clear_completed()` | 无 | `None` | 清理已完成任务 |
| `get_running_tasks()` | 无 | `Dict[str, Task]` | 获取运行中任务 |
| `get_pending_tasks()` | 无 | `Dict[str, Task]` | 获取待处理任务 |
| `wait_for_tasks_completion(timeout=None)` | `timeout: Optional[float]` | `bool` | 等待任务完成 |
| `cancel_all_pending()` | 无 | `int` | 取消所有待处理任务 |
| `shutdown(wait=True)` | `wait: bool` | `None` | 关闭队列 |

### 全局实例

```python
task_queue: TaskQueue  # 全局单例
```

---

## 12. 路径管理器

**文件**: `config/path_manager.py`

### PathManager 类

路径管理器，强制所有数据写入 `./GlimpseData` 目录。

#### 属性接口

| 属性 | 类型 | 说明 |
|-----|------|------|
| `project_root` | `Path` | 项目根目录 |
| `data_root` | `Path` | 数据根目录 (GlimpseData) |
| `screenshots_dir` | `Path` | 截图目录 |
| `database_dir` | `Path` | 数据库目录 |
| `logs_dir` | `Path` | 日志目录 |
| `cache_dir` | `Path` | 缓存目录 |
| `config_dir` | `Path` | 配置目录 |
| `sqlite_path` | `Path` | SQLite 数据库路径 |
| `chroma_path` | `Path` | ChromaDB 路径 |
| `log_file` | `Path` | 日志文件路径 |

#### 方法接口

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `get_screenshot_path(filename)` | `filename: str` | `Path` | 获取截图完整路径 |
| `resolve(*parts)` | `*parts: str` | `Path` | 解析数据目录下的路径 |

### 全局实例

```python
path_manager: PathManager  # 全局单例
```

---

## 13. 设置管理器

**文件**: `config/settings_manager.py`

### SettingsManager 类

设置管理器，支持构造函数注入 PathManager 依赖。

#### 构造函数

```python
def __init__(self, path_manager: "PathManager")
```

#### 读写接口

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `get(key, default=None)` | `key: str`, `default: Any` | `Any` | 获取设置项，支持点分路径 |
| `set(key, value)` | `key: str`, `value: Any` | `bool` | 设置设置项 |
| `get_all()` | 无 | `Dict[str, Any]` | 获取所有设置 |
| `update(settings)` | `settings: Dict[str, Any]` | `bool` | 更新设置（部分更新） |
| `reset()` | 无 | `None` | 重置为默认值 |
| `reload()` | 无 | `None` | 重新加载设置 |
| `has_changes(new_settings)` | `new_settings: Dict[str, Any]` | `bool` | 检查是否有变化 |

### 默认设置结构

```python
{
    "hotkeys": {
        "screenshot": "<ctrl>+<shift>+g",
        "search": "<ctrl>+<f>",
        "clear": "<escape>"
    },
    "screenshot": {
        "debounce_interval": 5.0,
        "cluster_threshold": 2.0,
        "max_captures_per_window": 10
    },
    "ai": {
        "provider": "OpenAI",
        "provider_type": "openai_compatible",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4o-mini",
        "timeout": 30
    },
    "ocr": {
        "engine": "rapidocr",
        "language": "ch"
    },
    "database": {
        "sqlite_timeout": 30,
        "chroma_collection": "memories"
    },
    "cluster": {
        "cluster_mode": false,
        "cluster_auto_submit": true,
        "cluster_max_images": 5,
        "cluster_timeout": 5
    },
    "ui": {
        "theme": "light",
        "auto_hide": False,
        "start_minimized": False
    }
}
```

---

## 14. 容器注册服务清单

通过 `container.initialize_defaults()` 注册的服务列表：

| 服务名 | 生命周期 | 实际类型 | 说明 |
|-------|---------|---------|------|
| `path_manager` | 单例 | `PathManager` | 路径管理 |
| `settings_manager` | 单例 | `SettingsManager` | 设置管理 |
| `ai_client` | 单例 | `AIClient` | AI 客户端 |
| `keyboard_manager` | 单例 | `KeyboardManager` | 键盘管理 |
| `ocr_engine` | 单例 | `RapidOCREngine` | OCR 引擎 |
| `embedding_client` | 单例 | `EmbeddingClient` | 嵌入客户端 |
| `task_queue` | 单例 | `TaskQueue` | 任务队列 |
| `capture_manager` | 单例 | `CaptureManager` | 截图管理 |
| `sqlite_manager` | 单例 | `SQLiteManager` | SQLite 管理 |
| `chroma_manager` | 单例 | `ChromaManager` | ChromaDB 管理 |
| `cluster_buffer` | 单例 | `ClusterBuffer` | 集群缓冲 |
| `memory_service` | 单例 | `MemoryService` | 记忆服务 |
| `search_service` | 单例 | `SearchService` | 搜索服务 |

---

## 15. 类型别名速查

### 常用导入类型

```python
# 数据记录
from db.sqlite_manager import MemoryRecord

# 结果类型
from core.capture import CaptureResult
from core.task_queue import Task, TaskStatus

# 服务接口
from services.ocr_engine import OCREngine, RapidOCREngine

# 容器
from container import container, DIContainer, Scope

# 全局实例
from config.path_manager import path_manager
from services.keyboard_manager import keyboard_manager
from core.task_queue import task_queue
from services.ocr_engine import ocr_engine
```

---

*文档版本: 1.0*
*最后更新: 2026-04-11*
