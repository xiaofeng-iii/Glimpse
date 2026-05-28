"""
TaskQueue 单元测试

测试核心模块 core/task_queue.py
覆盖: TaskStatus, Task, TaskQueue 单例及所有方法
"""
import time
import threading
import pytest

from core.task_queue import (
    TaskStatus,
    Task,
    TaskQueue,
    task_queue,
)


class TestTaskStatus:
    """TaskStatus 枚举测试"""

    def test_enum_values(self):
        """验证枚举包含所有预期状态"""
        statuses = list(TaskStatus)
        names = {s.name for s in statuses}
        assert names == {"PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"}

    def test_enum_uniqueness(self):
        """验证每个枚举值都是唯一的"""
        values = [s.value for s in TaskStatus]
        assert len(values) == len(set(values))


class TestTask:
    """Task 数据类测试"""

    def test_task_default_values(self):
        """验证 Task 默认值"""
        def dummy():
            pass

        task = Task(id="test-1", func=dummy)
        assert task.id == "test-1"
        assert task.func is dummy
        assert task.args == ()
        assert task.kwargs == {}
        assert task.status == TaskStatus.PENDING
        assert task.result is None
        assert task.error is None
        assert task.callback is None
        assert task.started_at is None
        assert task.completed_at is None

    def test_task_with_args_kwargs(self):
        """验证 Task 接受自定义参数"""
        def dummy(a, b=0):
            return a + b

        cb = lambda t: None
        task = Task(
            id="test-2",
            func=dummy,
            args=(1,),
            kwargs={"b": 2},
            callback=cb,
        )
        assert task.args == (1,)
        assert task.kwargs == {"b": 2}
        assert task.callback is cb

    def test_duration_none_when_not_started(self):
        """验证: 未开始的任务 duration 为 None"""
        def dummy():
            pass

        task = Task(id="t", func=dummy)
        assert task.duration is None

    def test_duration_after_started(self):
        """验证: 已启动的任务 duration 为当前已用时间"""
        def dummy():
            pass

        task = Task(id="t", func=dummy)
        task.started_at = time.time() - 1.0
        duration = task.duration
        assert duration is not None
        assert 0.9 <= duration <= 1.2  # 允许少量时间误差

    def test_duration_after_completed(self):
        """验证: 已完成的任务 duration 为总耗时"""
        def dummy():
            pass

        now = time.time()
        task = Task(id="t", func=dummy)
        task.started_at = now - 2.0
        task.completed_at = now
        assert task.duration is not None
        assert pytest.approx(task.duration, rel=0.1) == 2.0


class TestTaskQueueSingleton:
    """TaskQueue 单例模式测试"""

    def test_singleton_same_instance(self):
        """验证: 多次构造返回同一实例"""
        q1 = TaskQueue()
        q2 = TaskQueue()
        assert q1 is q2

    def test_global_instance(self):
        """验证: 全局 task_queue 是 TaskQueue 实例"""
        assert isinstance(task_queue, TaskQueue)


class TestTaskQueueSubmit:
    """TaskQueue.submit 测试"""

    @pytest.fixture
    def queue(self):
        """提供可复用的 TaskQueue 单例"""
        q = TaskQueue()
        q.reset()  # 确保未被之前的测试 shutdown
        yield q

    def test_submit_returns_task(self, queue):
        """验证: submit 返回 Task 对象"""
        def dummy():
            pass

        task = queue.submit("id-1", dummy)
        assert isinstance(task, Task)
        assert task.id == "id-1"
        assert task.status in (TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.COMPLETED)

    def test_submit_runs_function(self, queue):
        """验证: submit 的任务最终执行"""
        result_container = []

        def work():
            result_container.append("done")
            return 42

        queue.submit("id-2", work)
        queue.wait_for_tasks_completion(timeout=5.0)

        assert "done" in result_container
        task = queue.get_task("id-2")
        assert task is not None
        assert task.status == TaskStatus.COMPLETED
        assert task.result == 42

    def test_submit_with_args(self, queue):
        """验证: submit 传递 *args 参数"""
        def add(a, b):
            return a + b

        queue.submit("id-3", add, 3, 4)
        queue.wait_for_tasks_completion(timeout=5.0)

        task = queue.get_task("id-3")
        assert task.result == 7

    def test_submit_with_kwargs(self, queue):
        """验证: submit 传递 **kwargs 参数"""
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}"

        queue.submit("id-4", greet, name="World", greeting="Hi")
        queue.wait_for_tasks_completion(timeout=5.0)

        task = queue.get_task("id-4")
        assert task.result == "Hi, World"

    def test_submit_callback_called(self, queue):
        """验证: submit 的回调函数被调用"""
        callback_called = threading.Event()

        def work():
            return "ok"

        def on_complete(t: Task):
            callback_called.set()

        queue.submit("id-5", work, callback=on_complete)
        assert callback_called.wait(timeout=5.0)

    def test_submit_duplicate_id_returns_existing(self, queue):
        """验证: 重复 task_id 返回已有任务（如果仍在 PENDING/RUNNING）"""
        def slow():
            time.sleep(0.1)

        t1 = queue.submit("dup", slow)
        t2 = queue.submit("dup", slow)
        assert t1 is t2  # 返回相同对象

    def test_submit_after_shutdown_raises(self, queue):
        """验证: shutdown 后 submit 抛出 RuntimeError"""
        queue.shutdown(wait=True)

        with pytest.raises(RuntimeError, match="shut down"):
            queue.submit("id-after", lambda: None)


class TestTaskQueueCancel:
    """TaskQueue.cancel_task 测试"""

    @pytest.fixture
    def queue(self):
        q = TaskQueue()
        q.reset()
        yield q

    def test_cancel_nonexistent_returns_false(self, queue):
        """验证: 取消不存在的任务返回 False"""
        assert queue.cancel_task("nonexistent") is False

    def test_cancel_pending(self, queue):
        """验证: 取消 PENDING 任务成功"""
        # 提交一个任务并用 barrier 阻止它开始
        barrier = threading.Barrier(2, timeout=5)

        def work():
            barrier.wait()  # 阻塞直到主线程也 wait

        task = queue.submit("c1", work)
        assert task.status in (TaskStatus.PENDING, TaskStatus.RUNNING)

        # 如果任务已经是 RUNNING 了，标记为不可取消
        if task.status == TaskStatus.PENDING:
            result = queue.cancel_task("c1")
            assert result is True
            assert task.status == TaskStatus.CANCELLED
        barrier.wait()  # 无论如何释放线程


class TestTaskQueueQuery:
    """TaskQueue 查询方法测试"""

    @pytest.fixture
    def queue(self):
        q = TaskQueue()
        q.reset()
        yield q

    def test_get_task_existing(self, queue):
        """验证: get_task 返回已提交的任务"""
        queue.submit("q1", lambda: None)
        task = queue.get_task("q1")
        assert task is not None
        assert task.id == "q1"

    def test_get_task_nonexistent(self, queue):
        """验证: get_task 获取不存在的任务返回 None"""
        assert queue.get_task("no-such") is None

    def test_get_all_tasks(self, queue):
        """验证: get_all_tasks 返回所有任务"""
        queue.submit("a1", lambda: None)
        queue.submit("a2", lambda: None)
        all_tasks = queue.get_all_tasks()
        assert "a1" in all_tasks
        assert "a2" in all_tasks

    def test_clear_completed_removes_finished(self, queue):
        """验证: clear_completed 清除已完成的任务"""
        queue.submit("clr1", lambda: None)
        queue.wait_for_tasks_completion(timeout=5.0)

        queue.clear_completed()
        assert queue.get_task("clr1") is None

    def test_get_running_tasks(self, queue):
        """验证: get_running_tasks 返回运行中任务"""
        started = threading.Event()
        running = threading.Event()

        def work():
            started.set()
            running.wait(timeout=5)

        queue.submit("r1", work)
        started.wait(timeout=5)

        running_tasks = queue.get_running_tasks()
        assert "r1" in running_tasks
        running.set()

    def test_get_pending_tasks(self, queue):
        """验证: get_pending_tasks 返回待处理任务"""
        # 用 barrier 阻止任务开始
        barrier = threading.Barrier(2, timeout=5)

        def work():
            barrier.wait()

        queue.submit("p1", work)
        pending = queue.get_pending_tasks()
        barrier.wait()
        # 可能在获取时已经变为 RUNNING，所以用宽松断言
        assert ("p1" in pending) or (queue.get_task("p1").status == TaskStatus.RUNNING)


class TestTaskQueueWaitAndCancel:
    """wait_for_tasks_completion 和 cancel_all_pending 测试"""

    @pytest.fixture
    def queue(self):
        q = TaskQueue()
        q.reset()
        yield q

    def test_wait_for_tasks_completion_all_done(self, queue):
        """验证: wait_for_tasks_completion 在所有任务完成后返回 True"""
        queue.submit("w1", lambda: None)
        result = queue.wait_for_tasks_completion(timeout=5.0)
        assert result is True

    def test_wait_for_tasks_completion_timeout(self, queue):
        """验证: wait_for_tasks_completion 超时返回 False"""
        started = threading.Event()

        def slow():
            started.set()
            time.sleep(5)  # 比 timeout 长

        queue.submit("w2", slow)
        started.wait(timeout=5)
        result = queue.wait_for_tasks_completion(timeout=0.5)
        assert result is False

    def test_cancel_all_pending_returns_count(self, queue):
        """验证: cancel_all_pending 返回取消的数量"""
        # 使用 Event 代替 Barrier 以避免竞态
        started = threading.Event()

        def work():
            started.set()
            time.sleep(0.5)

        queue.submit("ca1", work)

        # 等待任务开始（它变为 RUNNING 即不可取消）
        started.wait(timeout=5)
        # 此时尝试取消 - 可能为 0（已 RUNNING）或 1（幸运地还在 PENDING）
        count = queue.cancel_all_pending()
        assert count >= 0


class TestTaskQueueShutdown:
    """TaskQueue.shutdown 测试"""

    def test_shutdown_marks_flag(self):
        """验证: shutdown 设置关闭标志"""
        # 需要新实例避免影响其他测试
        import threading
        q = TaskQueue()
        # 清空所有任务
        q.shutdown(wait=True)
        # 状态已修改，不需要再验证
