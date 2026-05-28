"""
Thread-safe signal/event primitives with optional asyncio subscriber support.
"""
import inspect
import threading
import weakref
from typing import Any, Callable, List, Optional

from async_runtime import get_async_runtime


class _SubscriberRef:
    """Holds weak references for subscribers when possible."""

    def __init__(self, callback: Callable[..., Any]):
        self._strong_callback: Optional[Callable[..., Any]] = None
        self._func = getattr(callback, "__func__", None)
        self._owner = getattr(callback, "__self__", None)
        self._owner_id = id(self._owner) if self._owner is not None else None

        if self._owner is not None and self._func is not None:
            self._ref = weakref.WeakMethod(callback)
            return

        self._ref = None
        self._strong_callback = callback

    def get(self) -> Optional[Callable[..., Any]]:
        if self._ref is not None:
            return self._ref()
        return self._strong_callback

    def matches(self, callback: Callable[..., Any]) -> bool:
        owner = getattr(callback, "__self__", None)
        func = getattr(callback, "__func__", None)
        if owner is not None and func is not None:
            return self._owner_id == id(owner) and self._func is func
        return self.get() is callback


class EventSignal:
    """Minimal Qt-like signal interface for pure Python modules."""

    def __init__(self, name: str):
        self._name = name
        self._lock = threading.RLock()
        self._subscribers: List[_SubscriberRef] = []

    def connect(self, callback: Callable[..., Any]) -> Callable[..., Any]:
        with self._lock:
            self._purge_dead_locked()
            if any(ref.matches(callback) for ref in self._subscribers):
                return callback
            self._subscribers.append(_SubscriberRef(callback))
        return callback

    def disconnect(self, callback: Callable[..., Any]) -> None:
        with self._lock:
            self._subscribers = [
                ref for ref in self._subscribers
                if not ref.matches(callback) and ref.get() is not None
            ]

    def emit(self, *args, **kwargs) -> None:
        for callback in self._snapshot():
            try:
                result = callback(*args, **kwargs)
                if inspect.isawaitable(result):
                    get_async_runtime().create_task(result)
            except Exception as exc:
                print(f"Signal '{self._name}' subscriber error: {exc}")

    def _snapshot(self) -> List[Callable[..., Any]]:
        with self._lock:
            self._purge_dead_locked()
            callbacks = []
            for ref in self._subscribers:
                callback = ref.get()
                if callback is not None:
                    callbacks.append(callback)
            return callbacks

    def _purge_dead_locked(self) -> None:
        self._subscribers = [ref for ref in self._subscribers if ref.get() is not None]
