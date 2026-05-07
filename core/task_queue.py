"""
Task Queue - ThreadPoolExecutor 调度与任务生命周期管理
"""
import time
from typing import Callable, Optional, Any, Dict
from dataclasses import dataclass, field
from enum import Enum, auto
from concurrent.futures import ThreadPoolExecutor, Future
import threading


class TaskStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass
class Task:
    id: str
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    callback: Optional[Callable] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    @property
    def duration(self) -> Optional[float]:
        if self.started_at is None:
            return None
        end = self.completed_at or time.time()
        return end - self.started_at


class TaskQueue:
    """任务队列管理器 - 单例模式"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._tasks: Dict[str, Task] = {}
        self._futures: Dict[str, Future] = {}
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._shutdown = False

    def submit(
        self,
        task_id: str,
        func: Callable,
        *args,
        callback: Optional[Callable] = None,
        **kwargs,
    ) -> Optional[Task]:
        with self._lock:
            if self._shutdown:
                raise RuntimeError("TaskQueue has been shut down")
            if task_id in self._tasks:
                existing = self._tasks[task_id]
                if existing.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                    return existing

            task = Task(
                id=task_id,
                func=func,
                args=args,
                kwargs=kwargs,
                callback=callback,
            )
            self._tasks[task_id] = task

        future = self._executor.submit(self._run_task, task)
        with self._lock:
            self._futures[task_id] = future

        return task

    def _run_task(self, task: Task) -> Any:
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()

        try:
            result = task.func(*task.args, **task.kwargs)
            task.status = TaskStatus.COMPLETED
            task.result = result
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
        finally:
            task.completed_at = time.time()
            with self._condition:
                self._condition.notify_all()
            if task.callback:
                try:
                    task.callback(task)
                except Exception:
                    pass

        return task.result

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        with self._lock:
            if task_id not in self._tasks:
                return False
            task = self._tasks[task_id]
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                return False
            if task_id in self._futures:
                self._futures[task_id].cancel()
            task.status = TaskStatus.CANCELLED
            return True

    def get_all_tasks(self) -> Dict[str, Task]:
        return self._tasks.copy()

    def clear_completed(self):
        with self._lock:
            completed_ids = [
                tid for tid, t in self._tasks.items()
                if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
            ]
            for tid in completed_ids:
                del self._tasks[tid]
                if tid in self._futures:
                    del self._futures[tid]

    def get_running_tasks(self) -> Dict[str, Task]:
        """获取所有正在运行的任务"""
        with self._lock:
            return {
                tid: task for tid, task in self._tasks.items()
                if task.status == TaskStatus.RUNNING
            }

    def get_pending_tasks(self) -> Dict[str, Task]:
        """获取所有待处理的任务"""
        with self._lock:
            return {
                tid: task for tid, task in self._tasks.items()
                if task.status == TaskStatus.PENDING
            }

    def wait_for_tasks_completion(self, timeout: Optional[float] = None) -> bool:
        """等待所有任务完成（用于热更新前的资源清理）

        Args:
            timeout: 最大等待时间（秒），None 表示无限等待

        Returns:
            是否所有任务都已完成
        """
        start_time = time.time()
        with self._condition:
            while True:
                active_tasks = [
                    tid for tid, t in self._tasks.items()
                    if t.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
                ]

                if not active_tasks:
                    return True

                if timeout is not None:
                    elapsed = time.time() - start_time
                    remaining = timeout - elapsed
                    if remaining <= 0:
                        return False
                    if not self._condition.wait(timeout=remaining):
                        return False
                else:
                    self._condition.wait()

    def cancel_all_pending(self) -> int:
        """取消所有待处理的任务

        Returns:
            取消的任务数量
        """
        cancelled_count = 0
        with self._condition:
            for tid, task in self._tasks.items():
                if task.status == TaskStatus.PENDING:
                    if tid in self._futures:
                        self._futures[tid].cancel()
                    task.status = TaskStatus.CANCELLED
                    task.error = "Cancelled by user"
                    task.completed_at = time.time()
                    cancelled_count += 1
            if cancelled_count > 0:
                self._condition.notify_all()
        return cancelled_count
    
    def reset(self):
        """重置队列状态（用于测试或重新初始化场景）"""
        with self._lock:
            self._shutdown = False
            # 如果 executor 已关闭，创建新的
            if self._executor._shutdown:
                self._executor = ThreadPoolExecutor(max_workers=4)

    def shutdown(self, wait: bool = True):
        with self._lock:
            self._shutdown = True
        self._executor.shutdown(wait=wait)


task_queue = TaskQueue()
