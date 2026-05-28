"""
Shared asyncio runtime for modules that need timers or coroutine dispatch
without owning the application's main event loop.
"""
import asyncio
import threading
from concurrent.futures import Future
from typing import Coroutine, Optional


class AsyncRuntime:
    """Owns a dedicated background asyncio loop."""

    _instance: Optional["AsyncRuntime"] = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_ready = threading.Event()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="glimpse-asyncio",
            daemon=True,
        )
        self._thread.start()
        self._loop_ready.wait()

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        self._loop_ready.wait()
        if self._loop is None:
            raise RuntimeError("Async runtime loop failed to initialize")
        return self._loop

    def _run_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._loop_ready.set()

        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

    def create_task(self, coroutine: Coroutine) -> Future:
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop)

    def stop(self) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(loop.stop)
        self._thread.join(timeout=5)


def get_async_runtime() -> AsyncRuntime:
    return AsyncRuntime()
